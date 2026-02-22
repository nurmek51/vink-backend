from app.modules.esim.repository import EsimRepository
from app.providers.esim_provider.client import EsimProviderClient
from app.providers.epay.client import EpayClient
from app.providers.epay.schemas import EpayCardIdPaymentRequest
from app.core.config import settings
from app.modules.users.repository import UserRepository
from app.modules.esim.schemas import Esim, Tariff, UpdateSettingsRequest, UsageData
from app.modules.users.schemas import User
from app.common.exceptions import NotFoundError, AppError
from app.common.mcc_codes import get_country_by_mcc
from app.common.logging import logger
from typing import List, Optional, Tuple
import httpx
import uuid
import datetime
import time

class EsimService:
    def __init__(self):
        self.repository = EsimRepository()
        self.user_repository = UserRepository()
        self.provider = EsimProviderClient()
        self.epay = EpayClient()
        self._rates_cache: List[Tariff] = []
        self._rates_last_updated = 0.0

    async def _maybe_trigger_autopay(
        self,
        user: User,
        esim_data: dict,
        provider_balance_mb: float,
        current_rate_usd_per_mb: Optional[float],
        country_name: str = "Global",
    ) -> None:
        if not settings.EPAY_ESIM_AUTOPAY_ENABLED:
            return
        if provider_balance_mb > settings.EPAY_ESIM_AUTOPAY_THRESHOLD_MB:
            return
        if current_rate_usd_per_mb is None or current_rate_usd_per_mb <= 0:
            esim_data["autopay_last_status"] = "no_tariff_rate"
            await self.repository.save_esim(esim_data)
            return

        package_mb = float(settings.EPAY_ESIM_AUTOPAY_PACKAGE_MB)
        charge_usd = float(current_rate_usd_per_mb) * package_mb
        charge_kzt = round(charge_usd * float(settings.EPAY_USD_TO_KZT_RATE), 2)
        if charge_kzt <= 0:
            esim_data["autopay_last_status"] = "invalid_tariff_rate"
            await self.repository.save_esim(esim_data)
            return

        now_ts = time.time()
        cooldown_seconds = max(1, settings.EPAY_ESIM_AUTOPAY_COOLDOWN_MINUTES) * 60
        last_attempt_ts = float(esim_data.get("autopay_last_attempt_ts", 0) or 0)
        if (now_ts - last_attempt_ts) < cooldown_seconds:
            return
        if esim_data.get("autopay_in_progress"):
            return

        esim_data["autopay_in_progress"] = True
        esim_data["autopay_last_attempt_ts"] = now_ts
        await self.repository.save_esim(esim_data)

        try:
            saved_cards = await self.epay.get_saved_cards(user.id)
            if not saved_cards:
                esim_data["autopay_last_status"] = "no_saved_card"
                await self.repository.save_esim(esim_data)
                return

            selected_card = self._pick_latest_card_id(saved_cards)
            if not selected_card:
                esim_data["autopay_last_status"] = "no_valid_card"
                await self.repository.save_esim(esim_data)
                return

            invoice_id = self._generate_autopay_invoice_id(esim_data.get("imsi", ""))
            post_link = self._url_join(settings.EPAY_POSTLINK_BASE_URL, "/api/v1/payments/webhook")

            token_resp = await self.epay.obtain_payment_token(
                invoice_id=invoice_id,
                amount=charge_kzt,
                currency="KZT",
                post_link=post_link,
                failure_post_link=post_link,
            )

            pay_req = EpayCardIdPaymentRequest(
                amount=charge_kzt,
                currency="KZT",
                name="VinkSIM AutoPay",
                terminalId=self.epay.terminal_id,
                invoiceId=invoice_id,
                description=f"AutoPay 3GB {country_name} @ {current_rate_usd_per_mb:.6f} USD/MB",
                accountId=user.id,
                email=user.email or "",
                phone=user.phone_number or "",
                backLink=settings.EPAY_DEFAULT_BACK_LINK,
                failureBackLink=settings.EPAY_DEFAULT_FAILURE_BACK_LINK,
                postLink=post_link,
                failurePostLink=post_link,
                language=(user.preferred_language or "rus"),
                paymentType="cardId",
                recurrent=True,
                cardId={"id": selected_card},
            )

            payment_resp = await self.epay.pay_with_saved_card(pay_req, token_resp.access_token)
            if payment_resp.status not in ("AUTH", "CHARGE"):
                esim_data["autopay_last_status"] = f"payment_{(payment_resp.status or 'failed').lower()}"
                await self.repository.save_esim(esim_data)
                return

            await self.provider.top_up(esim_data["imsi"], package_mb)

            esim_data["data_limit"] = float(esim_data.get("data_limit", 0.0) or 0.0) + package_mb
            esim_data["autopay_last_status"] = "success"
            esim_data["autopay_last_success_ts"] = now_ts
            esim_data["autopay_last_card_id"] = selected_card
            esim_data["autopay_last_rate_usd_per_mb"] = float(current_rate_usd_per_mb)
            esim_data["autopay_last_amount_usd"] = round(charge_usd, 4)
            esim_data["autopay_last_amount_kzt"] = charge_kzt
            esim_data["autopay_last_country"] = country_name
            await self.repository.save_esim(esim_data)
        except Exception as exc:
            logger.error("eSIM autopay failed for esim_id=%s: %s", esim_data.get("id"), exc)
            esim_data["autopay_last_status"] = "error"
            await self.repository.save_esim(esim_data)
        finally:
            esim_data["autopay_in_progress"] = False
            await self.repository.save_esim(esim_data)

    @staticmethod
    def _pick_latest_card_id(cards) -> str:
        if not cards:
            return ""
        # Best-effort: prefer card with latest CreatedDate, fallback to first element
        try:
            sorted_cards = sorted(cards, key=lambda c: c.CreatedDate or "", reverse=True)
            return sorted_cards[0].ID
        except Exception:
            return cards[0].ID

    @staticmethod
    def _generate_autopay_invoice_id(imsi: str) -> str:
        tail = (imsi or "000000")[-6:]
        return f"{int(time.time())}{tail}"[:15]

    @staticmethod
    def _url_join(base: str, path: str) -> str:
        return f"{base.rstrip('/')}/{path.lstrip('/')}"

    async def _fetch_rates(self) -> List[Tariff]:
        # Update cache if older than 1 hour (3600 seconds)
        if self._rates_cache and (time.time() - self._rates_last_updated < 3600):
            return self._rates_cache

        url = "https://imsimarket.com/js/data/alternative.rates.json"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                tariffs = []
                for rate in data:
                    tariffs.append(
                        Tariff(
                            plmn=rate.get("PLMN"),
                            network_name=rate.get("NetworkName"),
                            country_name=rate.get("CountryName"),
                            data_rate=float(rate.get("DataRate", 0.0))
                        )
                    )
                
                self._rates_cache = tariffs
                self._rates_last_updated = time.time()
                return tariffs
            except Exception as e:
                logger.error(f"Failed to fetch tariffs: {e}")
                # Return cached outdated or empty if fails
                return self._rates_cache

    async def get_tariffs(self) -> List[Tariff]:
        return await self._fetch_rates()

    async def _resolve_country_and_rate(self, last_mcc: Optional[str]) -> Tuple[str, Optional[float]]:
        country_name = "Global"
        current_rate = None

        if last_mcc:
            try:
                mapped_country = get_country_by_mcc(int(last_mcc))
            except Exception:
                mapped_country = "Unknown"

            if mapped_country != "Unknown":
                country_name = mapped_country
                all_tariffs = await self.get_tariffs()
                country_rates = [t.data_rate for t in all_tariffs if t.country_name == country_name]
                if country_rates:
                    current_rate = min(country_rates)

        return country_name, current_rate

    async def get_user_esims(self, user: User) -> List[Esim]:
        # 1. Get allocated IMSIs from DB
        user_esims_data = await self.repository.get_user_esims(user.id)
        
        # Prefetch rates once
        all_tariffs = await self.get_tariffs()
        
        esims = []
        for data in user_esims_data:
            imsi_info = None
            try:
                # 2. Sync with Provider "Master Profile" data
                imsi_info = await self.provider.get_imsi_info(data["imsi"])
            except Exception:
                pass

            activation_code = data.get("activation_code", "UNKNOWN")

            provider_balance = 0.0
            last_mcc = None
            if imsi_info:
                if imsi_info.BALANCE is not None:
                    provider_balance = float(imsi_info.BALANCE)
                last_mcc = getattr(imsi_info, "LASTMCC", None)
                
                # Sync ICCID if missing or different in DB
                if imsi_info.ICCID and data.get("iccid") != imsi_info.ICCID:
                    data["iccid"] = imsi_info.ICCID
                    data["msisdn"] = imsi_info.MSISDN
                    await self.repository.save_esim(data)

            # Map MCC to Country and find best rate
            country_name = "Global"
            current_rate = None
            if last_mcc:
                try:
                    mapped_country = get_country_by_mcc(int(last_mcc))
                except Exception:
                    mapped_country = "Unknown"
                if mapped_country != "Unknown":
                    country_name = mapped_country
                    country_rates = [t.data_rate for t in all_tariffs if t.country_name == country_name]
                    if country_rates:
                        current_rate = min(country_rates)

            # Auto-recharge: if remaining balance <= threshold, charge tariff-derived amount and add 3GB
            await self._maybe_trigger_autopay(user, data, provider_balance, current_rate, country_name)

            esim = Esim(
                id=data["id"],
                user_id=user.id,
                name=data.get("name", "Vink eSIM"),
                imsi=data["imsi"],
                iccid=imsi_info.ICCID if imsi_info else data.get("iccid"),
                msisdn=imsi_info.MSISDN if imsi_info else data.get("msisdn"),
                data_used=max(0.0, data.get("data_limit", 0.0) - provider_balance), 
                data_limit=data.get("data_limit", 0.0),
                is_active=bool(imsi_info.MSISDN if imsi_info else data.get("msisdn")), 
                activation_code=activation_code,
                provider_balance=provider_balance,
                country=country_name,
                provider="Vink",
                current_rate=current_rate
            )
            esims.append(esim)
                
        return esims

    async def get_esim_by_id(self, user: User, esim_id: str) -> Esim:
        # Check DB ownership
        data = await self.repository.get_esim(esim_id)
        if not data or data.get("user_id") != user.id:
            raise NotFoundError("eSIM not found")
            
        # Fetch provider info
        imsi_info = await self.provider.get_imsi_info(data["imsi"])

        activation_code = data.get("activation_code", "UNKNOWN")
        
        last_mcc = getattr(imsi_info, "LASTMCC", None)
        country_name, current_rate = await self._resolve_country_and_rate(last_mcc)
        
        return Esim(
            id=data["id"],
            user_id=user.id,
            name=data.get("name"),
            imsi=imsi_info.IMSI if imsi_info else data.get("imsi"),
            iccid=imsi_info.ICCID if imsi_info else data.get("iccid"),
            msisdn=imsi_info.MSISDN if imsi_info else data.get("msisdn"),
            data_limit=data.get("data_limit", 0.0),
            provider_balance=float(imsi_info.BALANCE) if imsi_info and imsi_info.BALANCE is not None else 0.0,
            data_used=max(0.0, data.get("data_limit", 0.0) - (float(imsi_info.BALANCE) if imsi_info and imsi_info.BALANCE is not None else 0.0)),
            activation_code=activation_code,
            country=country_name,
            provider="Vink",
            current_rate=current_rate
        )

    async def activate_esim(self, user: User, esim_id: str, code: str) -> Esim:
        # EXPLANATION: "Activate" in this context implies assigning a real MSISDN to the IMSI
        # so it becomes functional on the network.
        
        # 1. Get eSIM
        esim_data = await self.repository.get_esim(esim_id)
        if not esim_data or esim_data.get("user_id") != user.id:
            raise NotFoundError("eSIM not found")
        
        # 2. Check Provider Status (Idempotency)
        try:
            imsi_info = await self.provider.get_imsi_info(esim_data["imsi"])
            current_msisdn = imsi_info.MSISDN
            # If MSISDN does NOT start with "48", it is ALREADY ACTIVE (Real Number).
            if current_msisdn and not current_msisdn.startswith("48"):
                return await self.get_esim_by_id(user, esim_id)
        except Exception:
            # Fallback to process if check fails
            pass

        # 3. Get available MSISDNs ("Revoked" list on Provider)
        revoked_list = await self.provider.get_revoked_msisdns()
        if not revoked_list:
            raise AppError(503, "No numbers available for activation")
            
        # 4. Pick one
        msisdn_to_assign = revoked_list[0]
        
        # 5. Assign via Provider API
        await self.provider.assign_msisdn(esim_data["imsi"], msisdn_to_assign)
        
        # 6. Update DB (Optional, but good for cache)
        esim_data["msisdn"] = msisdn_to_assign
        await self.repository.save_esim(esim_data)
        
        # 7. Return updated info
        return await self.get_esim_by_id(user, esim_id)

    async def deactivate_esim(self, user: User, esim_id: str):
        # EXPLANATION: "Deactivate" implies revoking the MSISDN, putting it back "on the shelf".
        # The IMSI remains with the user, but has no number.
        
        esim_data = await self.repository.get_esim(esim_id)
        if not esim_data or esim_data.get("user_id") != user.id:
            raise NotFoundError("eSIM not found")

        # Check Provider Status (Idempotency)
        # Avoid "Impossible to revoke technical MSISDN" error
        try:
            imsi_info = await self.provider.get_imsi_info(esim_data["imsi"])
            current_msisdn = imsi_info.MSISDN
            # If starts with "48", it is ALREADY INACTIVE (Technical Number).
            if current_msisdn and current_msisdn.startswith("48"):
                return
        except Exception:
            pass
            
        await self.provider.revoke_msisdn(esim_data["imsi"])
        
        # Update DB
        esim_data["msisdn"] = None
        await self.repository.save_esim(esim_data)

    async def update_esim_settings(self, user: User, esim_id: str, data: UpdateSettingsRequest) -> Esim:
        # Update name in DB
        esim_data = await self.repository.get_esim(esim_id)
        if not esim_data or esim_data.get("user_id") != user.id:
            raise NotFoundError("eSIM not found")
        
        esim_data["name"] = data.name
        await self.repository.save_esim(esim_data)
        
        return await self.get_esim_by_id(user, esim_id)

    async def top_up_esim_by_imsi(self, user: User, imsi: str, amount: float):
        # Internal method called by UserService
        # 1. Verify ownership of this IMSI via DB
        esim_data = await self.repository.get_esim_by_imsi(imsi)
        if not esim_data or esim_data.get("user_id") != user.id:
            raise NotFoundError("IMSIs not found or not owned by user")

        # 2. Request Top-up from Provider
        # Propagate AppError from client (e.g. 400 Insufficient Reseller Funds)
        await self.provider.top_up(imsi, amount)
            
        # 3. Update local record of total data/limit
        esim_data["data_limit"] = esim_data.get("data_limit", 0.0) + amount
        await self.repository.save_esim(esim_data)

    async def get_esim_usage(self, user: User, esim_id: str) -> UsageData:
        # 1. Verify ownership
        esim_data = await self.repository.get_esim(esim_id)
        if not esim_data or esim_data.get("user_id") != user.id:
            raise NotFoundError("eSIM not found")
            
        # 2. Get Real Balance from Provider
        try:
            imsi_info = await self.provider.get_imsi_info(esim_data["imsi"])
            current_balance = imsi_info.BALANCE if imsi_info.BALANCE is not None else 0.0
        except Exception:
            current_balance = 0.0
            
        # 3. Calculate usage
        # Assumption: data_limit in DB is the initial balance or total purchased
        data_limit = esim_data.get("data_limit", 0.0)
        data_used = max(0.0, data_limit - current_balance)
        percentage = (data_used / data_limit * 100) if data_limit > 0 else 0.0

        # Trigger autopay after usage calculation if user has low remaining data
        last_mcc = getattr(imsi_info, "LASTMCC", None) if 'imsi_info' in locals() and imsi_info else None
        country_name, current_rate = await self._resolve_country_and_rate(last_mcc)
        await self._maybe_trigger_autopay(user, esim_data, float(current_balance), current_rate, country_name)
        
        return UsageData(
            esim_id=esim_id,
            period={"start": datetime.datetime.utcnow().strftime("%Y-%m-%d"), "end": datetime.datetime.utcnow().strftime("%Y-%m-%d")},
            usage={
                "data_used_mb": float(data_used), 
                "data_limit_mb": float(data_limit), 
                "data_remaining_mb": float(current_balance), 
                "percentage_used": float(percentage)
            },
            daily_breakdown=[] # Usage history not provided by B2B API currently
        )


    async def purchase_esim(self, user: User) -> Esim:
        # EXPLANATION: Based on user clarification, IMSIs are pre-funded for initial purchase.
        # This endpoint assigns the first available (unallocated) IMSI to the user.
        
        # 1. Fetch all IMSI from Provider ("Master Profile" full list)
        all_imsis_provider = await self.provider.list_imsis()
        
        # 2. Fetch all allocated IMSIs from DB
        allocated = await self.repository.get_all_allocated_imsis()
        
        # 3. Find one unallocated (exclusive allocation logic)
        target_imsi_item = None
        for item in all_imsis_provider:
             if item.imsi not in allocated:
                 target_imsi_item = item
                 break
        
        if not target_imsi_item:
            raise AppError(503, "No available eSIMs in stock")

        # Fetch ICCID to store it
        iccid = None
        try:
             imsi_info = await self.provider.get_imsi_info(target_imsi_item.imsi)
             iccid = imsi_info.ICCID
        except Exception:
             pass
        
        # 4. Allocate (Database Record)
        # Check if we already have a record for this IMSI (e.g. it was unassigned before)
        existing_record = await self.repository.get_esim_by_imsi(target_imsi_item.imsi)
        
        if existing_record:
            # Update existing record
            esim_id = existing_record["id"]
            existing_record["user_id"] = user.id
            existing_record["status"] = "allocated"
            if iccid:
                existing_record["iccid"] = iccid
            existing_record["provider"] = "Vink"
            existing_record["updated_at"] = datetime.datetime.utcnow().isoformat()
            await self.repository.save_esim(existing_record)
        else:
            # Create new record
            esim_id = str(uuid.uuid4())
            data_limit = getattr(target_imsi_item, "balance", 0.0)
            
            # Using placeholders for Activation as before
            activation_code = "UNKNOWN"
            
            esim_record = {
                "id": esim_id,
                "user_id": user.id,
                "imsi": target_imsi_item.imsi,
                "iccid": iccid,
                "msisdn": target_imsi_item.msisdn, 
                "status": "allocated",
                "data_limit": data_limit,
                "name": f"Vink eSIM {target_imsi_item.imsi[-4:]}",
                "provider": "Vink",
                "activation_code": activation_code,
                "created_at": datetime.datetime.utcnow().isoformat()
            }
            await self.repository.save_esim(esim_record)
        
        # 5. Return fully populated eSIM info (consistent with detailed view)
        return await self.get_esim_by_id(user, esim_id)

    async def get_unassigned_esims(self) -> List[Esim]:
        # 1. Fetch all IMSI from Provider
        all_imsis_provider = await self.provider.list_imsis()
        
        # 2. Fetch all allocated IMSIs from DB
        allocated_imsis = await self.repository.get_all_allocated_imsis()
        
        # 3. Fetch all unassigned records from DB (those already known but not allocated)
        db_unassigned = await self.repository.get_unassigned_esims()
        db_unassigned_map = {item["imsi"]: item for item in db_unassigned}
        
        # 4. Filter unallocated and map to Esim objects
        results = []
        for item in all_imsis_provider:
             if item.imsi not in allocated_imsis:
                 db_record = db_unassigned_map.get(item.imsi)
                 if db_record:
                     results.append(Esim(
                         id=db_record["id"],
                         imsi=db_record["imsi"],
                         iccid=db_record.get("iccid"),
                         msisdn=db_record.get("msisdn") or item.msisdn,
                         data_limit=db_record.get("data_limit", 0.0) or item.balance,
                         provider_balance=item.balance,
                         status="free",
                         activation_code=db_record.get("activation_code"),
                         provider="Vink"
                     ))
                 else:
                     results.append(Esim(
                         id=f"free-{item.imsi}",
                         imsi=item.imsi,
                         msisdn=item.msisdn,
                         data_limit=item.balance,
                         provider_balance=item.balance,
                         status="free",
                         provider="Vink"
                     ))
        return results

    async def unassign_imsi_admin(self, imsi: str):
        # 1. Verify existence of this IMSI in DB
        esim_data = await self.repository.get_esim_by_imsi(imsi)
        if not esim_data:
            raise NotFoundError("IMSI mapping not found in database")

        # 2. Nullify relation and update status
        esim_data["user_id"] = None
        esim_data["status"] = "free"
        esim_data["updated_at"] = datetime.datetime.utcnow().isoformat()
        
        await self.repository.save_esim(esim_data)

    async def sync_activation_codes(self) -> dict:
        snapshots = await self.provider.fetch_esim_snapshots()
        updated_count = 0
        total_found = len(snapshots)
        
        for item in snapshots:
            iccid = item.get("iccid")
            activation_code = item.get("activation_code")
            if iccid and activation_code:
                updated = await self.repository.update_activation_code_by_iccid(iccid, activation_code)
                if updated:
                    updated_count += 1
        
        return {
            "total_provider_records": total_found,
            "updated_local_records": updated_count
        }

    async def run_autopay_for_esim_admin(self, esim_id: str) -> dict:
        esim_data = await self.repository.get_esim(esim_id)
        if not esim_data:
            raise NotFoundError("eSIM not found")

        user_id = esim_data.get("user_id")
        if not user_id:
            raise NotFoundError("eSIM is not assigned to a user")

        user = await self.user_repository.get_user(user_id)
        if not user:
            raise NotFoundError("User not found")

        provider_balance = 0.0
        try:
            imsi_info = await self.provider.get_imsi_info(esim_data["imsi"])
            provider_balance = float(imsi_info.BALANCE) if imsi_info.BALANCE is not None else 0.0
        except Exception:
            pass

        before_status = esim_data.get("autopay_last_status")
        last_mcc = getattr(imsi_info, "LASTMCC", None) if 'imsi_info' in locals() and imsi_info else None
        country_name, current_rate = await self._resolve_country_and_rate(last_mcc)
        await self._maybe_trigger_autopay(user, esim_data, provider_balance, current_rate, country_name)
        refreshed = await self.repository.get_esim(esim_id)

        return {
            "esim_id": esim_id,
            "user_id": user_id,
            "provider_balance_mb": provider_balance,
            "autopay_last_status_before": before_status,
            "autopay_last_status_after": refreshed.get("autopay_last_status") if refreshed else None,
            "autopay_last_success_ts": refreshed.get("autopay_last_success_ts") if refreshed else None,
        }

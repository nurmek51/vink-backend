from app.modules.esim.repository import EsimRepository
from app.providers.esim_provider.client import EsimProviderClient
from app.providers.esim_provider.mapper import map_imsi_to_esim
from app.modules.esim.schemas import Esim, Tariff, ActivateRequest, UpdateSettingsRequest, UsageData
from app.modules.users.schemas import User
from app.common.exceptions import NotFoundError, ForbiddenError, AppError
from typing import List
import uuid
import datetime
import json
import os

class EsimService:
    def __init__(self):
        self.repository = EsimRepository()
        self.provider = EsimProviderClient()

    async def get_user_esims(self, user: User) -> List[Esim]:
        # 1. Get allocated IMSIs from DB
        user_esims_data = await self.repository.get_user_esims(user.id)
        
        esims = []
        for data in user_esims_data:
            imsi_info = None
            try:
                # 2. Sync with Provider "Master Profile" data
                imsi_info = await self.provider.get_imsi_info(data["imsi"])
            except Exception:
                # If provider fails, we rely on DB or skip? 
                # Better to show what we have in DB to not block user
                pass

            # QUESTION: input.md does not provide SMDP+ Address or Activation Code (QR data) in ImsiInfo.
            # However, the App requires 'qr' and 'activationCode' to install the eSIM.
            # I am filling these with placeholders. Please clarify source of SMDP data.
            qr_code = data.get("qr_code", "LPA:1$smdp.example.com$UNKNOWN")
            activation_code = data.get("activation_code", "UNKNOWN")

            # Map Provider Balance to Data Used/Remaining logic
            # input.md says 'BALANCE' is available. 
            # We assume 'data_limit' is what user bought (e.g. 5.0 GB or $5.00).
            # If BALANCE is numeric, we store it.
            provider_balance = 0.0
            if imsi_info and imsi_info.BALANCE is not None:
                provider_balance = float(imsi_info.BALANCE)

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
                qr_code=qr_code,
                activation_code=activation_code,
                provider_balance=provider_balance
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

        # QUESTION: Same as above re: QR/SMDP
        qr_code = data.get("qr_code", "LPA:1$smdp.example.com$UNKNOWN")
        activation_code = data.get("activation_code", "UNKNOWN")
        
        return Esim(
            id=data["id"],
            user_id=user.id,
            name=data.get("name"),
            imsi=imsi_info.IMSI,
            iccid=imsi_info.ICCID,
            msisdn=imsi_info.MSISDN,
            data_limit=data.get("data_limit", 0.0),
            qr_code=qr_code,
            activation_code=activation_code
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

    async def get_tariffs(self) -> List[Tariff]:
        # Parse tariffs from alternative_rates.json
        # These represent the different network rates available
        rates_path = os.path.join(os.getcwd(), "alternative_rates.json")
        try:
            with open(rates_path, "r") as f:
                rates_data = json.load(f)
            
            tariffs = []
            for rate in rates_data:
                tariffs.append(
                    Tariff(
                        plmn=rate.get("PLMN"),
                        network_name=rate.get("NetworkName"),
                        country_name=rate.get("CountryName"),
                        data_rate=rate.get("DataRate")
                    )
                )
            return tariffs
        except Exception as e:
            # If rate file is missing or invalid, return empty list
            return []

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
            existing_record["updated_at"] = datetime.datetime.utcnow().isoformat()
            await self.repository.save_esim(existing_record)
        else:
            # Create new record
            esim_id = str(uuid.uuid4())
            data_limit = getattr(target_imsi_item, "balance", 0.0)
            
            # Using placeholders for QR/Activation as before
            qr_code = "LPA:1$smdp.example.com$UNKNOWN"
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
                "qr_code": qr_code,
                "activation_code": activation_code,
                "created_at": datetime.datetime.utcnow().isoformat()
            }
            await self.repository.save_esim(esim_record)
        
        # Return object (map from DB record might be safer)
        final_data = await self.repository.get_esim(esim_id)
        return Esim(**final_data)

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

from app.modules.esim.repository import EsimRepository
from app.providers.esim_provider.client import EsimProviderClient
from app.providers.esim_provider.mapper import map_imsi_to_esim
from app.modules.esim.schemas import Esim, Tariff, ActivateRequest, UpdateSettingsRequest, UsageData
from app.modules.users.schemas import User
from app.common.exceptions import NotFoundError, ForbiddenError, AppError
from typing import List
import uuid
import datetime

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
                name=data.get("name", "Travel eSIM"),
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

    async def top_up_esim(self, user: User, esim_id: str, amount: float) -> Esim:
        # 1. Verify ownership
        esim_data = await self.repository.get_esim(esim_id)
        if not esim_data or esim_data.get("user_id") != user.id:
            raise NotFoundError("eSIM not found")

        # 2. Check User Wallet Balance
        # Note: We deduct from the app's internal balance to pay for the provider top-up
        if user.balance < amount:
            raise AppError(400, "Insufficient funds in your account balance")

        # 3. Request Top-up from Provider (Imsimarket B2B)
        try:
            # input.md: /topup/{imsi}/{amount}
            await self.provider.top_up(esim_data["imsi"], amount)
        except Exception as e:
            from app.common.logging import logger
            logger.error(f"Provider topup failed for {esim_data['imsi']}: {e}")
            raise AppError(503, "Failed to top up eSIM with provider")

        # 4. Deduct from local user wallet
        from app.modules.users.repository import UserRepository
        user_repo = UserRepository()
        new_balance = user.balance - amount
        await user_repo.update_user(user.id, {"balance": new_balance})
        
        # 5. Update local record of total data/limit (optional metadata)
        esim_data["data_limit"] = esim_data.get("data_limit", 0.0) + amount
        await self.repository.save_esim(esim_data)

        # 6. Return updated eSIM info
        return await self.get_esim_by_id(user, esim_id)

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
        # Tariffs are likely internal configuration since input.md is B2B backend.
        # We define what we sell.
        return [
            Tariff(
                id="plan_1gb_us",
                name="1GB USA",
                data_amount=1.0,
                price=5.0,
                currency="USD",
                duration_days=7,
                countries=["US"]
            ),
            Tariff(
                id="plan_5gb_eu",
                name="5GB Europe",
                data_amount=5.0,
                price=15.0,
                currency="USD",
                duration_days=30,
                countries=["FR", "DE", "IT", "ES"]
            )
        ]

    async def purchase_esim(self, user: User, tariff_id: str) -> Esim:
        # 1. Validate Tariff
        # EXPLANATION: Based on user clarification, IMSIs are pre-funded for initial purchase.
        
        # 2. Fetch all IMSI from Provider ("Master Profile" full list)
        all_imsis_provider = await self.provider.list_imsis()
        
        # 3. Fetch all allocated IMSIs from DB
        allocated = await self.repository.get_all_allocated_imsis()
        
        # 4. Find one unallocated (exclusive allocation logic)
        target_imsi_item = None
        for item in all_imsis_provider:
             if item.imsi not in allocated:
                 target_imsi_item = item
                 break
        
        if not target_imsi_item:
            raise AppError(503, "No available eSIMs in stock")
        
        # Get Tariff details for local limit
        # In a real app, fetch from DB. Mocking lookup here based on ID.
        data_limit = 1.0
        if "5gb" in tariff_id:
            data_limit = 5.0
            
        # 5. Allocate (Database Record)
        new_esim_id = str(uuid.uuid4())
        
        # QUESTION: Where is QR code? Using placeholder as per previous notes.
        qr_code = "LPA:1$smdp.example.com$UNKNOWN"
        activation_code = "UNKNOWN"
        
        esim_record = {
            "id": new_esim_id,
            "user_id": user.id,
            "imsi": target_imsi_item.imsi,
            "msisdn": target_imsi_item.msisdn, 
            "status": "created",
            "data_limit": data_limit,
            "name": f"Travel eSIM {target_imsi_item.imsi[-4:]}",
            "qr_code": qr_code,
            "activation_code": activation_code,
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        
        await self.repository.save_esim(esim_record)
        
        return Esim(
            id=new_esim_id,
            user_id=user.id,
            imsi=target_imsi_item.imsi,
            msisdn=target_imsi_item.msisdn,
            data_limit=data_limit,
            status="created",
            qr_code=qr_code,
            activation_code=activation_code
        )

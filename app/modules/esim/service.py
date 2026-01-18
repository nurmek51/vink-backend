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
            # 2. Fetch fresh info from provider for each IMSI
            # This is slow O(N) but precise. For optimization, we could use list_imsis and map.
            try:
                imsi_info = await self.provider.get_imsi_info(data["imsi"])
                
                # Update local DB if needed? Maybe balance?
                # For now just construct response object mixing DB data and Provider data
                esim = Esim(
                    id=data["id"],
                    user_id=user.id,
                    name=data.get("name", "Travel eSIM"),
                    imsi=imsi_info.IMSI,
                    iccid=imsi_info.ICCID,
                    msisdn=imsi_info.MSISDN,
                    data_used=0.0, # Provider doesn't explicitly return Used, only Balance.
                    # Assumption: FUEL/Balance is remaining credit or data?
                    # input.md says "BALANCE: 125.12". Usually currency.
                    # We might need to map this.
                    # user_esim_data might have 'data_limit' from when it was purchased.
                    data_limit=data.get("data_limit", 0.0),
                    is_active=True # user owns it
                )
                esims.append(esim)
            except Exception as e:
                # If provider check fails, return what we have in DB or skip?
                # Better to show partial data or error?
                # We'll continue for robustness, maybe mark as stale
                pass
                
        return esims

    async def get_esim_by_id(self, user: User, esim_id: str) -> Esim:
        # Check DB ownership
        data = await self.repository.get_esim(esim_id)
        if not data or data.get("user_id") != user.id:
            raise NotFoundError("eSIM not found")
            
        # Fetch provider info
        imsi_info = await self.provider.get_imsi_info(data["imsi"])
        
        return Esim(
            id=data["id"],
            user_id=user.id,
            name=data.get("name"),
            imsi=imsi_info.IMSI,
            iccid=imsi_info.ICCID,
            msisdn=imsi_info.MSISDN,
            data_limit=data.get("data_limit", 0.0)
        )

    async def activate_esim(self, user: User, esim_id: str, code: str) -> Esim:
        # Logic: Assign an available MSISDN to the IMSI?
        # input.md says "Assigning MSISDN to IMSI" from Revoked list.
        # This seems to be the "Activation" step equivalent.
        
        # 1. Get eSIM
        esim_data = await self.repository.get_esim(esim_id)
        if not esim_data or esim_data.get("user_id") != user.id:
            raise NotFoundError("eSIM not found")

        # 2. Get available MSISDNs
        revoked_list = await self.provider.get_revoked_msisdns()
        if not revoked_list:
            raise AppError(503, "No numbers available for activation")
            
        msisdn_to_assign = revoked_list[0]
        
        # 3. Assign
        await self.provider.assign_msisdn(esim_data["imsi"], msisdn_to_assign)
        
        # 4. Return updated info
        return await self.get_esim_by_id(user, esim_id)

    async def deactivate_esim(self, user: User, esim_id: str):
        # Logic: Revoke MSISDN
        esim_data = await self.repository.get_esim(esim_id)
        if not esim_data or esim_data.get("user_id") != user.id:
            raise NotFoundError("eSIM not found")
            
        await self.provider.revoke_msisdn(esim_data["imsi"])

    async def update_esim_settings(self, user: User, esim_id: str, data: UpdateSettingsRequest) -> Esim:
        # Update name in DB
        esim_data = await self.repository.get_esim(esim_id)
        if not esim_data or esim_data.get("user_id") != user.id:
            raise NotFoundError("eSIM not found")
        
        esim_data["name"] = data.name
        await self.repository.save_esim(esim_data)
        
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
        # 1. Fetch all IMSI from Provider
        all_imsis_provider = await self.provider.list_imsis()
        
        # 2. Fetch all allocated IMSIs from DB
        allocated = await self.repository.get_all_allocated_imsis()
        
        # 3. Find one unallocated
        target_imsi_item = None
        for item in all_imsis_provider:
             if item.imsi not in allocated:
                 target_imsi_item = item
                 break
        
        if not target_imsi_item:
            raise AppError(503, "No available eSIMs in stock")
            
        # 4. Allocate (Database Record)
        new_esim_id = str(uuid.uuid4())
        esim_record = {
            "id": new_esim_id,
            "user_id": user.id,
            "imsi": target_imsi_item.imsi,
            "msisdn": target_imsi_item.msisdn, 
            "status": "created",
            "data_limit": 1.0, # Determine from tariff_id logic
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        
        await self.repository.save_esim(esim_record)
        
        return Esim(
            id=new_esim_id,
            user_id=user.id,
            imsi=target_imsi_item.imsi,
            msisdn=target_imsi_item.msisdn,
            data_limit=1.0,
            status="created"
        )

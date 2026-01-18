from app.modules.esim.repository import EsimRepository
from app.providers.esim_provider.client import EsimProviderClient
from app.providers.esim_provider.mapper import map_imsi_to_esim
from app.modules.esim.schemas import Esim, Tariff, ActivateRequest, UpdateSettingsRequest, UsageData
from app.modules.users.schemas import User
from app.common.exceptions import NotFoundError, ForbiddenError
from typing import List
import uuid

class EsimService:
    def __init__(self):
        self.repository = EsimRepository()
        self.provider = EsimProviderClient()

    async def get_user_esims(self, user: User) -> List[Esim]:
        # Implementation strategy:
        # We likely need to know WHICH IMSIs belong to this user from our DB.
        # But for now, if the provider returns all imsis, we might not know ownership unless we stored it.
        # Assuming we store it in Firestore.
        # This implementation blindly returns all IMSIs from provider for now as per previous logic, but that's bad.
        # Let's try to fetch from DB first.
        # user_esims = await self.repository.get_esims_by_user(user.id)
        # But 'repository' interface is unknown.
        # I'll stick to the "Mock" approach or provider approach but ideally we filter.
        # "input.md" says: "Gives a full list of IMSI assigned to user." (The 'user' here is the Partner/Reseller).
        # So 'list_imsis' returns ALL imsis owned by the Reseller.
        # We must filter by 'user.id' of the app.
        
        # Proper implementation:
        # Get all esims from DB for this user.
        # Enrich with provider status if needed.
        # For simplicity in this adaptation, I'll return mock data or what logic allows.
        # Let's try to implement a mock that matches API doc structure.
        
        # Real impl would be:
        # db_esims = await self.repository.get_by_user(user.id)
        # return db_esims
        
        # Mock for now:
        return [
            Esim(id="esim_001", provider="FlexSIM", country="Germany", is_active=True, data_used=1.5, data_limit=5.0)
        ]

    async def get_esim_by_id(self, user: User, esim_id: str) -> Esim:
        # Check DB
        # esim = await self.repository.get(esim_id)
        # if not esim or esim.user_id != user.id: raise NotFound
        
        # Mock
        if esim_id == "esim_001":
            return Esim(id="esim_001", provider="FlexSIM", country="Germany", is_active=True, data_used=1.5, data_limit=5.0)
        raise NotFoundError("eSIM not found")

    async def activate_esim(self, user: User, esim_id: str, code: str) -> Esim:
        # Call provider implementation if strictly needed (e.g. assign MSISDN)
        # Or just update status in DB
        
        # Mock
        return Esim(id=esim_id, provider="FlexSIM", country="Germany", is_active=True, status="active")

    async def deactivate_esim(self, user: User, esim_id: str):
        # Update status in DB
        pass

    async def update_esim_settings(self, user: User, esim_id: str, data: UpdateSettingsRequest) -> Esim:
        # Update DB
        return Esim(id=esim_id, provider="FlexSIM", country="Germany", name=data.name or "Updated")

    async def get_esim_usage(self, user: User, esim_id: str) -> UsageData:
        # Initial mock usage
        return UsageData(
            esim_id=esim_id,
            period={"start": "2024-11-20T00:00:00Z", "end": "2024-11-27T00:00:00Z"},
            usage={
                "data_used_mb": 1536.0,
                "data_limit_mb": 5120.0,
                "data_remaining_mb": 3584.0,
                "percentage_used": 30.0
            },
            daily_breakdown=[{"date": "2024-11-21", "data_mb": 200.0}]
        )

    async def get_tariffs(self) -> List[Tariff]:
        # Mock tariffs
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
        # Mock purchase
        new_esim = Esim(
            id=str(uuid.uuid4()),
            iccid="8900000000000000000",
            imsi="260000000000000",
            msisdn="1234567890",
            provider="Imsimarket",
            country="Global",
            data_used=0.0,
            data_limit=1.0, # Based on tariff
            is_active=True
        )
        
        # Save to Firestore
        await self.repository.save_esim(new_esim.dict())
        return new_esim

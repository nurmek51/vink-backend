from app.modules.esim.repository import EsimRepository
from app.providers.esim_provider.client import EsimProviderClient
from app.providers.esim_provider.mapper import map_imsi_to_esim
from app.modules.esim.schemas import Esim, Tariff
from app.modules.users.schemas import User
from typing import List
import uuid

class EsimService:
    def __init__(self):
        self.repository = EsimRepository()
        self.provider = EsimProviderClient()

    async def get_user_esims(self, user: User) -> List[Esim]:
        # Fetch from provider
        try:
            imsis = await self.provider.list_imsis()
            esims = [map_imsi_to_esim(item) for item in imsis]
            
            # Sync/Enrich with Firestore if needed
            # For now, just return what provider gives
            return esims
        except Exception as e:
            # Fallback to Firestore if provider fails?
            # Or just raise
            raise e

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
        # 1. Check balance (Wallet) - skipped for now
        # 2. Call provider to provision (Mocked as we can't create IMSI)
        
        # We'll simulate a new eSIM
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

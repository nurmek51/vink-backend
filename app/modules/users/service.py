from app.modules.users.repository import UserRepository
from app.modules.users.schemas import User, UserUpdate
from app.modules.wallet.service import WalletService
from app.modules.wallet.schemas import BalanceHistoryResponse
from app.common.exceptions import NotFoundError, AppError
from datetime import datetime
from typing import Optional
import uuid

class UserService:
    def __init__(self):
        self.repository = UserRepository()
        self.wallet_service = WalletService()

    async def get_profile(self, user_id: str) -> User:
        user = await self.repository.get_user(user_id)
        if not user:
            raise NotFoundError("User not found")
        return user

    async def get_subscriber_info(self, user: User) -> dict:
        # Use local import to avoid circular dependency if EsimService imports UserService
        from app.modules.esim.service import EsimService
        esim_service = EsimService()
        
        # 1. Get allocated esims
        esims = await esim_service.get_user_esims(user)
        
        # 2. Structure as per API
        return {
            "balance": user.balance,
            "imsi": [
                {
                    "imsi": e.imsi,
                    "iccid": e.iccid,
                    "balance": e.provider_balance,
                    "country": e.country,
                    "iso": "DE", 
                    "brand": e.provider,
                    "rate": e.current_rate or 0.0,
                    "activationCode": e.activation_code
                } for e in esims
            ]
        }

    async def update_profile(self, user_id: str, data: UserUpdate) -> User:
        user = await self.repository.update_user(user_id, data.dict(exclude_unset=True))
        return user

    async def delete_user(self, user_id: str):
        await self.repository.delete_user(user_id)

    async def top_up_balance(self, user_id: str, amount: float, imsi: Optional[str] = None):
        user = await self.get_profile(user_id)
        
        if imsi:
            # Case 1: eSIM Top-Up (Spend User Balance -> Fund Provider eSIM by IMSI)
            if user.balance < amount:
                raise AppError(400, "Insufficient funds in your account balance")
            
            # Delegate to EsimService
            from app.modules.esim.service import EsimService
            esim_service = EsimService()
            await esim_service.top_up_esim_by_imsi(user, imsi, amount)
            
            # Deduct from Wallet
            new_balance = user.balance - amount
            await self.repository.update_user(user_id, {"balance": new_balance})
            
            await self.wallet_service.log_transaction(user_id, "esim_top_up", amount, description=f"Top Up IMSI {imsi}")
            
        else:
            # Case 2: User Wallet Top-Up (Deposit funds)
            new_balance = user.balance + amount
            await self.repository.update_user(user_id, {"balance": new_balance})
            await self.wallet_service.log_transaction(user_id, "top_up", amount, description="Wallet Deposit")

    async def get_balance_history(self, user_id: str) -> BalanceHistoryResponse:
        return await self.wallet_service.get_balance_history(user_id)

    async def verify_email(self, user_id: str, code: str):
        if code == "123456":
            await self.repository.update_user(user_id, {"is_email_verified": True})
        else:
            raise AppError(400, "Invalid code")

    async def verify_phone(self, user_id: str, code: str):
        if code == "123456":
            await self.repository.update_user(user_id, {"is_phone_verified": True})
        else:
            raise AppError(400, "Invalid code")

    async def upload_avatar(self, user_id: str, path: str) -> User:
        return await self.repository.update_user(user_id, {"avatar_url": path})

    async def _log_transaction(self, user_id: str, type: str, amount: float, description: str = ""):
        txn = Transaction(
            id=str(uuid.uuid4()),
            type=type,
            amount=amount,
            currency="USD",
            date=datetime.utcnow(),
            status="completed",
            description=description
        )
        await self.repository.add_transaction(user_id, txn)

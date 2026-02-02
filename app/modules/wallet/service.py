from app.modules.wallet.repository import WalletRepository
from app.modules.wallet.schemas import Transaction, BalanceHistoryResponse
from app.modules.users.schemas import User
from datetime import datetime
import uuid
from typing import Optional

class WalletService:
    def __init__(self):
        self.repository = WalletRepository()

    async def get_balance_history(self, user_id: str) -> BalanceHistoryResponse:
        transactions = await self.repository.get_transactions(user_id)
        
        total_top_up = sum(t.amount for t in transactions if t.type == "top_up")
        total_spent = sum(t.amount for t in transactions if t.type != "top_up")
        
        return BalanceHistoryResponse(
            transactions=transactions,
            total_top_up=total_top_up,
            total_spent=total_spent
        )

    async def log_transaction(self, user_id: str, type: str, amount: float, description: str = ""):
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

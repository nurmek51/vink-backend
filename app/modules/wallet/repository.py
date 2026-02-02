from app.infrastructure.firestore import get_db
from app.modules.wallet.schemas import Transaction
from typing import List
import anyio

class WalletRepository:
    def __init__(self):
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_db()
        return self._db

    def _get_user_ref(self, user_id: str):
        return self.db.collection("users").document(user_id)

    async def add_transaction(self, user_id: str, transaction: Transaction):
        # Subcollection "transactions" under user document
        ref = self._get_user_ref(user_id).collection("transactions").document(transaction.id)
        await anyio.to_thread.run_sync(ref.set, transaction.dict())

    async def get_transactions(self, user_id: str) -> List[Transaction]:
        ref = self._get_user_ref(user_id).collection("transactions").order_by("date", direction="DESCENDING")
        docs = await anyio.to_thread.run_sync(ref.get)
        return [Transaction(**doc.to_dict()) for doc in docs]

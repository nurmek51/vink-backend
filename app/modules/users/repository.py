from app.infrastructure.firestore import get_db
from app.modules.users.schemas import User
from typing import Optional

class UserRepository:
    def __init__(self):
        pass

    @property
    def collection(self):
        return get_db().collection("users")

    async def get_user(self, user_id: str) -> Optional[User]:
        doc = self.collection.document(user_id).get()
        if doc.exists:
            return User(**doc.to_dict())
        return None

    async def update_user(self, user_id: str, data: dict) -> Optional[User]:
        ref = self.collection.document(user_id)
        ref.update(data)
        doc = ref.get()
        return User(**doc.to_dict())

    async def delete_user(self, user_id: str):
        self.collection.document(user_id).delete()

    async def add_transaction(self, user_id: str, transaction: 'Transaction'):
        # Subcollection "transactions" under user document
        self.collection.document(user_id).collection("transactions").document(transaction.id).set(transaction.dict())

    async def get_transactions(self, user_id: str) -> list['Transaction']:
        from app.modules.users.schemas import Transaction
        docs = self.collection.document(user_id).collection("transactions").order_by("date", direction="DESCENDING").stream()
        return [Transaction(**doc.to_dict()) for doc in docs]

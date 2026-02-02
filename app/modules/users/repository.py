from app.infrastructure.firestore import get_db
from app.modules.users.schemas import User
from typing import Optional
import anyio

class UserRepository:
    def __init__(self):
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_db()
        return self._db

    @property
    def collection(self):
        return self.db.collection("users")

    async def get_user(self, user_id: str) -> Optional[User]:
        doc_ref = self.collection.document(user_id)
        doc = await anyio.to_thread.run_sync(doc_ref.get)
        if doc.exists:
            return User(**doc.to_dict())
        return None

    async def update_user(self, user_id: str, data: dict) -> Optional[User]:
        ref = self.collection.document(user_id)
        await anyio.to_thread.run_sync(ref.update, data)
        doc = await anyio.to_thread.run_sync(ref.get)
        return User(**doc.to_dict())

    async def delete_user(self, user_id: str):
        ref = self.collection.document(user_id)
        await anyio.to_thread.run_sync(ref.delete)

from app.infrastructure.firestore import get_db
from app.modules.users.schemas import User, UserCreate
from datetime import datetime
import uuid
import anyio

class AuthRepository:
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

    async def get_user_by_phone(self, phone_number: str):
        query = self.collection.where("phone_number", "==", phone_number).limit(1)
        docs = await anyio.to_thread.run_sync(query.get)
        for doc in docs:
            return User(**doc.to_dict())
        return None

    async def create_user(self, user_create: UserCreate) -> User:
        user_id = str(uuid.uuid4())
        now = datetime.utcnow()
        user_data = user_create.dict()
        user_data.update({
            "id": user_id,
            "created_at": now,
            "last_login_at": now
        })
        
        doc_ref = self.collection.document(user_id)
        await anyio.to_thread.run_sync(doc_ref.set, user_data)
        return User(**user_data)

    async def update_last_login(self, user_id: str):
        doc_ref = self.collection.document(user_id)
        await anyio.to_thread.run_sync(doc_ref.update, {"last_login_at": datetime.utcnow()})

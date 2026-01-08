from app.infrastructure.firestore import get_db
from app.modules.users.schemas import User, UserCreate
from datetime import datetime
import uuid

class AuthRepository:
    def __init__(self):
        self.db = get_db()
        self.collection = self.db.collection("users")

    async def get_user_by_phone(self, phone_number: str):
        # Firestore query
        users_ref = self.collection.where("phone_number", "==", phone_number).limit(1).stream()
        for doc in users_ref:
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
        
        self.collection.document(user_id).set(user_data)
        return User(**user_data)

    async def update_last_login(self, user_id: str):
        self.collection.document(user_id).update({
            "last_login_at": datetime.utcnow()
        })

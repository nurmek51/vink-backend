from app.infrastructure.firestore import get_db
from app.modules.users.schemas import User
from typing import Optional

class UserRepository:
    def __init__(self):
        self.db = get_db()
        self.collection = self.db.collection("users")

    async def get_user(self, user_id: str) -> Optional[User]:
        doc = self.collection.document(user_id).get()
        if doc.exists:
            return User(**doc.to_dict())
        return None

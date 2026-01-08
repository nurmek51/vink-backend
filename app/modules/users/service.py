from app.modules.users.repository import UserRepository
from app.modules.users.schemas import User
from app.common.exceptions import NotFoundError

class UserService:
    def __init__(self):
        self.repository = UserRepository()

    async def get_profile(self, user_id: str) -> User:
        user = await self.repository.get_user(user_id)
        if not user:
            raise NotFoundError("User not found")
        return user

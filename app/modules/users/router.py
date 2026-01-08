from fastapi import APIRouter, Depends
from app.modules.users.service import UserService
from app.modules.users.schemas import User
from app.core.dependencies import get_current_user
from app.common.responses import DataResponse

router = APIRouter()
service = UserService()

@router.get("/subscriber", response_model=DataResponse[User])
async def get_subscriber(current_user: User = Depends(get_current_user)):
    # We can just return current_user since it's populated from token/DB
    # But let's fetch fresh from DB via service to be sure
    user = await service.get_profile(current_user.id)
    return DataResponse(data=user)

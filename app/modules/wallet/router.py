from fastapi import APIRouter, Depends
from app.core.dependencies import require_app_permission
from app.modules.users.schemas import User

router = APIRouter()

@router.get("/wallet")
async def get_wallet(current_user: User = Depends(require_app_permission("vink"))):
    return {"message": "Wallet module"}

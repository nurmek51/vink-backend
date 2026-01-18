from fastapi import APIRouter, Depends, Query
from app.modules.users.service import UserService
from app.modules.users.schemas import (
    User, UserUpdate, BalanceTopUpRequest, BalanceHistoryResponse, 
    ChangePasswordRequest, VerifyRequest, AvatarUploadRequest
)
from app.core.dependencies import get_current_user
from app.common.responses import DataResponse, ResponseBase
from typing import Dict, Any

router = APIRouter()
service = UserService()

@router.get("/subscriber")
async def get_subscriber(current_user: User = Depends(get_current_user)):
    # Returns balance and list of IMSIs
    subscriber_data = await service.get_subscriber_info(current_user)
    return subscriber_data 

@router.get("/user/profile", response_model=DataResponse[User])
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    user = await service.get_profile(current_user.id)
    return DataResponse(data=user)

@router.put("/user/profile", response_model=DataResponse[User])
async def update_user_profile(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user)
):
    updated_user = await service.update_profile(current_user.id, update_data)
    return DataResponse(data=updated_user)

@router.delete("/user/profile")
async def delete_user_profile(current_user: User = Depends(get_current_user)):
    await service.delete_user(current_user.id)
    return ResponseBase()

@router.post("/user/balance/top-up")
async def top_up_balance(
    request: BalanceTopUpRequest,
    current_user: User = Depends(get_current_user)
):
    await service.top_up_balance(current_user.id, request.amount, request.imsi)
    return ResponseBase()

@router.get("/user/balance/history", response_model=DataResponse[BalanceHistoryResponse])
async def get_balance_history(current_user: User = Depends(get_current_user)):
    history = await service.get_balance_history(current_user.id)
    return DataResponse(data=history)

@router.post("/user/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user)
):
    await service.change_password(current_user.id, request.old_password, request.new_password)
    return ResponseBase()

@router.post("/user/verify-email")
async def verify_email(
    request: VerifyRequest,
    current_user: User = Depends(get_current_user)
):
    await service.verify_email(current_user.id, request.verification_code)
    return ResponseBase()

@router.post("/user/verify-phone")
async def verify_phone(
    request: VerifyRequest,
    current_user: User = Depends(get_current_user)
):
    await service.verify_phone(current_user.id, request.verification_code)
    return ResponseBase()

@router.post("/user/avatar", response_model=DataResponse[User])
async def upload_avatar(
    request: AvatarUploadRequest,
    current_user: User = Depends(get_current_user)
):
    user = await service.upload_avatar(current_user.id, request.avatar_path)
    return DataResponse(data=user)

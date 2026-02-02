from fastapi import APIRouter, Depends, status
from app.modules.auth.schemas import (
    OTPRequest, OTPVerify, Token
)
from app.modules.auth.service import AuthService
from app.common.responses import ResponseBase, DataResponse

router = APIRouter()
service = AuthService()

@router.post("/otp/whatsapp", response_model=ResponseBase)
async def send_otp(request: OTPRequest):
    await service.send_otp(request)
    # Return expires_in as per API doc
    return ResponseBase(message="OTP sent successfully", meta={"expires_in": 300})

@router.post("/otp/verify", response_model=DataResponse[Token])
async def verify_otp(request: OTPVerify):
    token = await service.verify_otp(request)
    return DataResponse(data=token, message="Authentication successful")

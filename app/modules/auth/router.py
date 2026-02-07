from fastapi import APIRouter, Depends, status
from app.modules.auth.schemas import (
    OTPRequest, OTPVerify, Token, RefreshTokenRequest
)
from app.modules.auth.service import AuthService
from app.common.responses import ResponseBase, DataResponse

router = APIRouter()
service = AuthService()

@router.post("/otp/sms", response_model=ResponseBase)
async def send_otp_sms(request: OTPRequest):
    await service.send_otp(request, channel="sms")
    return ResponseBase(message="OTP sent successfully", meta={"expires_in": 300})

@router.post("/otp/whatsapp", response_model=ResponseBase)
async def send_otp_whatsapp(request: OTPRequest):
    await service.send_otp(request, channel="whatsapp")
    return ResponseBase(message="OTP sent successfully", meta={"expires_in": 300})

@router.post("/otp/verify", response_model=DataResponse[Token])
async def verify_otp(request: OTPVerify):
    token = await service.verify_otp(request)
    return DataResponse(data=token, message="Authentication successful")

@router.post("/token/refresh", response_model=DataResponse[Token])
async def refresh_token(request: RefreshTokenRequest):
    token = await service.refresh_tokens(request)
    return DataResponse(data=token, message="Token refreshed successfully")

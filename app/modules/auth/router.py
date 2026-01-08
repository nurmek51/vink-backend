from fastapi import APIRouter, Depends, status
from app.modules.auth.schemas import OTPRequest, OTPVerify, Token
from app.modules.auth.service import AuthService
from app.common.responses import ResponseBase, DataResponse

router = APIRouter()
service = AuthService()

@router.post("/otp/whatsapp", response_model=ResponseBase)
async def send_otp(request: OTPRequest):
    await service.send_otp(request)
    return ResponseBase(message="OTP sent successfully")

@router.post("/otp/verify", response_model=DataResponse[Token])
async def verify_otp(request: OTPVerify):
    token = await service.verify_otp(request)
    return DataResponse(data=token, message="Authentication successful")

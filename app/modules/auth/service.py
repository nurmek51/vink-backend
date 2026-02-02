from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import OTPRequest, OTPVerify, Token, LoginConfirmRequest
from app.modules.users.schemas import UserCreate
from app.core.jwt import create_access_token
from app.common.exceptions import UnauthorizedError
from datetime import timedelta

class AuthService:
    def __init__(self):
        self.repository = AuthRepository()

    async def send_otp(self, request: OTPRequest):
        # Mock implementation
        # In real world: Call Twilio/WhatsApp API
        return True

    async def verify_otp(self, verify: OTPVerify) -> Token:
        if verify.otp_code != "123456":
            raise UnauthorizedError("Invalid OTP code")
        
        user = await self.repository.get_user_by_phone(verify.phone_number)
        
        if not user:
            new_user_create = UserCreate(phone_number=verify.phone_number)
            user = await self.repository.create_user(new_user_create)
        else:
            await self.repository.update_last_login(user.id)
            
        token_payload = {
            "sub": user.id,
            "phone": user.phone_number,
            "apps": user.apps_enabled
        }
        
        access_token = create_access_token(
            data=token_payload, 
            expires_delta=timedelta(days=7)
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=3600*24*7,
            user_id=user.id,
            firebase_custom_token="mock_firebase_token"
        )

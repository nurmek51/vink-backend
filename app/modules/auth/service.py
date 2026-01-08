from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import OTPRequest, OTPVerify, Token
from app.modules.users.schemas import UserCreate
from app.core.config import settings
from app.core.jwt import create_access_token
from app.common.exceptions import BadRequestError, UnauthorizedError
from datetime import timedelta

class AuthService:
    def __init__(self):
        self.repository = AuthRepository()

    async def send_otp(self, request: OTPRequest):
        # Mock implementation
        # In real world: Call Twilio API
        if request.phone_number != "+77777777751":
             # For demo purposes, we might allow any number or restrict.
             # The prompt says "Allowed phone: +77777777751"
             pass 
        
        # Logic to store OTP (e.g. in Redis) would go here.
        # For mock, we just return success.
        return True

    async def verify_otp(self, verify: OTPVerify) -> Token:
        # Mock verification
        if verify.otp_code != settings.MOCK_OTP_CODE:
            raise UnauthorizedError("Invalid OTP code")
        
        # Check if user exists
        user = await self.repository.get_user_by_phone(verify.phone_number)
        
        if not user:
            # Register new user
            user_create = UserCreate(phone_number=verify.phone_number)
            user = await self.repository.create_user(user_create)
        else:
            await self.repository.update_last_login(user.id)
            
        # Generate Token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": user.id,
                "phone": user.phone_number,
                "apps": user.apps_enabled
            },
            expires_delta=access_token_expires
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

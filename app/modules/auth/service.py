from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import OTPRequest, OTPVerify, Token, LoginConfirmRequest
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
        # For mock, we just return success.
        return True

    async def verify_otp(self, verify: OTPVerify) -> Token:
        # Mock verification
        if verify.otp_code != "123456": # Mock code
            raise UnauthorizedError("Invalid OTP code")
        
        # Check if user exists or create
        user_id = "user_001"
        
        access_token = create_access_token(data={"sub": user_id}, expires_delta=timedelta(days=7))
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=3600*24*7,
            user_id=user_id,
            firebase_custom_token="mock_firebase_token"
        )
        
    async def login_by_email(self, email: str) -> Token:
        # Mock logic
        user_id = "user_001"
        access_token = create_access_token(data={"sub": user_id}, expires_delta=timedelta(days=7))
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=3600*24*7,
            user_id=user_id,
            firebase_custom_token="mock_firebase_token"
        )

    async def confirm_login(self, endpoint: str, request: LoginConfirmRequest):
        # Mock confirmation
        pass

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

from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import OTPRequest, OTPVerify, Token, RefreshTokenRequest
from app.modules.users.schemas import UserCreate
from app.core.jwt import create_access_token, create_refresh_token, decode_token
from app.common.exceptions import UnauthorizedError, BadRequestError
from app.core.config import settings
from datetime import timedelta
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import firebase_admin
from firebase_admin import auth

class AuthService:
    def __init__(self):
        self.repository = AuthRepository()
        self.twilio_client = None
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            self.twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    async def send_otp(self, request: OTPRequest, channel: str = "sms"):
        """
        Sends OTP via Twilio.
        """
        if not self.twilio_client:
            # If no credentials configured, we can't send real SMS.
            if settings.MOCK_OTP_CODE:
                return True # Assume developer will use mock code
            print("Warning: Twilio credentials not set. OTP not sent.")
            return True

        try:
            self.twilio_client.verify.v2.services(
                settings.TWILIO_SERVICE_SID
            ).verifications.create(to=request.phone_number, channel=channel)
            return True
        except TwilioRestException as e:
            raise BadRequestError(f"Failed to send OTP via {channel}: {e.msg}")

    async def verify_otp(self, verify: OTPVerify) -> Token:
        """
        Verifies the OTP code. Checks against usage of Mock OTP code first,
        then Twilio Verify API.
        """
        # 1. Check Mock OTP
        if verify.otp_code == settings.MOCK_OTP_CODE:
            pass # Skip Twilio check
        else:
            # 2. Check Twilio
            if not self.twilio_client:
                raise UnauthorizedError("Twilio service not configured and invalid mock code used.")

            try:
                verification_check = self.twilio_client.verify.v2.services(
                    settings.TWILIO_SERVICE_SID
                ).verification_checks.create(to=verify.phone_number, code=verify.otp_code)
                
                if verification_check.status != "approved":
                    raise UnauthorizedError("Invalid OTP code")
            except TwilioRestException as e:
                # e.msg usually contains "Invalid code" or similar
                raise UnauthorizedError(f"OTP verification failed: {e.msg}")
        
        # 3. User Logic
        user = await self.repository.get_user_by_phone(verify.phone_number)
        
        if not user:
            new_user_create = UserCreate(phone_number=verify.phone_number)
            user = await self.repository.create_user(new_user_create)
        else:
            await self.repository.update_last_login(user.id)
            
        token_payload = {
            "sub": user.id,
            "phone": user.phone_number,
            "apps": user.apps_enabled if user.apps_enabled else []
        }
        
        access_token = create_access_token(data=token_payload)
        refresh_token = create_refresh_token(data={"sub": user.id})
        
        # Firebase Custom Token
        # Explain: Used to authenticate the user with Firebase Client SDKs (e.g. for direct Firestore access)
        firebase_token = None
        try:
            if firebase_admin._apps:
                firebase_token = auth.create_custom_token(user.id).decode("utf-8")
        except Exception:
            # If firebase is not fully configured, we skip this
            pass
            
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_expires_in=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
            user_id=user.id,
            firebase_custom_token=firebase_token
        )

    async def refresh_tokens(self, request: RefreshTokenRequest) -> Token:
        """
        Refreshes tokens using a valid refresh token.
        """
        payload = decode_token(request.refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid or expired refresh token")
        
        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedError("Invalid token payload")
        
        user = await self.repository.get_user_by_id(user_id)
        if not user:
            raise UnauthorizedError("User not found")
        
        token_payload = {
            "sub": user.id,
            "phone": user.phone_number,
            "apps": user.apps_enabled if user.apps_enabled else []
        }
        
        access_token = create_access_token(token_payload)
        refresh_token = create_refresh_token({"sub": user.id})
        
        # Firebase Custom Token
        firebase_token = None
        try:
            if firebase_admin._apps:
                firebase_token = auth.create_custom_token(user.id).decode("utf-8")
        except Exception:
            pass

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_expires_in=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
            user_id=user.id,
            firebase_custom_token=firebase_token
        )

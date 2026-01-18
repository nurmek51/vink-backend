from pydantic import BaseModel, Field, EmailStr
from typing import Optional

class OTPRequest(BaseModel):
    phone_number: str = Field(..., example="+77777777751")

class OTPVerify(BaseModel):
    phone_number: str = Field(..., example="+77777777751")
    otp_code: str = Field(..., example="123456")

class LoginRequest(BaseModel):
    email: EmailStr

class LoginConfirmRequest(BaseModel):
    token: str
    ticketCode: str

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user_id: Optional[str] = None
    firebase_custom_token: Optional[str] = None

class TokenResponse(BaseModel):
    token: str

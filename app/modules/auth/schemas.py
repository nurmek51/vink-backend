from pydantic import BaseModel, Field

class OTPRequest(BaseModel):
    phone_number: str = Field(..., example="+77777777751")

class OTPVerify(BaseModel):
    phone_number: str = Field(..., example="+77777777751")
    otp_code: str = Field(..., example="123456")

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime
import uuid

class UserBase(BaseModel):
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    preferred_language: Optional[str] = "en"
    preferred_currency: Optional[str] = "USD"

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    preferred_language: Optional[str] = None
    preferred_currency: Optional[str] = None

class VerifyRequest(BaseModel):
    verification_code: str

class  AvatarUploadRequest(BaseModel):
    avatar_path: str

class User(UserBase):
    id: str
    avatar_url: Optional[str] = None
    balance: float = 0.0
    currency: str = "USD"
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_email_verified: bool = False
    is_phone_verified: bool = False
    favorite_countries: List[str] = []
    apps_enabled: List[str] = ["vink", "vink-sim"]
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True

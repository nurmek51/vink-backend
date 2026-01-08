from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid

class UserBase(BaseModel):
    phone_number: str
    apps_enabled: List[str] = ["vink", "vink-sim"]

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: str
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True

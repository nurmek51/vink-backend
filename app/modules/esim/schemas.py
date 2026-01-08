from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class EsimBase(BaseModel):
    name: Optional[str] = "My eSIM"

class Esim(EsimBase):
    id: str
    iccid: str
    imsi: str
    msisdn: Optional[str] = None
    provider: str = "Imsimarket"
    country: Optional[str] = None
    data_used: float = 0.0
    data_limit: float = 0.0
    is_active: bool = True
    expiration_date: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class Tariff(BaseModel):
    id: str
    name: str
    data_amount: float # GB
    price: float
    currency: str
    duration_days: int
    countries: list[str]

class PurchaseRequest(BaseModel):
    tariff_id: str

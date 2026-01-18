from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Tariff(BaseModel):
    id: str
    name: str
    data_amount: float
    price: float
    currency: str
    duration_days: int
    countries: List[str]

class PurchaseRequest(BaseModel):
    tariff_id: str
    payment_data: Optional[dict] = None

class TopUpEsimRequest(BaseModel):
    amount: float

class ActivateRequest(BaseModel):
    activation_code: str

class UpdateSettingsRequest(BaseModel):
    name: Optional[str] = None
    data_alert_threshold: Optional[int] = None

class EsimUsage(BaseModel):
    data_used_mb: float
    data_limit_mb: float
    data_remaining_mb: float
    percentage_used: float

class DailyUsage(BaseModel):
    date: str
    data_mb: float

class UsageData(BaseModel):
    esim_id: str
    period: dict
    usage: EsimUsage
    daily_breakdown: List[DailyUsage]

class Esim(BaseModel):
    id: str
    name: Optional[str] = "Travel eSIM"
    provider: str = "Imsimarket"
    country: Optional[str] = "Global"
    region: Optional[str] = None
    is_active: bool = False
    data_used: float = 0.0
    data_limit: float = 0.0
    activation_date: Optional[datetime] = None
    qr_code: Optional[str] = None
    activation_code: Optional[str] = None
    provider_balance: Optional[float] = 0.0 # Carry numeric balance from provider
    expiration_date: Optional[datetime] = None
    status: str = "active"
    qr_code: Optional[str] = None
    activation_code: Optional[str] = None
    price: float = 0.0
    currency: str = "USD"
    supported_networks: List[str] = []

    # Internal fields mapping to Provider
    iccid: Optional[str] = None
    imsi: Optional[str] = None
    msisdn: Optional[str] = None
    
    # New Field for allocation
    user_id: Optional[str] = None

    class Config:
        from_attributes = True

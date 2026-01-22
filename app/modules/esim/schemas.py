from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Tariff(BaseModel):
    plmn: str = Field(..., description="Public Land Mobile Network identifier, unique code for each operator (e.g., AFGTD)")
    network_name: str = Field(..., description="The name of the mobile network operator (e.g., Roshan Afghanistan)")
    country_name: str = Field(..., description="The country where the network operates (e.g., Afghanistan)")
    data_rate: float = Field(..., description="The cost per MB of data usage in the specified network")

    class Config:
        from_attributes = True

class TopUpEsimRequest(BaseModel):
    amount: float

class ActivateRequest(BaseModel):
    activation_code: str

class UnassignImsiRequest(BaseModel):
    imsi: str

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
    name: Optional[str] = "Vink eSIM"
    user_id: Optional[str] = None
    iccid: Optional[str] = None
    imsi: Optional[str] = None
    msisdn: Optional[str] = None
    is_active: bool = False
    status: Optional[str] = "active"
    country: Optional[str] = "Global"
    provider: str = "Vink"
    current_rate: Optional[float] = None
    data_used: float = 0.0
    data_limit: float = 0.0
    provider_balance: Optional[float] = 0.0
    qr_code: Optional[str] = None
    activation_code: Optional[str] = None

    class Config:
        from_attributes = True

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ImsiTokenResponse(BaseModel):
    access_token: str
    expires_in: int
    token_type: str

class ImsiFuelResponse(BaseModel):
    MVNO_WALLET: str
    MVNO_NAME: str
    MVNO_BALANCE: float
    HISTORY: float
    MONTH_HISTORY: float
    YESTERDAY_HISTORY: float
    TODAY_HISTORY: float
    MVNO_UUID: str
    MVNO_DISCOUNT: str

class ImsiInfoResponse(BaseModel):
    ICCID: str
    IMSI: str
    MSISDN: str
    BALANCE: Optional[float] = Field(None, alias="BALNCE") # Typo in doc "BALNCE"
    LASTUPDATE: Optional[str] = None
    LASTMCC: Optional[int] = None
    LASTMNC: Optional[int] = None

class ImsiListItem(BaseModel):
    imsi: str
    msisdn: str
    balance: float

class ImsiListResponse(BaseModel):
    # The key is dynamic (email), so we might need custom parsing or Dict
    data: Dict[str, List[ImsiListItem]]

class TopUpResponse(BaseModel):
    BEFORE: float
    ADDED: Optional[float] = None
    NOT_ADDED: Optional[float] = None
    AFTER: Optional[float] = None
    FUEL: float
    REASON: Optional[str] = None

class RevokeResponse(BaseModel):
    BEFORE: Dict[str, str]
    AFTER: Dict[str, str]

class AssignResponse(BaseModel):
    BEFORE: Dict[str, str]
    AFTER: Dict[str, str]

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Union

class ImsiTokenResponse(BaseModel):
    access_token: str
    expires_in: int
    token_type: str

class ImsiFuelResponse(BaseModel):
    # ... (fields unchanged)
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
    BALANCE: Optional[float] = None # Support both keys
    BALNCE: Optional[float] = None
    LASTUPDATE: Optional[str] = None
    LASTMCC: Optional[int] = None
    LASTMNC: Optional[int] = None

    @field_validator('BALANCE', mode='before')
    @classmethod
    def check_legacy_balance(cls, v: Any, info: Any) -> Optional[float]:
        # If 'BALANCE' is present, use it. 
        # If not, check 'BALNCE' in values if available (Pydantic validator context might be needed if we want dynamic lookup)
        # But simply defining both optional allows Pydantic to parse what's there.
        # However, to unify them into 'BALANCE':
        return v
    
    def model_post_init(self, __context: Any) -> None:
        # After init, if BALANCE is None but BALNCE is set, copy it
        if self.BALANCE is None and self.BALNCE is not None:
            self.BALANCE = self.BALNCE

    @field_validator('LASTMCC', 'LASTMNC', mode='before')
    @classmethod
    def parse_nullable_int(cls, v: Any) -> Optional[int]:
        if v == "NULL" or v == "null" or v == "":
            return None
        return v

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

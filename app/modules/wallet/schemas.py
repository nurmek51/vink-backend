from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class BalanceTopUpRequest(BaseModel):
    amount: float
    imsi: Optional[str] = None # If provided, funds go to this IMSI

class Transaction(BaseModel):
    id: str
    type: str # top_up, esim_top_up, purchase, etc.
    amount: float
    currency: str
    date: datetime
    status: str
    description: Optional[str] = None

class BalanceHistoryResponse(BaseModel):
    transactions: List[Transaction]
    total_top_up: float
    total_spent: float


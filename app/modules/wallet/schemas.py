from pydantic import BaseModel

class Wallet(BaseModel):
    id: str
    balance: float
    currency: str

from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ---------------------------------------------------------------------------
#  Enums
# ---------------------------------------------------------------------------

class PaymentStatus(str, Enum):
    PENDING = "pending"
    AUTH = "auth"
    CHARGE = "charge"
    REFUND = "refund"
    CANCEL = "cancel"
    FAILED = "failed"


class PaymentType(str, Enum):
    ONE_TIME = "one_time"
    CARD_SAVE = "card_save"
    RECURRENT = "recurrent"


# ---------------------------------------------------------------------------
#  Firestore document model
# ---------------------------------------------------------------------------

class PaymentRecord(BaseModel):
    """Persisted in Firestore under users/{uid}/payments/{payment_id}."""
    id: str
    user_id: str
    invoice_id: str
    amount: float
    currency: str = "KZT"
    description: str = ""
    status: PaymentStatus = PaymentStatus.PENDING
    payment_type: PaymentType = PaymentType.ONE_TIME
    epay_transaction_id: Optional[str] = None
    card_mask: Optional[str] = None
    card_type: Optional[str] = None
    card_id: Optional[str] = None
    reference: Optional[str] = None
    reason: Optional[str] = None
    reason_code: Optional[int] = None
    secret_hash: Optional[str] = None
    checkout_token: Optional[str] = None
    back_link: Optional[str] = None
    failure_back_link: Optional[str] = None
    language: Optional[str] = None
    save_card_requested: bool = False
    target_esim_id: Optional[str] = None
    target_imsi: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
#  API request / response schemas
# ---------------------------------------------------------------------------

class InitiatePaymentRequest(BaseModel):
    """Client requests a payment session (one-time top-up)."""
    amount: Optional[float] = Field(None, gt=0, description="Amount in KZT")
    esim_id: str = Field(..., description="Target eSIM id to top up")
    description: str = Field("Top-up", max_length=125)
    save_card: bool = Field(False, description="If true, initiates card verification/saving flow")
    language: str = Field("rus", pattern="^(rus|kaz|eng)$")

    @model_validator(mode="after")
    def validate_amount_for_non_card_save(self):
        if self.amount is None:
            raise ValueError("amount is required")
        return self


class InitiatePaymentResponse(BaseModel):
    """Returned to the frontend to open the ePay payment page / widget."""
    invoice_id: str
    payment_id: str
    payment_type: PaymentType
    save_card: bool
    checkout_url: str
    auth: dict  # Full token object to pass into halyk.pay()
    payment_page_url: str
    terminal: str
    amount: float
    currency: str
    back_link: str
    failure_back_link: Optional[str] = None
    post_link: str
    failure_post_link: str
    description: str
    language: str


class RecurrentPaymentRequest(BaseModel):
    """Server-side payment using a saved card."""
    esim_id: str = Field(..., description="Target eSIM id to top up")
    card_id: str = Field(..., description="Stored ePay cardId UUID")
    amount: float = Field(..., gt=0)
    description: str = Field("Recurrent charge", max_length=125)
    currency: str = "KZT"


class RecurrentPaymentResponse(BaseModel):
    payment_id: str
    invoice_id: str
    status: str
    epay_transaction_id: Optional[str] = None
    requires_3ds: bool = False
    secure3d: Optional[dict] = None


class SavedCardOut(BaseModel):
    id: str
    card_mask: str
    card_type: Optional[str] = None
    payer_name: Optional[str] = None
    created_date: Optional[str] = None


class PaymentStatusOut(BaseModel):
    payment_id: str
    invoice_id: str
    status: PaymentStatus
    amount: float
    currency: str
    card_mask: Optional[str] = None
    created_at: datetime


class RefundRequest(BaseModel):
    amount: Optional[float] = Field(None, gt=0, description="Partial refund amount. Omit for full.")


class ChargeRequest(BaseModel):
    amount: Optional[float] = Field(None, gt=0, description="Partial charge amount. Omit for full.")


class AdminOperationsQuery(BaseModel):
    start_date: str = Field(..., description="ISO datetime e.g. 2025-01-01T00:00:00Z")
    end_date: str = Field(..., description="ISO datetime")
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)

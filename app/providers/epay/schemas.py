from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class EpayTokenResponse(BaseModel):
    access_token: str
    expires_in: int
    refresh_token: Optional[str] = None
    scope: str
    token_type: str


class EpayPaymentTokenRequest(BaseModel):
    """Request body for obtaining an ePay payment-scoped token."""
    invoice_id: str
    amount: float
    currency: str = "KZT"
    terminal: str
    post_link: Optional[str] = None
    failure_post_link: Optional[str] = None


class EpayPostlinkPayload(BaseModel):
    """Payload received on postLink callback from ePay."""
    id: str
    dateTime: str
    invoiceId: str
    invoiceIdAlt: Optional[str] = None
    amount: float
    currency: str
    terminal: str
    accountId: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    cardMask: Optional[str] = None
    cardType: Optional[str] = None
    issuer: Optional[str] = None
    reference: Optional[str] = None
    secure: Optional[str] = None
    secureDetails: Optional[str] = None
    tokenRecipient: Optional[str] = None
    code: str  # "ok" or "error"
    reason: str
    reasonCode: int
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    ip: Optional[str] = None
    ipCountry: Optional[str] = None
    ipCity: Optional[str] = None
    ipRegion: Optional[str] = None
    ipDistrict: Optional[str] = None
    ipLongitude: Optional[float] = None
    ipLatitude: Optional[float] = None
    cardId: Optional[str] = None
    secret_hash: Optional[str] = None
    approvalCode: Optional[str] = None


class TransactionStatusName(str, Enum):
    AUTH = "AUTH"
    CHARGE = "CHARGE"
    CANCEL = "CANCEL"
    REFUND = "REFUND"


class EpayTransactionDetail(BaseModel):
    id: str
    createdDate: Optional[str] = None
    invoiceID: Optional[str] = None
    amount: Optional[float] = None
    amountBonus: Optional[float] = None
    payoutAmount: Optional[float] = None
    orgAmount: Optional[float] = None
    approvalCode: Optional[str] = None
    data: Optional[str] = None
    currency: Optional[str] = None
    terminal: Optional[str] = None
    terminalID: Optional[str] = None
    accountID: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    cardMask: Optional[str] = None
    cardType: Optional[str] = None
    issuer: Optional[str] = None
    reference: Optional[str] = None
    reason: Optional[str] = None
    reasonCode: Optional[str] = None
    intReference: Optional[str] = None
    secure: Optional[bool] = None
    secureDetails: Optional[str] = None
    statusID: Optional[str] = None
    statusName: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    cardID: Optional[str] = None
    ip: Optional[str] = None
    ipCountry: Optional[str] = None
    ipCity: Optional[str] = None
    ipRegion: Optional[str] = None
    ipDistrict: Optional[str] = None
    ipLatitude: Optional[float] = None
    ipLongitude: Optional[float] = None


class EpayStatusResponse(BaseModel):
    resultCode: str
    resultMessage: str
    transaction: Optional[EpayTransactionDetail] = None


class EpayCardIdPaymentRequest(BaseModel):
    """Server-to-server payment using a saved cardId."""
    amount: float
    currency: str = "KZT"
    name: Optional[str] = None
    terminalId: str
    invoiceId: str
    invoiceIdAlt: Optional[str] = None
    description: str
    accountId: str
    email: Optional[str] = None
    phone: Optional[str] = None
    backLink: str
    failureBackLink: Optional[str] = None
    postLink: str
    failurePostLink: Optional[str] = None
    language: str = "rus"
    paymentType: str = "cardId"
    recurrent: bool = True
    cardId: dict  # {"id": "<card-uuid>"}


class EpayCardIdPaymentResponse(BaseModel):
    id: str
    accountId: Optional[str] = None
    amount: float
    amountBonus: Optional[float] = None
    currency: Optional[str] = None
    description: Optional[str] = None
    invoiceID: Optional[str] = None
    invoiceIdAlt: Optional[str] = None
    language: Optional[str] = None
    phone: Optional[str] = None
    reference: Optional[str] = None
    intReference: Optional[str] = None
    secure3D: Optional[dict] = None
    cardID: Optional[str] = None
    code: Optional[int] = None
    status: Optional[str] = None
    fee: Optional[float] = None


class EpaySavedCard(BaseModel):
    ID: str
    TransactionId: Optional[str] = None
    MerchantID: Optional[str] = None
    CardHash: Optional[str] = None
    CardMask: Optional[str] = None
    PayerName: Optional[str] = None
    Reference: Optional[str] = None
    IntReference: Optional[str] = None
    Token: Optional[str] = None
    Terminal: Optional[str] = None
    CreatedDate: Optional[str] = None
    PaymentAvailable: Optional[bool] = None
    AccountID: Optional[str] = None

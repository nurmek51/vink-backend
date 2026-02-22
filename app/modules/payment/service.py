import uuid
import secrets
from datetime import datetime
from typing import List, Optional
import json

from app.core.config import settings
from app.common.logging import logger
from app.common.exceptions import BadRequestError, NotFoundError, AppError
from app.modules.payment.repository import PaymentRepository
from app.modules.payment.schemas import (
    PaymentRecord,
    PaymentStatus,
    PaymentType,
    InitiatePaymentRequest,
    InitiatePaymentResponse,
    InitiateCardSaveRequest,
    InitiateCardSaveResponse,
    RecurrentPaymentRequest,
    RecurrentPaymentResponse,
    SavedCardOut,
    PaymentStatusOut,
)
from app.modules.users.repository import UserRepository
from app.modules.wallet.service import WalletService
from app.providers.epay.client import EpayClient
from app.providers.epay.schemas import (
    EpayPostlinkPayload,
    EpayCardIdPaymentRequest,
)


class PaymentService:
    """Orchestrates ePay payment flows."""

    def __init__(self) -> None:
        self.repo = PaymentRepository()
        self.user_repo = UserRepository()
        self.wallet_service = WalletService()
        self.epay = EpayClient()

    # ------------------------------------------------------------------
    # 1. One-time payment initiation
    # ------------------------------------------------------------------

    async def initiate_payment(
        self, user_id: str, req: InitiatePaymentRequest
    ) -> InitiatePaymentResponse:
        invoice_id = self._generate_invoice_id()
        payment_id = str(uuid.uuid4())
        secret_hash = secrets.token_urlsafe(24)
        checkout_token = secrets.token_urlsafe(32)
        back_link = req.back_link or settings.EPAY_DEFAULT_BACK_LINK
        failure_back_link = req.failure_back_link or settings.EPAY_DEFAULT_FAILURE_BACK_LINK

        post_link = self._url_join(settings.EPAY_POSTLINK_BASE_URL, "/api/v1/payments/webhook")
        failure_post_link = self._url_join(settings.EPAY_POSTLINK_BASE_URL, "/api/v1/payments/webhook")

        token_resp = await self.epay.obtain_payment_token(
            invoice_id=invoice_id,
            amount=req.amount,
            currency="KZT",
            post_link=post_link,
            failure_post_link=failure_post_link,
            secret_hash=secret_hash,
        )

        record = PaymentRecord(
            id=payment_id,
            user_id=user_id,
            invoice_id=invoice_id,
            amount=req.amount,
            currency="KZT",
            description=req.description,
            status=PaymentStatus.PENDING,
            payment_type=PaymentType.ONE_TIME,
            secret_hash=secret_hash,
            checkout_token=checkout_token,
            back_link=back_link,
            failure_back_link=failure_back_link,
            language=req.language,
        )
        await self.repo.create_payment(record)
        await self.repo.create_invoice_mapping(invoice_id, user_id, payment_id)
        await self.repo.create_checkout_mapping(payment_id, user_id, checkout_token)

        checkout_url = self._url_join(
            settings.EPAY_CHECKOUT_BASE_URL,
            f"/api/v1/payments/checkout/{payment_id}?token={checkout_token}",
        )

        auth_object = {
            "access_token": token_resp.access_token,
            "expires_in": token_resp.expires_in,
            "token_type": token_resp.token_type,
            "scope": token_resp.scope,
        }

        return InitiatePaymentResponse(
            invoice_id=invoice_id,
            payment_id=payment_id,
            checkout_url=checkout_url,
            auth=auth_object,
            payment_page_url=settings.EPAY_PAYMENT_PAGE_JS,
            terminal=self.epay.terminal_id,
            amount=req.amount,
            currency="KZT",
            back_link=back_link,
            failure_back_link=failure_back_link,
            post_link=post_link,
            failure_post_link=failure_post_link,
            description=req.description,
            language=req.language,
        )

    async def get_checkout_html(self, payment_id: str, checkout_token: str) -> str:
        record = await self.repo.resolve_checkout_payment(payment_id, checkout_token)
        if not record:
            raise NotFoundError("Checkout session not found or expired")

        if not record.back_link:
            raise BadRequestError("Payment back_link is missing")

        payment_token = await self.epay.obtain_payment_token(
            invoice_id=record.invoice_id,
            amount=record.amount,
            currency=record.currency,
            post_link=self._url_join(settings.EPAY_POSTLINK_BASE_URL, "/api/v1/payments/webhook"),
            failure_post_link=self._url_join(settings.EPAY_POSTLINK_BASE_URL, "/api/v1/payments/webhook"),
            secret_hash=record.secret_hash,
        )

        auth_json = json.dumps(
            {
                "access_token": payment_token.access_token,
                "expires_in": payment_token.expires_in,
                "token_type": payment_token.token_type,
                "scope": payment_token.scope,
            },
            ensure_ascii=False,
        )
        payment_json = json.dumps(
            {
                "invoiceId": record.invoice_id,
                "backLink": record.back_link,
                "failureBackLink": record.failure_back_link or record.back_link,
                "postLink": self._url_join(settings.EPAY_POSTLINK_BASE_URL, "/api/v1/payments/webhook"),
                "failurePostLink": self._url_join(settings.EPAY_POSTLINK_BASE_URL, "/api/v1/payments/webhook"),
                "language": record.language or "rus",
                "description": record.description,
                "accountId": record.user_id,
                "terminal": self.epay.terminal_id,
                "amount": record.amount,
                "currency": record.currency,
            },
            ensure_ascii=False,
        )

        return f"""
<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>ePay Checkout</title>
    <script src=\"{settings.EPAY_PAYMENT_PAGE_JS}\"></script>
  </head>
  <body>
    <h3>Redirecting to ePay...</h3>
    <p>payment_id: {record.id}</p>
    <p>invoice_id: {record.invoice_id}</p>
    <script>
      const auth = {auth_json};
      const paymentObject = {payment_json};
      paymentObject.auth = auth;
      window.halyk.pay(paymentObject);
    </script>
  </body>
</html>
"""

    # ------------------------------------------------------------------
    # 2. Card save initiation
    # ------------------------------------------------------------------

    async def initiate_card_save(
        self, user_id: str, req: InitiateCardSaveRequest
    ) -> InitiateCardSaveResponse:
        invoice_id = self._generate_invoice_id()
        payment_id = str(uuid.uuid4())

        post_link = f"{settings.EPAY_POSTLINK_BASE_URL}/api/v1/payments/webhook"

        token_resp = await self.epay.obtain_card_save_token(
            invoice_id=invoice_id,
            post_link=post_link,
        )

        record = PaymentRecord(
            id=payment_id,
            user_id=user_id,
            invoice_id=invoice_id,
            amount=0,
            currency="USD",
            description="Card verification",
            status=PaymentStatus.PENDING,
            payment_type=PaymentType.CARD_SAVE,
        )
        await self.repo.create_payment(record)
        await self.repo.create_invoice_mapping(invoice_id, user_id, payment_id)

        auth_object = {
            "access_token": token_resp.access_token,
            "expires_in": token_resp.expires_in,
            "token_type": token_resp.token_type,
            "scope": token_resp.scope,
        }

        return InitiateCardSaveResponse(
            invoice_id=invoice_id,
            auth=auth_object,
            payment_page_url=settings.EPAY_PAYMENT_PAGE_JS,
            terminal=self.epay.terminal_id,
            back_link=req.back_link,
            failure_back_link=req.failure_back_link,
            post_link=post_link,
            language=req.language,
        )

    # ------------------------------------------------------------------
    # 3. Recurrent payment (server-to-server using saved card)
    # ------------------------------------------------------------------

    async def pay_with_saved_card(
        self, user_id: str, req: RecurrentPaymentRequest
    ) -> RecurrentPaymentResponse:
        invoice_id = self._generate_invoice_id()
        payment_id = str(uuid.uuid4())

        user = await self.user_repo.get_user(user_id)
        if not user:
            raise NotFoundError("User not found")

        post_link = f"{settings.EPAY_POSTLINK_BASE_URL}/api/v1/payments/webhook"
        failure_post_link = post_link
        back_link = f"{settings.EPAY_POSTLINK_BASE_URL}/api/v1/payments/status/{payment_id}"

        # Obtain payment token for the recurrent charge
        token_resp = await self.epay.obtain_payment_token(
            invoice_id=invoice_id,
            amount=req.amount,
            currency=req.currency,
            post_link=post_link,
            failure_post_link=failure_post_link,
        )

        epay_req = EpayCardIdPaymentRequest(
            amount=req.amount,
            currency=req.currency,
            name=f"{user.first_name or ''} {user.last_name or ''}".strip() or "Vink User",
            terminalId=self.epay.terminal_id,
            invoiceId=invoice_id,
            description=req.description,
            accountId=user_id,
            email=user.email or "",
            phone=user.phone_number or "",
            backLink=back_link,
            failureBackLink=back_link,
            postLink=post_link,
            failurePostLink=failure_post_link,
            language="rus",
            paymentType="cardId",
            recurrent=True,
            cardId={"id": req.card_id},
        )

        record = PaymentRecord(
            id=payment_id,
            user_id=user_id,
            invoice_id=invoice_id,
            amount=req.amount,
            currency=req.currency,
            description=req.description,
            status=PaymentStatus.PENDING,
            payment_type=PaymentType.RECURRENT,
            card_id=req.card_id,
        )
        await self.repo.create_payment(record)
        await self.repo.create_invoice_mapping(invoice_id, user_id, payment_id)

        epay_resp = await self.epay.pay_with_saved_card(epay_req, token_resp.access_token)

        requires_3ds = epay_resp.status == "3D"
        if epay_resp.status == "AUTH" or epay_resp.status == "CHARGE":
            record.status = PaymentStatus.AUTH
            record.epay_transaction_id = epay_resp.id
            record.reference = epay_resp.reference
            record.card_id = epay_resp.cardID
            await self.repo.update_payment(record)
        elif requires_3ds:
            record.epay_transaction_id = epay_resp.id
            await self.repo.update_payment(record)

        return RecurrentPaymentResponse(
            payment_id=payment_id,
            invoice_id=invoice_id,
            status=epay_resp.status or "UNKNOWN",
            epay_transaction_id=epay_resp.id,
            requires_3ds=requires_3ds,
            secure3d=epay_resp.secure3D if requires_3ds else None,
        )

    # ------------------------------------------------------------------
    # 4. Webhook handler
    # ------------------------------------------------------------------

    async def handle_webhook(self, payload: EpayPostlinkPayload) -> None:
        """Process ePay postLink callback.

        Steps:
        1. Locate internal payment record via invoice_id.
        2. Verify the transaction status with ePay ``check-status`` API.
        3. Update internal record and adjust user balance on success.
        """
        logger.info(
            "Webhook received: invoice=%s code=%s reason=%s",
            payload.invoiceId,
            payload.code,
            payload.reason,
        )

        record = await self.repo.find_payment_by_invoice(payload.invoiceId)
        if not record:
            logger.error("Webhook: no payment record for invoice=%s", payload.invoiceId)
            return

        previous_status = record.status

        # Verify with ePay regardless of callback code
        status_resp = await self.epay.check_transaction_status(payload.invoiceId)

        if status_resp.resultCode == "100" and status_resp.transaction:
            txn = status_resp.transaction
            epay_status = (txn.statusName or "").upper()

            record.epay_transaction_id = txn.id
            record.card_mask = txn.cardMask
            record.card_type = txn.cardType
            record.reference = txn.reference
            record.reason = txn.reason
            record.reason_code = int(txn.reasonCode) if txn.reasonCode else None
            record.card_id = txn.cardID

            if epay_status in ("AUTH", "CHARGE"):
                record.status = PaymentStatus.AUTH if epay_status == "AUTH" else PaymentStatus.CHARGE

                # Credit user balance for one-time / recurrent payments
                if (
                    previous_status not in (PaymentStatus.AUTH, PaymentStatus.CHARGE)
                    and record.payment_type in (PaymentType.ONE_TIME, PaymentType.RECURRENT)
                    and record.amount > 0
                ):
                    await self._credit_user_balance(record.user_id, record.amount)
                    await self.wallet_service.log_transaction(
                        user_id=record.user_id,
                        type="top_up",
                        amount=record.amount,
                        description=f"ePay payment {record.invoice_id}",
                    )
            elif epay_status == "REFUND":
                record.status = PaymentStatus.REFUND
            elif epay_status == "CANCEL":
                record.status = PaymentStatus.CANCEL
            else:
                record.status = PaymentStatus.FAILED
        else:
            record.status = PaymentStatus.FAILED
            record.reason = payload.reason
            record.reason_code = payload.reasonCode

        await self.repo.update_payment(record)
        logger.info("Webhook processed: payment=%s → %s", record.id, record.status)

    # ------------------------------------------------------------------
    # 5. Saved card management
    # ------------------------------------------------------------------

    async def get_saved_cards(self, user_id: str) -> List[SavedCardOut]:
        epay_cards = await self.epay.get_saved_cards(user_id)
        return [
            SavedCardOut(
                id=c.ID,
                card_mask=c.CardMask or "",
                card_type=None,
                payer_name=c.PayerName,
                created_date=c.CreatedDate,
            )
            for c in epay_cards
        ]

    async def deactivate_card(self, user_id: str, card_id: str) -> dict:
        return await self.epay.deactivate_card(card_id)

    # ------------------------------------------------------------------
    # 6. Admin: charge, refund, status
    # ------------------------------------------------------------------

    async def charge_payment(self, payment_id: str, amount: Optional[float] = None) -> PaymentRecord:
        record = await self.repo.get_payment_any_user(payment_id)
        if not record:
            raise NotFoundError("Payment not found")
        if not record.epay_transaction_id:
            raise BadRequestError("No ePay transaction id for this payment")
        await self.epay.charge_payment(record.epay_transaction_id, amount)
        record.status = PaymentStatus.CHARGE
        await self.repo.update_payment(record)
        return record

    async def refund_payment(self, payment_id: str, amount: Optional[float] = None) -> PaymentRecord:
        record = await self.repo.get_payment_any_user(payment_id)
        if not record:
            raise NotFoundError("Payment not found")
        if not record.epay_transaction_id:
            raise BadRequestError("No ePay transaction id for this payment")
        await self.epay.refund_payment(record.epay_transaction_id, amount)
        record.status = PaymentStatus.REFUND
        await self.repo.update_payment(record)
        return record

    async def get_payment_status(self, user_id: str, payment_id: str, sync_with_epay: bool = True) -> PaymentStatusOut:
        record = await self.repo.get_payment(user_id, payment_id)
        if not record:
            raise NotFoundError("Payment not found")

        if sync_with_epay and record.status == PaymentStatus.PENDING:
            record = await self._sync_payment_status_from_epay(record)

        return PaymentStatusOut(
            payment_id=record.id,
            invoice_id=record.invoice_id,
            status=record.status,
            amount=record.amount,
            currency=record.currency,
            card_mask=record.card_mask,
            created_at=record.created_at,
        )

    async def list_payments(self, user_id: str) -> List[PaymentStatusOut]:
        records = await self.repo.list_payments(user_id)
        return [
            PaymentStatusOut(
                payment_id=r.id,
                invoice_id=r.invoice_id,
                status=r.status,
                amount=r.amount,
                currency=r.currency,
                card_mask=r.card_mask,
                created_at=r.created_at,
            )
            for r in records
        ]

    async def verify_payment_from_epay(self, invoice_id: str) -> dict:
        """Directly query ePay for a transaction status."""
        resp = await self.epay.check_transaction_status(invoice_id)
        return resp.dict()

    async def handle_webhook_raw(self, payload: dict) -> None:
        invoice_id = payload.get("invoiceId") or payload.get("invoiceID")
        if not invoice_id:
            logger.error("Webhook payload missing invoiceId: %s", payload)
            return

        code = payload.get("code")
        reason = payload.get("reason", "")
        reason_code = payload.get("reasonCode")
        try:
            reason_code_int = int(reason_code) if reason_code is not None else -1
        except (TypeError, ValueError):
            reason_code_int = -1

        parsed = EpayPostlinkPayload(
            id=str(payload.get("id") or "unknown"),
            dateTime=str(payload.get("dateTime") or datetime.utcnow().isoformat()),
            invoiceId=str(invoice_id),
            amount=float(payload.get("amount") or 0),
            currency=str(payload.get("currency") or "KZT"),
            terminal=str(payload.get("terminal") or settings.EPAY_TERMINAL_ID),
            code=str(code or "unknown"),
            reason=str(reason),
            reasonCode=reason_code_int,
            accountId=payload.get("accountId"),
            description=payload.get("description"),
            language=payload.get("language"),
            cardMask=payload.get("cardMask"),
            cardType=payload.get("cardType"),
            issuer=payload.get("issuer"),
            reference=payload.get("reference"),
            secure=payload.get("secure"),
            secureDetails=payload.get("secureDetails"),
            tokenRecipient=payload.get("tokenRecipient"),
            name=payload.get("name"),
            email=payload.get("email"),
            phone=payload.get("phone"),
            ip=payload.get("ip"),
            ipCountry=payload.get("ipCountry"),
            ipCity=payload.get("ipCity"),
            ipRegion=payload.get("ipRegion"),
            ipDistrict=payload.get("ipDistrict"),
            ipLongitude=payload.get("ipLongitude"),
            ipLatitude=payload.get("ipLatitude"),
            cardId=payload.get("cardId"),
            secret_hash=payload.get("secret_hash"),
            approvalCode=payload.get("approvalCode"),
        )
        await self.handle_webhook(parsed)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _credit_user_balance(self, user_id: str, amount: float) -> None:
        user = await self.user_repo.get_user(user_id)
        if not user:
            logger.error("Cannot credit balance: user %s not found", user_id)
            return
        new_balance = user.balance + amount
        await self.user_repo.update_user(user_id, {"balance": new_balance})
        logger.info("User %s balance updated: %.2f → %.2f", user_id, user.balance, new_balance)

    async def _sync_payment_status_from_epay(self, record: PaymentRecord) -> PaymentRecord:
        status_resp = await self.epay.check_transaction_status(record.invoice_id)
        if status_resp.resultCode != "100" or not status_resp.transaction:
            return record

        txn = status_resp.transaction
        epay_status = (txn.statusName or "").upper()
        previous_status = record.status

        record.epay_transaction_id = txn.id
        record.card_mask = txn.cardMask
        record.card_type = txn.cardType
        record.reference = txn.reference
        record.reason = txn.reason
        record.reason_code = int(txn.reasonCode) if txn.reasonCode else None
        record.card_id = txn.cardID

        if epay_status == "AUTH":
            record.status = PaymentStatus.AUTH
        elif epay_status == "CHARGE":
            record.status = PaymentStatus.CHARGE
        elif epay_status == "REFUND":
            record.status = PaymentStatus.REFUND
        elif epay_status == "CANCEL":
            record.status = PaymentStatus.CANCEL

        if (
            previous_status not in (PaymentStatus.AUTH, PaymentStatus.CHARGE)
            and record.status in (PaymentStatus.AUTH, PaymentStatus.CHARGE)
            and record.payment_type in (PaymentType.ONE_TIME, PaymentType.RECURRENT)
            and record.amount > 0
        ):
            await self._credit_user_balance(record.user_id, record.amount)
            await self.wallet_service.log_transaction(
                user_id=record.user_id,
                type="top_up",
                amount=record.amount,
                description=f"ePay payment {record.invoice_id}",
            )

        await self.repo.update_payment(record)
        return record

    @staticmethod
    def _generate_invoice_id() -> str:
        """Generate a numeric invoice ID (6-15 digits) as required by ePay."""
        import random
        import time

        ts = str(int(time.time()))[-6:]
        rand = str(random.randint(100, 999))
        return ts + rand  # 9 digits, unique enough per second

    @staticmethod
    def _url_join(base: str, path: str) -> str:
        return f"{base.rstrip('/')}/{path.lstrip('/')}"

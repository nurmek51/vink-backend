from typing import List, Optional
import anyio

from app.infrastructure.firestore import get_db
from app.modules.payment.schemas import PaymentRecord, PaymentStatus
from app.common.logging import logger


class PaymentRepository:
    """Firestore persistence for payment records.

    Collection path: ``users/{user_id}/payments/{payment_id}``
    """

    def __init__(self) -> None:
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_db()
        return self._db

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _payments_ref(self, user_id: str):
        return self.db.collection("users").document(user_id).collection("payments")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_payment(self, record: PaymentRecord) -> PaymentRecord:
        ref = self._payments_ref(record.user_id).document(record.id)
        await anyio.to_thread.run_sync(ref.set, record.dict())
        logger.info("Payment record created: %s (user=%s)", record.id, record.user_id)
        return record

    async def get_payment(self, user_id: str, payment_id: str) -> Optional[PaymentRecord]:
        ref = self._payments_ref(user_id).document(payment_id)
        doc = await anyio.to_thread.run_sync(ref.get)
        if doc.exists:
            return PaymentRecord(**doc.to_dict())
        return None

    async def get_payment_by_invoice(self, user_id: str, invoice_id: str) -> Optional[PaymentRecord]:
        """Lookup payment by ePay invoice_id. Uses a query on the subcollection."""
        ref = (
            self._payments_ref(user_id)
            .where("invoice_id", "==", invoice_id)
            .limit(1)
        )
        docs = await anyio.to_thread.run_sync(ref.get)
        for doc in docs:
            return PaymentRecord(**doc.to_dict())
        return None

    async def find_payment_by_invoice(self, invoice_id: str) -> Optional[PaymentRecord]:
        """Global lookup across all users — used by webhook handler.

        Firestore does not support collection-group queries on subcollections
        without a pre-built index, so we also maintain a top-level
        ``payment_invoices/{invoice_id}`` mapping document.
        """
        ref = self.db.collection("payment_invoices").document(invoice_id)
        doc = await anyio.to_thread.run_sync(ref.get)
        if not doc.exists:
            return None
        mapping = doc.to_dict()
        user_id = mapping.get("user_id")
        payment_id = mapping.get("payment_id")
        if not user_id or not payment_id:
            return None
        return await self.get_payment(user_id, payment_id)

    async def update_payment(self, record: PaymentRecord) -> PaymentRecord:
        from datetime import datetime

        record.updated_at = datetime.utcnow()
        ref = self._payments_ref(record.user_id).document(record.id)
        await anyio.to_thread.run_sync(ref.set, record.dict(), {"merge": True})
        logger.info("Payment record updated: %s status=%s", record.id, record.status)
        return record

    async def list_payments(self, user_id: str, limit: int = 50) -> List[PaymentRecord]:
        ref = (
            self._payments_ref(user_id)
            .order_by("created_at", direction="DESCENDING")
            .limit(limit)
        )
        docs = await anyio.to_thread.run_sync(ref.get)
        return [PaymentRecord(**doc.to_dict()) for doc in docs]

    # ------------------------------------------------------------------
    # Invoice → user mapping (for webhook resolution)
    # ------------------------------------------------------------------

    async def create_invoice_mapping(self, invoice_id: str, user_id: str, payment_id: str) -> None:
        ref = self.db.collection("payment_invoices").document(invoice_id)
        await anyio.to_thread.run_sync(
            ref.set,
            {"user_id": user_id, "payment_id": payment_id, "invoice_id": invoice_id},
        )

    async def create_checkout_mapping(self, payment_id: str, user_id: str, checkout_token: str) -> None:
        ref = self.db.collection("payment_checkout").document(payment_id)
        await anyio.to_thread.run_sync(
            ref.set,
            {
                "payment_id": payment_id,
                "user_id": user_id,
                "checkout_token": checkout_token,
            },
        )

    async def resolve_checkout_payment(self, payment_id: str, checkout_token: str) -> Optional[PaymentRecord]:
        ref = self.db.collection("payment_checkout").document(payment_id)
        doc = await anyio.to_thread.run_sync(ref.get)
        if not doc.exists:
            return None
        mapping = doc.to_dict()
        if mapping.get("checkout_token") != checkout_token:
            return None
        user_id = mapping.get("user_id")
        if not user_id:
            return None
        return await self.get_payment(user_id, payment_id)

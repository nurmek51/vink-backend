import httpx
import time
from typing import Optional, List

from app.core.config import settings
from app.common.logging import logger
from app.common.exceptions import AppError
from app.providers.epay.schemas import (
    EpayTokenResponse,
    EpayStatusResponse,
    EpayCardIdPaymentRequest,
    EpayCardIdPaymentResponse,
    EpaySavedCard,
)


class EpayClient:
    """HTTP client for the Halyk ePay gateway.

    Handles:
    - OAuth2 token lifecycle (client_credentials, payment-scoped).
    - Transaction status checks.
    - Server-to-server card-based payments.
    - Saved-card listing and deactivation.
    - Charge (confirm) and refund operations.
    """

    def __init__(self) -> None:
        self.oauth_url: str = settings.EPAY_OAUTH_URL
        self.api_url: str = settings.EPAY_API_URL
        self.client_id: str = settings.EPAY_CLIENT_ID
        self.client_secret: str = settings.EPAY_CLIENT_SECRET
        self.terminal_id: str = settings.EPAY_TERMINAL_ID

        # Cached service-level token (client_credentials, scope=webapi …)
        self._service_token: Optional[str] = None
        self._service_token_expires_at: float = 0.0

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    async def _obtain_service_token(self) -> str:
        """Obtain / refresh a *service* token (client_credentials, broad scope)."""
        if self._service_token and time.time() < (self._service_token_expires_at - 120):
            return self._service_token

        form = {
            "grant_type": "client_credentials",
            "scope": "webapi usermanagement email_send verification statement statistics payment",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        data = await self._post_form(self.oauth_url, form, auth_header=None)
        resp = EpayTokenResponse(**data)
        self._service_token = resp.access_token
        self._service_token_expires_at = time.time() + resp.expires_in
        logger.info("ePay service token obtained (expires_in=%s)", resp.expires_in)
        return self._service_token

    async def obtain_payment_token(
        self,
        invoice_id: str,
        amount: float,
        currency: str = "KZT",
        post_link: Optional[str] = None,
        failure_post_link: Optional[str] = None,
        secret_hash: Optional[str] = None,
    ) -> EpayTokenResponse:
        """Obtain a *payment*-scoped token used by the frontend widget / page."""
        form: dict = {
            "grant_type": "client_credentials",
            "scope": "payment",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "invoiceID": invoice_id,
            "amount": str(amount),
            "currency": currency,
            "terminal": self.terminal_id,
        }
        if post_link:
            form["postLink"] = post_link
        if failure_post_link:
            form["failurePostLink"] = failure_post_link
        if secret_hash:
            form["secret_hash"] = secret_hash

        data = await self._post_form(self.oauth_url, form, auth_header=None)
        resp = EpayTokenResponse(**data)
        logger.info(
            "ePay payment token obtained for invoice=%s amount=%s",
            invoice_id,
            amount,
        )
        return resp

    async def obtain_card_save_token(
        self,
        invoice_id: str,
        post_link: Optional[str] = None,
        failure_post_link: Optional[str] = None,
    ) -> EpayTokenResponse:
        """Token for card-verification / save flow (amount=0, currency=USD)."""
        form: dict = {
            "grant_type": "client_credentials",
            "scope": "webapi usermanagement email_send verification statement statistics payment",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "invoiceID": invoice_id,
            "amount": "0",
            "currency": "USD",
            "terminal": self.terminal_id,
        }
        if post_link:
            form["postLink"] = post_link
        if failure_post_link:
            form["failurePostLink"] = failure_post_link

        data = await self._post_form(self.oauth_url, form, auth_header=None)
        resp = EpayTokenResponse(**data)
        logger.info("ePay card-save token obtained for invoice=%s", invoice_id)
        return resp

    # ------------------------------------------------------------------
    # Transaction status
    # ------------------------------------------------------------------

    async def check_transaction_status(self, invoice_id: str) -> EpayStatusResponse:
        """GET /check-status/payment/transaction/:invoiceid"""
        token = await self._obtain_service_token()
        url = f"{self.api_url}/check-status/payment/transaction/{invoice_id}"
        data = await self._get_json(url, token)
        resp = EpayStatusResponse(**data)
        logger.info(
            "ePay status for invoice=%s → code=%s msg=%s",
            invoice_id,
            resp.resultCode,
            resp.resultMessage,
        )
        return resp

    # ------------------------------------------------------------------
    # Charge / confirm (DMS flow)
    # ------------------------------------------------------------------

    async def charge_payment(
        self, transaction_id: str, amount: Optional[float] = None
    ) -> None:
        """POST /operation/:id/charge — full or partial charge."""
        token = await self._obtain_service_token()
        url = f"{self.api_url}/operation/{transaction_id}/charge"
        body = {}
        if amount is not None:
            body["amount"] = amount
        await self._post_json(url, body or None, token)
        logger.info(
            "ePay charge completed for txn=%s amount=%s",
            transaction_id,
            amount or "full",
        )

    # ------------------------------------------------------------------
    # Refund
    # ------------------------------------------------------------------

    async def refund_payment(
        self, transaction_id: str, amount: Optional[float] = None
    ) -> None:
        """POST /operation/:id/refund — full or partial refund."""
        token = await self._obtain_service_token()
        url = f"{self.api_url}/operation/{transaction_id}/refund"
        body = {}
        if amount is not None:
            body["amount"] = amount
        await self._post_json(url, body or None, token)
        logger.info(
            "ePay refund completed for txn=%s amount=%s",
            transaction_id,
            amount or "full",
        )

    # ------------------------------------------------------------------
    # Saved cards
    # ------------------------------------------------------------------

    async def get_saved_cards(self, account_id: str) -> List[EpaySavedCard]:
        """GET /cards/:accountId"""
        token = await self._obtain_service_token()
        url = f"{self.api_url}/cards/{account_id}"
        data = await self._get_json(url, token)
        if isinstance(data, dict) and "code" in data:
            # ePay returns {"code":1373,"message":"…"} when no cards
            logger.info("ePay no saved cards for account=%s", account_id)
            return []
        return [EpaySavedCard(**item) for item in data]

    async def deactivate_card(self, card_id: str) -> dict:
        """POST /card/deactivate/:cardID"""
        token = await self._obtain_service_token()
        url = f"{self.api_url}/card/deactivate/{card_id}"
        data = await self._post_json(url, None, token)
        logger.info("ePay card deactivated: %s", card_id)
        return data

    # ------------------------------------------------------------------
    # card-based (recurrent) payment
    # ------------------------------------------------------------------

    async def pay_with_saved_card(
        self, request: EpayCardIdPaymentRequest, token: str
    ) -> EpayCardIdPaymentResponse:
        """POST /payments/cards/auth — server-to-server card payment."""
        url = f"{self.api_url}/payments/cards/auth"
        data = await self._post_json(url, request.dict(), token)
        resp = EpayCardIdPaymentResponse(**data)
        logger.info(
            "ePay cardId payment: invoice=%s status=%s",
            request.invoiceId,
            resp.status,
        )
        return resp

    # ------------------------------------------------------------------
    # Low-level HTTP helpers
    # ------------------------------------------------------------------

    async def _post_form(
        self, url: str, form: dict, auth_header: Optional[str]
    ) -> dict:
        headers = {}
        if auth_header:
            headers["Authorization"] = f"Bearer {auth_header}"

        logger.info("ePay POST (form) → %s", url)
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, data=form, headers=headers)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "ePay HTTP error: %s %s — %s",
                    exc.response.status_code,
                    url,
                    exc.response.text[:500],
                )
                raise AppError(502, f"ePay error: {exc.response.status_code}")
            except httpx.HTTPError as exc:
                logger.error("ePay network error: %s — %s", url, exc)
                raise AppError(502, "ePay gateway unreachable")

    async def _post_json(
        self, url: str, body: Optional[dict], token: str
    ) -> dict:
        headers = {"Authorization": f"Bearer {token}"}
        logger.info("ePay POST (json) → %s", url)
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, json=body, headers=headers)
                resp.raise_for_status()
                try:
                    return resp.json()
                except Exception:
                    return {"raw": resp.text}
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "ePay HTTP error: %s %s — %s",
                    exc.response.status_code,
                    url,
                    exc.response.text[:500],
                )
                raise AppError(502, f"ePay error: {exc.response.status_code}")
            except httpx.HTTPError as exc:
                logger.error("ePay network error: %s — %s", url, exc)
                raise AppError(502, "ePay gateway unreachable")

    async def _get_json(self, url: str, token: str) -> dict:
        headers = {"Authorization": f"Bearer {token}"}
        logger.info("ePay GET → %s", url)
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "ePay HTTP error: %s %s — %s",
                    exc.response.status_code,
                    url,
                    exc.response.text[:500],
                )
                raise AppError(502, f"ePay error: {exc.response.status_code}")
            except httpx.HTTPError as exc:
                logger.error("ePay network error: %s — %s", url, exc)
                raise AppError(502, "ePay gateway unreachable")

import httpx
import time
import asyncio
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
        self.oauth_fallback_url: Optional[str] = settings.EPAY_OAUTH_FALLBACK_URL
        self.api_fallback_url: Optional[str] = settings.EPAY_API_FALLBACK_URL
        self.client_id: str = settings.EPAY_CLIENT_ID
        self.client_secret: str = settings.EPAY_CLIENT_SECRET
        self.terminal_id: str = settings.EPAY_TERMINAL_ID
        self.timeout_seconds: float = float(settings.EPAY_HTTP_TIMEOUT_SECONDS)
        self.retries: int = max(1, int(settings.EPAY_HTTP_RETRIES))

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
            "terminal": self.terminal_id,
        }
        data = await self._post_form(self._oauth_urls(), form, auth_header=None)
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

        data = await self._post_form(self._oauth_urls(), form, auth_header=None)
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

        data = await self._post_form(self._oauth_urls(), form, auth_header=None)
        resp = EpayTokenResponse(**data)
        logger.info("ePay card-save token obtained for invoice=%s", invoice_id)
        return resp

    # ------------------------------------------------------------------
    # Transaction status
    # ------------------------------------------------------------------

    async def check_transaction_status(self, invoice_id: str) -> EpayStatusResponse:
        """GET /check-status/payment/transaction/:invoiceid"""
        token = await self._obtain_service_token()
        data = await self._get_json(
            self._api_urls_with_path(f"/check-status/payment/transaction/{invoice_id}"),
            token,
        )
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
        body = {}
        if amount is not None:
            body["amount"] = amount
        await self._post_json(
            self._api_urls_with_path(f"/operation/{transaction_id}/charge"),
            body or None,
            token,
        )
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
        body = {}
        if amount is not None:
            body["amount"] = amount
        await self._post_json(
            self._api_urls_with_path(f"/operation/{transaction_id}/refund"),
            body or None,
            token,
        )
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
        data = await self._get_json(
            self._api_urls_with_path(f"/cards/{account_id}"),
            token,
        )
        if isinstance(data, dict) and "code" in data:
            # ePay returns {"code":1373,"message":"…"} when no cards
            logger.info("ePay no saved cards for account=%s", account_id)
            return []
        return [EpaySavedCard(**item) for item in data]

    async def deactivate_card(self, card_id: str) -> dict:
        """POST /card/deactivate/:cardID"""
        token = await self._obtain_service_token()
        data = await self._post_json(
            self._api_urls_with_path(f"/card/deactivate/{card_id}"),
            None,
            token,
        )
        logger.info("ePay card deactivated: %s", card_id)
        return data

    # ------------------------------------------------------------------
    # card-based (recurrent) payment
    # ------------------------------------------------------------------

    async def pay_with_saved_card(
        self, request: EpayCardIdPaymentRequest, token: str
    ) -> EpayCardIdPaymentResponse:
        """POST /payments/cards/auth — server-to-server card payment."""
        data = await self._post_json(
            self._card_payment_urls(),
            request.dict(),
            token,
        )
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
        self, urls: List[str], form: dict, auth_header: Optional[str]
    ) -> dict:
        headers = {}
        if auth_header:
            headers["Authorization"] = f"Bearer {auth_header}"

        last_error: Optional[Exception] = None
        for url in urls:
            for attempt in range(1, self.retries + 1):
                logger.info("ePay POST (form) → %s (attempt %s/%s)", url, attempt, self.retries)
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    try:
                        resp = await client.post(url, data=form, headers=headers)
                        resp.raise_for_status()
                        try:
                            return resp.json()
                        except Exception as exc:
                            logger.error("ePay invalid JSON response: %s %s", url, str(exc))
                            raise AppError(502, "ePay invalid response")
                    except httpx.HTTPStatusError as exc:
                        status_code = exc.response.status_code
                        logger.error(
                            "ePay HTTP error: %s %s — %s",
                            status_code,
                            url,
                            exc.response.text[:500],
                        )
                        if 400 <= status_code < 500 and status_code not in (408, 429):
                            raise AppError(502, f"ePay error: {status_code}")
                        if attempt < self.retries:
                            await self._sleep_backoff(attempt)
                            continue
                        # try next fallback URL
                        break
                    except httpx.HTTPError as exc:
                        last_error = exc
                        logger.warning("ePay network error: %s — %s", url, exc)
                        if attempt < self.retries:
                            await self._sleep_backoff(attempt)
                    except AppError:
                        raise
                    except Exception as exc:
                        logger.exception("ePay unexpected error: %s %s", url, str(exc))
                        if attempt < self.retries:
                            await self._sleep_backoff(attempt)
                            continue
                        break

        logger.error("ePay gateway unreachable for all oauth URLs: %s", urls)
        raise AppError(502, "ePay gateway unreachable")

    async def _post_json(
        self, urls: List[str], body: Optional[dict], token: str
    ) -> dict:
        headers = {"Authorization": f"Bearer {token}"}
        for url_index, url in enumerate(urls):
            for attempt in range(1, self.retries + 1):
                logger.info("ePay POST (json) → %s (attempt %s/%s)", url, attempt, self.retries)
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    try:
                        resp = await client.post(url, json=body, headers=headers)
                        resp.raise_for_status()
                        try:
                            return resp.json()
                        except Exception:
                            return {"raw": resp.text}
                    except httpx.HTTPStatusError as exc:
                        status_code = exc.response.status_code
                        logger.error(
                            "ePay HTTP error: %s %s — %s",
                            status_code,
                            url,
                            exc.response.text[:500],
                        )
                        # Some ePay endpoints differ by host/base-path.
                        # If current URL returns 404 and we have other candidates,
                        # continue with next URL before failing the request.
                        if status_code == 404 and url_index < (len(urls) - 1):
                            logger.warning("ePay endpoint not found on this base, trying next URL: %s", url)
                            break
                        if 400 <= status_code < 500 and status_code not in (408, 429):
                            raise AppError(502, f"ePay error: {status_code}")
                        if attempt < self.retries:
                            await self._sleep_backoff(attempt)
                            continue
                        break
                    except httpx.HTTPError as exc:
                        logger.warning("ePay network error: %s — %s", url, exc)
                        if attempt < self.retries:
                            await self._sleep_backoff(attempt)
                    except AppError:
                        raise
                    except Exception as exc:
                        logger.exception("ePay unexpected error: %s %s", url, str(exc))
                        if attempt < self.retries:
                            await self._sleep_backoff(attempt)
                            continue
                        break

        logger.error("ePay gateway unreachable for all api URLs: %s", urls)
        raise AppError(502, "ePay gateway unreachable")

    async def _get_json(self, urls: List[str], token: str) -> dict:
        headers = {"Authorization": f"Bearer {token}"}
        for url in urls:
            for attempt in range(1, self.retries + 1):
                logger.info("ePay GET → %s (attempt %s/%s)", url, attempt, self.retries)
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    try:
                        resp = await client.get(url, headers=headers)
                        resp.raise_for_status()
                        try:
                            return resp.json()
                        except Exception as exc:
                            logger.error("ePay invalid JSON response: %s %s", url, str(exc))
                            raise AppError(502, "ePay invalid response")
                    except httpx.HTTPStatusError as exc:
                        status_code = exc.response.status_code
                        logger.error(
                            "ePay HTTP error: %s %s — %s",
                            status_code,
                            url,
                            exc.response.text[:500],
                        )
                        if 400 <= status_code < 500 and status_code not in (408, 429):
                            raise AppError(502, f"ePay error: {status_code}")
                        if attempt < self.retries:
                            await self._sleep_backoff(attempt)
                            continue
                        break
                    except httpx.HTTPError as exc:
                        logger.warning("ePay network error: %s — %s", url, exc)
                        if attempt < self.retries:
                            await self._sleep_backoff(attempt)
                    except AppError:
                        raise
                    except Exception as exc:
                        logger.exception("ePay unexpected error: %s %s", url, str(exc))
                        if attempt < self.retries:
                            await self._sleep_backoff(attempt)
                            continue
                        break

        logger.error("ePay gateway unreachable for all api URLs: %s", urls)
        raise AppError(502, "ePay gateway unreachable")

    def _oauth_urls(self) -> List[str]:
        urls = [self.oauth_url]
        if self.oauth_fallback_url:
            urls.append(self.oauth_fallback_url)
        return urls

    def _api_urls_with_path(self, path: str) -> List[str]:
        bases = [self.api_url]
        if self.api_fallback_url:
            bases.append(self.api_fallback_url)
        return [f"{base.rstrip('/')}/{path.lstrip('/')}" for base in bases]

    def _card_payment_urls(self) -> List[str]:
        """Build candidate URLs for cardId recurrent payment endpoint.

        Different ePay environments may expose `/payments/cards/auth`
        either under base `.../api` or directly on host root.
        """
        path = "/payments/cards/auth"
        bases: List[str] = [self.api_url]
        if self.api_fallback_url:
            bases.append(self.api_fallback_url)

        candidates: List[str] = []
        for base in bases:
            normalized = base.rstrip("/")
            candidates.append(f"{normalized}/{path.lstrip('/')}")

            if normalized.endswith("/api"):
                no_api_base = normalized[:-4]
                if no_api_base:
                    candidates.append(f"{no_api_base.rstrip('/')}/{path.lstrip('/')}")

        # Keep order, remove duplicates
        unique: List[str] = []
        for url in candidates:
            if url not in unique:
                unique.append(url)
        return unique

    @staticmethod
    async def _sleep_backoff(attempt: int) -> None:
        delay = min(3.0, 0.35 * (2 ** (attempt - 1)))
        await asyncio.sleep(delay)

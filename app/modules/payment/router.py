from fastapi import APIRouter, Depends, Request, Query
from typing import List, Optional
from fastapi.responses import HTMLResponse

from app.core.dependencies import require_app_permission, require_admin_api_key
from app.modules.users.schemas import User
from app.modules.payment.schemas import (
    InitiatePaymentRequest,
    InitiatePaymentResponse,
    InitiateCardSaveRequest,
    InitiateCardSaveResponse,
    RecurrentPaymentRequest,
    RecurrentPaymentResponse,
    SavedCardOut,
    PaymentStatusOut,
    RefundRequest,
    ChargeRequest,
)
from app.modules.payment.service import PaymentService
from app.common.responses import DataResponse
from app.common.logging import logger
from app.common.exceptions import AppError

router = APIRouter()


def _get_service() -> PaymentService:
    return PaymentService()


# ======================================================================
# User-facing endpoints (require vink app permission)
# ======================================================================

@router.post(
    "/payments/initiate",
    response_model=DataResponse[InitiatePaymentResponse],
    summary="Create a one-time payment session",
)
async def initiate_payment(
    req: InitiatePaymentRequest,
    current_user: User = Depends(require_app_permission("vink")),
    service: PaymentService = Depends(_get_service),
):
    result = await service.initiate_payment(current_user.id, req)
    return DataResponse(data=result, message="Payment session created")


@router.get(
    "/payments/checkout/{payment_id}",
    response_class=HTMLResponse,
    summary="Public checkout link for ePay payment page",
    include_in_schema=False,
)
async def payment_checkout_page(
    payment_id: str,
    token: str,
    service: PaymentService = Depends(_get_service),
):
    html = await service.get_checkout_html(payment_id, token)
    return HTMLResponse(content=html, status_code=200)


@router.post(
        "/payments/dev/checkout-html",
    summary="DEV: Create payment and return checkout URL",
)
async def initiate_payment_checkout_html(
        req: InitiatePaymentRequest,
        current_user: User = Depends(require_app_permission("vink")),
        service: PaymentService = Depends(_get_service),
):
        """Convenience endpoint for manual QA:

        1) Creates payment session in backend.
        2) Returns an HTML page that auto-runs `halyk.pay(...)`.
        """
        result = await service.initiate_payment(current_user.id, req)
        return DataResponse(
            data={
                "payment_id": result.payment_id,
                "invoice_id": result.invoice_id,
                "checkout_url": result.checkout_url,
                "status_url": f"/api/v1/payments/status/{result.payment_id}",
            },
            message="Open checkout_url in browser/WebView",
        )


@router.post(
    "/payments/card-save",
    response_model=DataResponse[InitiateCardSaveResponse],
    summary="Initiate card-save (verification) session",
)
async def initiate_card_save(
    req: InitiateCardSaveRequest,
    current_user: User = Depends(require_app_permission("vink")),
    service: PaymentService = Depends(_get_service),
):
    result = await service.initiate_card_save(current_user.id, req)
    return DataResponse(data=result, message="Card save session created")


@router.post(
    "/payments/recurrent",
    response_model=DataResponse[RecurrentPaymentResponse],
    summary="Charge a saved card (server-to-server)",
)
async def recurrent_payment(
    req: RecurrentPaymentRequest,
    current_user: User = Depends(require_app_permission("vink")),
    service: PaymentService = Depends(_get_service),
):
    result = await service.pay_with_saved_card(current_user.id, req)
    return DataResponse(data=result, message="Recurrent payment processed")


@router.get(
    "/payments/saved-cards",
    response_model=DataResponse[List[SavedCardOut]],
    summary="List saved cards for current user",
)
async def get_saved_cards(
    current_user: User = Depends(require_app_permission("vink")),
    service: PaymentService = Depends(_get_service),
):
    result = await service.get_saved_cards(current_user.id)
    return DataResponse(data=result)


@router.delete(
    "/payments/saved-cards/{card_id}",
    summary="Deactivate a saved card",
)
async def deactivate_card(
    card_id: str,
    current_user: User = Depends(require_app_permission("vink")),
    service: PaymentService = Depends(_get_service),
):
    await service.deactivate_card(current_user.id, card_id)
    return DataResponse(message="Card deactivated")


@router.get(
    "/payments",
    response_model=DataResponse[List[PaymentStatusOut]],
    summary="List payment history for current user",
)
async def list_payments(
    current_user: User = Depends(require_app_permission("vink")),
    service: PaymentService = Depends(_get_service),
):
    result = await service.list_payments(current_user.id)
    return DataResponse(data=result)


@router.get(
    "/payments/status/{payment_id}",
    response_model=DataResponse[PaymentStatusOut],
    summary="Get status of a specific payment",
)
async def get_payment_status(
    payment_id: str,
    sync: bool = Query(True, description="If true, reconcile pending status with ePay before response"),
    current_user: User = Depends(require_app_permission("vink")),
    service: PaymentService = Depends(_get_service),
):
    result = await service.get_payment_status(current_user.id, payment_id, sync_with_epay=sync)
    return DataResponse(data=result)


# ======================================================================
# Webhook (public — called by ePay servers, no auth)
# ======================================================================

@router.post(
    "/payments/webhook",
    summary="ePay postLink / failurePostLink callback",
    include_in_schema=False,
)
async def epay_webhook(request: Request, service: PaymentService = Depends(_get_service)):
    """Receive ePay webhook notifications.

    This endpoint is called by ePay's servers on payment success or failure.
    It accepts both JSON and form-encoded bodies.
    """
    content_type = request.headers.get("content-type", "")
    logger.info(
        "Webhook request received: content_type=%s ua=%s ip=%s",
        content_type,
        request.headers.get("user-agent"),
        request.client.host if request.client else "unknown",
    )
    try:
        if "application/json" in content_type:
            body = await request.json()
        else:
            form = await request.form()
            body = dict(form)
        logger.info("ePay webhook raw body: %s", body)
        await service.handle_webhook_raw(body)
    except Exception as exc:
        logger.exception("Webhook processing failed: %s", exc)
        # Return 200 to avoid aggressive retries by provider while we inspect logs
        return {"status": "error", "message": "logged"}

    # ePay expects HTTP 200 to acknowledge receipt
    return {"status": "ok"}


# ======================================================================
# Admin / Support endpoints (require admin API key)
# ======================================================================

@router.post(
    "/admin/payments/{payment_id}/charge",
    summary="Confirm (charge) a payment — DMS flow",
)
async def admin_charge_payment(
    payment_id: str,
    body: Optional[ChargeRequest] = None,
    _admin: dict = Depends(require_admin_api_key),
    service: PaymentService = Depends(_get_service),
):
    record = await service.charge_payment(payment_id, body.amount if body else None)
    return DataResponse(data=record.dict(), message="Payment charged")


@router.post(
    "/admin/payments/{payment_id}/refund",
    summary="Refund a payment (full or partial)",
)
async def admin_refund_payment(
    payment_id: str,
    body: Optional[RefundRequest] = None,
    _admin: dict = Depends(require_admin_api_key),
    service: PaymentService = Depends(_get_service),
):
    record = await service.refund_payment(payment_id, body.amount if body else None)
    return DataResponse(data=record.dict(), message="Payment refunded")


@router.get(
    "/admin/payments/verify/{invoice_id}",
    summary="Check ePay transaction status by invoice ID",
)
async def admin_verify_payment(
    invoice_id: str,
    _admin: dict = Depends(require_admin_api_key),
    service: PaymentService = Depends(_get_service),
):
    result = await service.verify_payment_from_epay(invoice_id)
    return DataResponse(data=result, message="Status retrieved from ePay")


@router.get(
    "/admin/payments/health",
    summary="Admin health check for ePay connectivity",
)
async def admin_payments_health(
    _admin: dict = Depends(require_admin_api_key),
    service: PaymentService = Depends(_get_service),
):
    probe_invoice_id = "000000001"
    try:
        probe = await service.verify_payment_from_epay(probe_invoice_id)
        return DataResponse(
            data={
                "admin_auth_mode": _admin.get("mode"),
                "epay_reachable": True,
                "probe_invoice_id": probe_invoice_id,
                "probe_result": {
                    "resultCode": probe.get("resultCode"),
                    "resultMessage": probe.get("resultMessage"),
                },
            },
            message="Health check completed",
        )
    except AppError as exc:
        return DataResponse(
            data={
                "admin_auth_mode": _admin.get("mode"),
                "epay_reachable": False,
                "probe_invoice_id": probe_invoice_id,
                "error": exc.detail,
            },
            message="Health check completed with connectivity issue",
        )

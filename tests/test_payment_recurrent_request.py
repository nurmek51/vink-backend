from pydantic import ValidationError

from app.modules.payment.schemas import RecurrentPaymentRequest


def test_recurrent_request_accepts_imsi():
    request = RecurrentPaymentRequest(
        imsi="260010183697260",
        card_id="card-id-1",
        amount=5,
        description="Subscription",
        currency="USD",
    )

    assert request.imsi == "260010183697260"
    assert request.esim_id is None


def test_recurrent_request_accepts_legacy_esim_id():
    request = RecurrentPaymentRequest(
        esim_id="free-260010183697260",
        card_id="card-id-1",
        amount=5,
        description="Subscription",
        currency="USD",
    )

    assert request.esim_id == "free-260010183697260"
    assert request.imsi is None


def test_recurrent_request_rejects_both_imsi_and_esim_id():
    try:
        RecurrentPaymentRequest(
            imsi="260010183697260",
            esim_id="free-260010183697260",
            card_id="card-id-1",
            amount=5,
            description="Subscription",
            currency="USD",
        )
    except ValidationError as exc:
        assert "Provide either imsi or esim_id, not both" in str(exc)
        return

    raise AssertionError("ValidationError was expected when both imsi and esim_id are provided")


def test_recurrent_request_requires_identifier():
    try:
        RecurrentPaymentRequest(
            card_id="card-id-1",
            amount=5,
            description="Subscription",
            currency="USD",
        )
    except ValidationError as exc:
        assert "Either imsi or esim_id is required" in str(exc)
        return

    raise AssertionError("ValidationError was expected when no identifier is provided")

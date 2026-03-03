from pydantic import ValidationError

from app.modules.payment.schemas import InitiatePaymentRequest


def test_initiate_request_accepts_imsi_topup():
    request = InitiatePaymentRequest(
        amount=5,
        imsi="260010183697260",
        save_card=False,
        language="rus",
    )

    assert request.imsi == "260010183697260"
    assert request.esim_id is None
    assert request.amount == 5


def test_initiate_request_accepts_legacy_esim_id_topup():
    request = InitiatePaymentRequest(
        amount=5,
        esim_id="free-260010183697260",
        save_card=False,
        language="rus",
    )

    assert request.esim_id == "free-260010183697260"
    assert request.imsi is None


def test_initiate_request_rejects_imsi_and_esim_id_together():
    try:
        InitiatePaymentRequest(
            amount=5,
            imsi="260010183697260",
            esim_id="free-260010183697260",
            save_card=False,
            language="rus",
        )
    except ValidationError as exc:
        assert "Provide either imsi or esim_id, not both" in str(exc)
        return

    raise AssertionError("ValidationError was expected when both imsi and esim_id are provided")

import hashlib
import hmac
from urllib.parse import urlencode


def build_vnpay_payment_url(
    base_url: str,
    hash_secret: str,
    params: dict[str, str],
) -> str:
    """
    Build signed VNPAY payment URL.
    """
    sorted_items = sorted((k, v) for k, v in params.items() if v is not None)
    raw_query = urlencode(sorted_items)
    secure_hash = hmac.new(
        hash_secret.encode("utf-8"),
        raw_query.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest()
    return f"{base_url}?{raw_query}&vnp_SecureHash={secure_hash}"


def verify_vnpay_signature(payload: dict, hash_secret: str) -> bool:
    """
    Verify VNPAY callback/webhook signature.
    """
    received_hash = payload.get("vnp_SecureHash")
    if not received_hash:
        return False

    signing_payload = {
        str(k): str(v)
        for k, v in payload.items()
        if k not in {"vnp_SecureHash", "vnp_SecureHashType"} and v is not None
    }
    sorted_items = sorted(signing_payload.items())
    raw_query = urlencode(sorted_items)
    expected_hash = hmac.new(
        hash_secret.encode("utf-8"),
        raw_query.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest()
    return expected_hash.lower() == str(received_hash).lower()

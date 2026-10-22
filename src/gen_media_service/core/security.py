import hashlib
import hmac


def sign_body(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(body: bytes, secret: str, signature: str | None) -> bool:
    if not signature:
        return False
    expected = sign_body(body, secret)
    return hmac.compare_digest(expected, signature)

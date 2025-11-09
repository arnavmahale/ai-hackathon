import hmac
import hashlib
from typing import Optional
from fastapi import HTTPException, status
from .config import GITHUB_WEBHOOK_SECRET


def verify_github_signature(payload: bytes, signature: Optional[str]) -> None:
    if not GITHUB_WEBHOOK_SECRET:
        return
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature")
    sig = signature.split("=", 1)[1]
    digest = hmac.new(GITHUB_WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, digest):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

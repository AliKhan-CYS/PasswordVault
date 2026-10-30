"""
TOTP-based 2FA (RFC 6238), compatible with Google Authenticator, Authy, etc.

The TOTP secret is encrypted with the user's DEK before being stored, so it
is protected by the same master-password/recovery-key scheme as the rest of
the vault.
"""

import io
import hmac
import time
from typing import Optional

import pyotp
import qrcode

from app import db, crypto
from app.auth import Session
from app.branding import APP_NAME


def generate_secret() -> str:
    return pyotp.random_base32()


def make_qr_png_bytes(secret: str, username: str, issuer: str = APP_NAME) -> bytes:
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def matching_step(secret: str, code: str, last_used_step: Optional[int] = None) -> Optional[int]:
    """Time step the code belongs to (allowing +/-1 step of clock drift), or None.
    Steps at or before last_used_step are refused so a code can't be replayed."""
    code = (code or "").strip()
    if len(code) != 6 or not code.isdigit():
        return None
    try:
        totp = pyotp.TOTP(secret)
        current = int(time.time()) // totp.interval
        for step in (current - 1, current, current + 1):
            if last_used_step is not None and step <= last_used_step:
                continue
            if hmac.compare_digest(totp.generate_otp(step), code):
                return step
    except Exception:
        return None
    return None


def verify_code(secret: str, code: str) -> bool:
    return matching_step(secret, code) is not None


def enable_2fa(session: Session, secret: str, confirm_code: str):
    step = matching_step(secret, confirm_code)
    if step is None:
        raise ValueError("That code didn't match. Check your phone and try again.")
    encrypted_secret = crypto.encrypt_str(session.dek, secret)
    db.set_totp(session.user_id, True, encrypted_secret)
    db.set_totp_last_step(session.user_id, step)


def disable_2fa(session: Session):
    db.set_totp(session.user_id, False, None)

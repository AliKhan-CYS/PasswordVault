"""
TOTP-based 2FA (RFC 6238), compatible with Google Authenticator, Authy, etc.

The TOTP secret is encrypted with the user's DEK before being stored, so it
is protected by the same master-password/recovery-key scheme as the rest of
the vault.
"""

import io
import pyotp
import qrcode

from app import db, crypto
from app.auth import Session


def generate_secret() -> str:
    return pyotp.random_base32()


def make_qr_png_bytes(secret: str, username: str, issuer: str = "SecureVaultPM") -> bytes:
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def verify_code(secret: str, code: str) -> bool:
    try:
        return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
    except Exception:
        return False


def enable_2fa(session: Session, secret: str, confirm_code: str):
    if not verify_code(secret, confirm_code):
        raise ValueError("Invalid verification code. 2FA was not enabled.")
    encrypted_secret = crypto.encrypt_str(session.dek, secret)
    db.set_totp(session.user_id, True, encrypted_secret)


def disable_2fa(session: Session):
    db.set_totp(session.user_id, False, None)

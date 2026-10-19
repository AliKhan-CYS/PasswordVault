"""
Recovery file handling.

The recovery key is generated in auth.register_user() and never stored by
the app. This module writes it into an encrypted .svrk file the user keeps
offline, reads it back, and rotates the recovery key.

File format: base64( MAGIC || AES-256-GCM(nonce || ciphertext+tag) ), wrapped
at 64 columns. Opened in a text editor it is unreadable. Note the file key is
built into the app, so this protects against casual viewing and tampering;
the real protection is still keeping the file offline and private.
"""

import base64
import datetime
import hashlib
import json
import textwrap

from cryptography.exceptions import InvalidTag

from app import db, crypto
from app.auth import Session, AuthError

RECOVERY_FILE_EXT = ".svrk"
RECOVERY_FILE_FILTER = "SecureVault Backup Key (*.svrk)"
_MAGIC = b"SVPM-RK2"
_FILE_KEY = hashlib.sha256(b"SecureVaultPM/recovery-file/v2/" + _MAGIC).digest()
_LEGACY_HEADER = "SECUREVAULTPM-RECOVERY-TOKEN-V1"
_MAX_FILE_CHARS = 16_384


def write_recovery_file(path: str, username: str, recovery_key: str):
    payload = json.dumps({
        "username": username,
        "recovery_key": recovery_key,
        "generated_at": datetime.datetime.utcnow().isoformat(),
    }).encode("utf-8")
    blob = _MAGIC + crypto.encrypt(_FILE_KEY, payload, aad=_MAGIC)
    text = "\n".join(textwrap.wrap(base64.b64encode(blob).decode("ascii"), 64))
    with open(path, "w", encoding="ascii") as f:
        f.write(text + "\n")


def _key_fields(data) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("username"), str) \
            or not isinstance(data.get("recovery_key"), str):
        raise AuthError("This is not a SecureVault backup key file.")
    return {"username": data["username"], "recovery_key": data["recovery_key"]}


def read_recovery_file(path: str) -> dict:
    """Returns {"username": ..., "recovery_key": ...}."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read(_MAX_FILE_CHARS + 1).strip()
    if len(content) > _MAX_FILE_CHARS:
        raise AuthError("This is not a SecureVault backup key file.")

    if content.startswith("{"):
        # Plaintext JSON files from v1 of the app.
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict) and data.get("header") == _LEGACY_HEADER:
            return _key_fields(data)
        raise AuthError("This is not a SecureVault backup key file.")

    try:
        blob = base64.b64decode("".join(content.split()), validate=True)
    except ValueError:
        raise AuthError("This is not a SecureVault backup key file.")
    if not blob.startswith(_MAGIC):
        raise AuthError("This is not a SecureVault backup key file.")
    try:
        payload = crypto.decrypt(_FILE_KEY, blob[len(_MAGIC):], aad=_MAGIC)
    except InvalidTag:
        raise AuthError("This backup key file is damaged or has been changed.")
    return _key_fields(json.loads(payload.decode("utf-8")))


def regenerate_recovery_key(session: Session) -> str:
    """Invalidate the old recovery key and issue a new one for the current DEK."""
    recovery_key = crypto.generate_recovery_key()
    rec_params = crypto.KdfParams(salt=crypto.generate_salt())
    wrapped = crypto.wrap_dek(session.dek, crypto.derive_key(recovery_key, rec_params))
    db.update_wrapped_dek_recovery(session.user_id, rec_params.salt, rec_params, wrapped)
    return recovery_key

"""
Backup/recovery token file handling.

The recovery key itself is generated in auth.register_user() (never stored
in plaintext by the app). This module only handles writing it to a
user-chosen file for safekeeping, and regenerating a new recovery key
(invalidating the old one) if the user wants to rotate it.
"""

import json
import datetime

from app import db, crypto
from app.auth import Session, AuthError


RECOVERY_FILE_HEADER = "SECUREVAULTPM-RECOVERY-TOKEN-V1"


def write_recovery_file(path: str, username: str, recovery_key: str):
    payload = {
        "header": RECOVERY_FILE_HEADER,
        "username": username,
        "recovery_key": recovery_key,
        "generated_at": datetime.datetime.utcnow().isoformat(),
        "note": (
            "Keep this file offline and private (USB drive, safe, etc). "
            "Anyone with this file AND your username can reset your master "
            "password and access your vault. SecureVaultPM support cannot "
            "recover your account without it."
        ),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def read_recovery_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("header") != RECOVERY_FILE_HEADER:
        raise AuthError("This does not look like a valid recovery token file.")
    return data


def regenerate_recovery_key(session: Session) -> str:
    """Invalidate the old recovery key and issue a new one for the current DEK."""
    recovery_key = crypto.generate_recovery_key()
    rec_salt = crypto.generate_salt()
    rec_params = crypto.KdfParams(salt=rec_salt)
    kek_recovery = crypto.derive_key(recovery_key, rec_params)
    wrapped_dek_recovery = crypto.wrap_dek(session.dek, kek_recovery)

    with db.get_conn() as conn:
        conn.execute(
            """UPDATE users SET
                recovery_salt=?, recovery_time_cost=?, recovery_memory_cost=?, recovery_parallelism=?,
                wrapped_dek_recovery=?
               WHERE id=?""",
            (
                rec_salt, rec_params.time_cost, rec_params.memory_cost, rec_params.parallelism,
                wrapped_dek_recovery, session.user_id,
            ),
        )
    return recovery_key

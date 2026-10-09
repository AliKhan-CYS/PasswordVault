"""
Authentication: registration, login (with brute-force lockout + optional
TOTP 2FA), master-password change, and recovery-key based account reset.

Nothing here ever stores the master password. The password is only ever
used transiently to derive a key that unwraps (or wraps) the per-user DEK.
"""

import datetime
from dataclasses import dataclass
from typing import Optional

from cryptography.exceptions import InvalidTag

from app import db, crypto

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 2


class AuthError(Exception):
    pass


class AccountLockedError(AuthError):
    pass


class TwoFactorRequiredError(AuthError):
    """Raised when password is correct but a valid TOTP code is still needed."""


@dataclass
class Session:
    user_id: int
    username: str
    dek: bytes  # kept in memory only, never persisted


def register_user(username: str, master_password: str) -> tuple[Session, str]:
    """
    Create a new user. Returns (session, recovery_key). The recovery_key is
    shown to the user exactly once -- the app never stores it in plaintext.
    """
    username = username.strip()
    if not username:
        raise AuthError("Username cannot be empty.")
    if db.get_user_by_username(username):
        raise AuthError("Username already exists.")
    if len(master_password) < 8:
        raise AuthError("Master password must be at least 8 characters.")

    dek = crypto.generate_key()

    pw_salt = crypto.generate_salt()
    pw_params = crypto.KdfParams(salt=pw_salt)
    kek_password = crypto.derive_key(master_password, pw_params)
    wrapped_dek_password = crypto.wrap_dek(dek, kek_password)

    recovery_key = crypto.generate_recovery_key()
    rec_salt = crypto.generate_salt()
    rec_params = crypto.KdfParams(salt=rec_salt)
    kek_recovery = crypto.derive_key(recovery_key, rec_params)
    wrapped_dek_recovery = crypto.wrap_dek(dek, kek_recovery)

    user_id = db.create_user(
        username,
        pw_salt, pw_params, wrapped_dek_password,
        rec_salt, rec_params, wrapped_dek_recovery,
    )

    return Session(user_id=user_id, username=username, dek=dek), recovery_key


def _check_lockout(user: dict):
    locked_until = user.get("locked_until")
    if locked_until:
        if datetime.datetime.utcnow() < datetime.datetime.fromisoformat(locked_until):
            raise AccountLockedError(
                f"Account locked due to too many failed attempts. Try again after {locked_until} UTC."
            )


def login(username: str, master_password: str, totp_code: Optional[str] = None) -> Session:
    user = db.get_user_by_username(username.strip())
    if not user:
        raise AuthError("Invalid username or password.")

    _check_lockout(user)

    pw_params = crypto.KdfParams(
        salt=user["password_salt"],
        time_cost=user["password_time_cost"],
        memory_cost=user["password_memory_cost"],
        parallelism=user["password_parallelism"],
    )
    kek_password = crypto.derive_key(master_password, pw_params)

    try:
        dek = crypto.unwrap_dek(user["wrapped_dek_password"], kek_password)
    except InvalidTag:
        _on_failed_attempt(user)
        raise AuthError("Invalid username or password.")

    if user["totp_enabled"]:
        from app import totp as totp_mod
        secret = crypto.decrypt(dek, user["totp_secret_encrypted"]).decode("utf-8")
        if not totp_code:
            raise TwoFactorRequiredError("TOTP code required.")
        if not totp_mod.verify_code(secret, totp_code):
            _on_failed_attempt(user)
            raise AuthError("Invalid 2FA code.")

    db.reset_failed_attempts(user["id"])
    return Session(user_id=user["id"], username=user["username"], dek=dek)


def _on_failed_attempt(user: dict):
    attempts = user["failed_attempts"] + 1
    locked_until = None
    if attempts >= MAX_FAILED_ATTEMPTS:
        locked_until = (
            datetime.datetime.utcnow() + datetime.timedelta(minutes=LOCKOUT_MINUTES)
        ).isoformat()
        attempts = 0
    db.record_failed_attempt(user["id"], attempts, locked_until)


def change_master_password(session: Session, new_master_password: str):
    if len(new_master_password) < 8:
        raise AuthError("Master password must be at least 8 characters.")
    pw_salt = crypto.generate_salt()
    pw_params = crypto.KdfParams(salt=pw_salt)
    kek_password = crypto.derive_key(new_master_password, pw_params)
    wrapped_dek_password = crypto.wrap_dek(session.dek, kek_password)
    db.update_wrapped_dek_password(session.user_id, pw_salt, pw_params, wrapped_dek_password)


def recover_account(username: str, recovery_key: str, new_master_password: str) -> Session:
    """Reset the master password using the recovery key, unwrapping the
    existing DEK so no vault data is lost."""
    user = db.get_user_by_username(username.strip())
    if not user:
        raise AuthError("Invalid username or recovery key.")
    if len(new_master_password) < 8:
        raise AuthError("Master password must be at least 8 characters.")

    rec_params = crypto.KdfParams(
        salt=user["recovery_salt"],
        time_cost=user["recovery_time_cost"],
        memory_cost=user["recovery_memory_cost"],
        parallelism=user["recovery_parallelism"],
    )
    kek_recovery = crypto.derive_key(recovery_key.strip(), rec_params)

    try:
        dek = crypto.unwrap_dek(user["wrapped_dek_recovery"], kek_recovery)
    except InvalidTag:
        raise AuthError("Invalid username or recovery key.")

    pw_salt = crypto.generate_salt()
    pw_params = crypto.KdfParams(salt=pw_salt)
    kek_password = crypto.derive_key(new_master_password, pw_params)
    wrapped_dek_password = crypto.wrap_dek(dek, kek_password)
    db.update_wrapped_dek_password(user["id"], pw_salt, pw_params, wrapped_dek_password)

    db.reset_failed_attempts(user["id"])
    return Session(user_id=user["id"], username=user["username"], dek=dek)

"""
Authentication: registration, login (with brute-force lockout + optional
TOTP 2FA), master-password change, and recovery-key based account reset.

Nothing here ever stores the master password. The password is only ever
used transiently to derive a key that unwraps (or wraps) the per-user DEK.
"""

import re
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


# ---------- master password policy ----------

def _username_core(text: str) -> str:
    # "Ali_Khan99!" -> "alikhan": catches the username with numbers/symbols bolted on.
    alnum = re.sub(r"[^a-z0-9]", "", text.lower())
    return alnum.strip("0123456789") or alnum


def is_username_based(username: str, password: str) -> bool:
    core = _username_core(username)
    return bool(core) and _username_core(password) == core


PASSWORD_RULES = [
    ("At least 8 characters", lambda u, p: len(p) >= 8),
    ("An uppercase letter (A-Z)", lambda u, p: any(c.isupper() for c in p)),
    ("A number (0-9)", lambda u, p: any(c.isdigit() for c in p)),
    ("A special character (!@#$...)", lambda u, p: any(not c.isalnum() and not c.isspace() for c in p)),
    ("Not your username (or username + numbers)", lambda u, p: bool(p) and not is_username_based(u, p)),
]


def password_rule_results(username: str, password: str) -> list[tuple[str, bool]]:
    return [(label, check(username, password)) for label, check in PASSWORD_RULES]


def validate_master_password(username: str, password: str):
    failed = [label for label, ok in password_rule_results(username, password) if not ok]
    if failed:
        raise AuthError("Master password must have:\n• " + "\n• ".join(failed))


def _kdf_params(user: dict, prefix: str) -> crypto.KdfParams:
    return crypto.KdfParams(
        salt=user[f"{prefix}_salt"],
        time_cost=user[f"{prefix}_time_cost"],
        memory_cost=user[f"{prefix}_memory_cost"],
        parallelism=user[f"{prefix}_parallelism"],
    )


def _wrap_with_new_password(dek: bytes, master_password: str):
    params = crypto.KdfParams(salt=crypto.generate_salt())
    kek = crypto.derive_key(master_password, params)
    return params, crypto.wrap_dek(dek, kek)


def normalize_recovery_key(recovery_key: str) -> str:
    return recovery_key.strip().upper()


# ---------- flows ----------

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
    validate_master_password(username, master_password)

    dek = crypto.generate_key()
    pw_params, wrapped_dek_password = _wrap_with_new_password(dek, master_password)

    recovery_key = crypto.generate_recovery_key()
    rec_params = crypto.KdfParams(salt=crypto.generate_salt())
    wrapped_dek_recovery = crypto.wrap_dek(dek, crypto.derive_key(recovery_key, rec_params))

    user_id = db.create_user(
        username,
        pw_params.salt, pw_params, wrapped_dek_password,
        rec_params.salt, rec_params, wrapped_dek_recovery,
    )
    return Session(user_id=user_id, username=username, dek=dek), recovery_key


def _check_lockout(user: dict):
    locked_until = user.get("locked_until")
    if not locked_until:
        return
    remaining = datetime.datetime.fromisoformat(locked_until) - datetime.datetime.utcnow()
    seconds = int(remaining.total_seconds())
    if seconds > 0:
        wait = f"{seconds // 60} min {seconds % 60} sec" if seconds >= 60 else f"{seconds} seconds"
        raise AccountLockedError(f"Too many failed attempts. Try again in {wait}.")


def login(username: str, master_password: str, totp_code: Optional[str] = None) -> Session:
    user = db.get_user_by_username(username.strip())
    if not user:
        raise AuthError("Invalid username or password.")

    _check_lockout(user)

    kek_password = crypto.derive_key(master_password, _kdf_params(user, "password"))
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


def verify_master_password(session: Session, master_password: str) -> bool:
    user = db.get_user_by_id(session.user_id)
    if not user:
        return False
    try:
        kek = crypto.derive_key(master_password, _kdf_params(user, "password"))
        crypto.unwrap_dek(user["wrapped_dek_password"], kek)
        return True
    except InvalidTag:
        return False


def change_master_password(session: Session, current_password: str, new_master_password: str):
    if not verify_master_password(session, current_password):
        raise AuthError("Current master password is incorrect.")
    if current_password == new_master_password:
        raise AuthError("New password must be different from the current one.")
    validate_master_password(session.username, new_master_password)
    pw_params, wrapped = _wrap_with_new_password(session.dek, new_master_password)
    db.update_wrapped_dek_password(session.user_id, pw_params.salt, pw_params, wrapped)


def recover_account(username: str, recovery_key: str, new_master_password: str) -> Session:
    """Reset the master password using the recovery key, unwrapping the
    existing DEK so no vault data is lost."""
    user = db.get_user_by_username(username.strip())
    if not user:
        raise AuthError("Invalid username or recovery key.")

    kek_recovery = crypto.derive_key(normalize_recovery_key(recovery_key), _kdf_params(user, "recovery"))
    try:
        dek = crypto.unwrap_dek(user["wrapped_dek_recovery"], kek_recovery)
    except InvalidTag:
        raise AuthError("Invalid username or recovery key.")

    validate_master_password(user["username"], new_master_password)
    pw_params, wrapped = _wrap_with_new_password(dek, new_master_password)
    db.update_wrapped_dek_password(user["id"], pw_params.salt, pw_params, wrapped)

    db.reset_failed_attempts(user["id"])
    return Session(user_id=user["id"], username=user["username"], dek=dek)

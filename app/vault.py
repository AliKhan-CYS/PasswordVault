"""
Vault item CRUD, strong password generation, and strength estimation.

Each vault item is serialized to JSON and encrypted as a single opaque
blob under the user's DEK -- title/username/password/notes are never
stored as separate plaintext (or even separately-encrypted) SQL columns,
so there's no plaintext metadata leakage even about field structure.
"""

import json
import secrets
import string
from dataclasses import dataclass, field
from typing import Optional

from zxcvbn import zxcvbn

from app import db, crypto
from app.auth import Session


@dataclass
class VaultItem:
    id: Optional[int]
    title: str
    website_or_app: str
    username: str
    password: str
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""


def _encrypt_item(dek: bytes, item: VaultItem) -> bytes:
    payload = json.dumps({
        "title": item.title,
        "website_or_app": item.website_or_app,
        "username": item.username,
        "password": item.password,
        "notes": item.notes,
    }).encode("utf-8")
    return crypto.encrypt(dek, payload)


def _decrypt_item(dek: bytes, row) -> VaultItem:
    item_id, encrypted_blob, created_at, updated_at = row
    data = json.loads(crypto.decrypt(dek, encrypted_blob).decode("utf-8"))
    return VaultItem(
        id=item_id,
        title=data["title"],
        website_or_app=data["website_or_app"],
        username=data["username"],
        password=data["password"],
        notes=data.get("notes", ""),
        created_at=created_at,
        updated_at=updated_at,
    )


def add_item(session: Session, item: VaultItem) -> int:
    blob = _encrypt_item(session.dek, item)
    return db.add_vault_item(session.user_id, blob)


def update_item(session: Session, item: VaultItem):
    if item.id is None:
        raise ValueError("Item has no id.")
    blob = _encrypt_item(session.dek, item)
    db.update_vault_item(session.user_id, item.id, blob)


def delete_item(session: Session, item_id: int):
    db.delete_vault_item(session.user_id, item_id)


def list_items(session: Session) -> list[VaultItem]:
    rows = db.list_vault_items(session.user_id)
    return [_decrypt_item(session.dek, row) for row in rows]


def filter_items(items: list[VaultItem], query: str) -> list[VaultItem]:
    query = query.strip().lower()
    if not query:
        return list(items)
    return [
        it for it in items
        if query in it.title.lower()
        or query in it.website_or_app.lower()
        or query in it.username.lower()
    ]


# ---------- password generator ----------

AMBIGUOUS = "lI1O0"


def generate_password(length: int = 20, use_upper=True, use_lower=True,
                       use_digits=True, use_symbols=True, avoid_ambiguous=True) -> str:
    pools = []
    if use_lower:
        pools.append(string.ascii_lowercase)
    if use_upper:
        pools.append(string.ascii_uppercase)
    if use_digits:
        pools.append(string.digits)
    if use_symbols:
        pools.append("!@#$%^&*()-_=+[]{};:,.?")

    if not pools:
        raise ValueError("At least one character set must be enabled.")

    alphabet = "".join(pools)
    if avoid_ambiguous:
        alphabet = "".join(c for c in alphabet if c not in AMBIGUOUS)

    # Guarantee at least one char from each selected pool for predictable strength.
    password_chars = [secrets.choice(
        "".join(c for c in pool if not avoid_ambiguous or c not in AMBIGUOUS) or pool
    ) for pool in pools]
    remaining = length - len(password_chars)
    password_chars += [secrets.choice(alphabet) for _ in range(max(remaining, 0))]

    rng = secrets.SystemRandom()
    rng.shuffle(password_chars)
    return "".join(password_chars[:length])


STRENGTH_LABELS = ["Very weak", "Weak", "Fair", "Good", "Strong"]


def password_strength(password: str, user_inputs: Optional[list[str]] = None) -> dict:
    """Returns zxcvbn's analysis: score (0-4), label, crack-time estimate, feedback."""
    if not password:
        return {"score": 0, "label": "", "crack_time_display": "", "feedback": {}}
    # zxcvbn gets slow on very long inputs; 64 chars is plenty for an estimate.
    result = zxcvbn(password[:64], user_inputs=[u for u in (user_inputs or []) if u])
    return {
        "score": result["score"],
        "label": STRENGTH_LABELS[result["score"]],
        "crack_time_display": result["crack_times_display"]["offline_slow_hashing_1e4_per_second"],
        "feedback": result["feedback"],
    }

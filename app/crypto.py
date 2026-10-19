"""
Core cryptography primitives for the password manager.

Key derivation: Argon2id (memory-hard, resists GPU/ASIC brute force).
Encryption: AES-256-GCM (authenticated — tampering/wrong-key is detected,
            not silently decrypted into garbage).

Design: every user has one random 32-byte Data Encryption Key (DEK) that
actually encrypts their vault. The DEK itself is "wrapped" (encrypted) by
two independent keys: one derived from the master password, one derived
from the recovery key. Either one can unwrap the same DEK. This means
recovery works without ever storing the master password, and rotating the
master password never requires re-encrypting the whole vault — only the
wrapped DEK is re-wrapped.
"""

import secrets
import base64
from dataclasses import dataclass

from argon2.low_level import hash_secret_raw, Type
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Argon2id parameters. time_cost/memory_cost chosen to take ~300-500ms on
# typical hardware -- slow enough to blunt offline brute force, fast enough
# to not annoy the user on every unlock.
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536  # 64 MB
ARGON2_PARALLELISM = 4
KEY_LEN = 32  # AES-256
SALT_LEN = 16
NONCE_LEN = 12


@dataclass
class KdfParams:
    salt: bytes
    time_cost: int = ARGON2_TIME_COST
    memory_cost: int = ARGON2_MEMORY_COST
    parallelism: int = ARGON2_PARALLELISM


def generate_salt() -> bytes:
    return secrets.token_bytes(SALT_LEN)


def generate_key(length: int = KEY_LEN) -> bytes:
    return secrets.token_bytes(length)


def derive_key(secret: str, params: KdfParams) -> bytes:
    """Derive a 32-byte key from a password/recovery-phrase using Argon2id."""
    return hash_secret_raw(
        secret=secret.encode("utf-8"),
        salt=params.salt,
        time_cost=params.time_cost,
        memory_cost=params.memory_cost,
        parallelism=params.parallelism,
        hash_len=KEY_LEN,
        type=Type.ID,
    )


def encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    """Encrypt with AES-256-GCM. Returns nonce || ciphertext (tag included)."""
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(NONCE_LEN)
    ciphertext = aesgcm.encrypt(nonce, plaintext, aad)
    return nonce + ciphertext


def decrypt(key: bytes, data: bytes, aad: bytes = b"") -> bytes:
    """Decrypt data produced by encrypt(). Raises InvalidTag on wrong key/tampering."""
    aesgcm = AESGCM(key)
    nonce, ciphertext = data[:NONCE_LEN], data[NONCE_LEN:]
    return aesgcm.decrypt(nonce, ciphertext, aad)


def encrypt_str(key: bytes, plaintext: str, aad: bytes = b"") -> bytes:
    return encrypt(key, plaintext.encode("utf-8"), aad)


def decrypt_str(key: bytes, data: bytes, aad: bytes = b"") -> str:
    return decrypt(key, data, aad).decode("utf-8")


def generate_recovery_key() -> str:
    """
    Generate a high-entropy, human-copyable recovery key, grouped like a
    license key for readability, e.g. XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX.
    32 bytes of randomness (256 bits) base32-encoded.
    """
    raw = secrets.token_bytes(32)
    b32 = base64.b32encode(raw).decode("utf-8").replace("=", "")
    groups = [b32[i:i + 4] for i in range(0, len(b32), 4)]
    return "-".join(groups)


def wrap_dek(dek: bytes, wrapping_key: bytes, aad: bytes = b"") -> bytes:
    return encrypt(wrapping_key, dek, aad)


def unwrap_dek(wrapped: bytes, wrapping_key: bytes, aad: bytes = b"") -> bytes:
    return decrypt(wrapping_key, wrapped, aad)

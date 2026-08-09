"""Hash de senha — Argon2 preferencialmente, bcrypt como alternativa.

Senha em texto puro nunca é gravada. O algoritmo utilizado fica registrado no
próprio hash, permitindo migrar de algoritmo sem invalidar as senhas antigas.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

_PBKDF2_ROUNDS = 260_000

try:  # preferencial
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

    _argon2 = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=2)
except ImportError:  # pragma: no cover
    _argon2 = None

try:  # alternativa
    import bcrypt as _bcrypt
except ImportError:  # pragma: no cover
    _bcrypt = None


def algorithm() -> str:
    if _argon2 is not None:
        return "argon2id"
    if _bcrypt is not None:
        return "bcrypt"
    return "pbkdf2-sha256"


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Senha vazia.")
    if _argon2 is not None:
        return _argon2.hash(password)
    if _bcrypt is not None:
        return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt(rounds=12)).decode()
    return _pbkdf2_hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    if not password or not stored_hash:
        return False
    if stored_hash.startswith("$argon2") and _argon2 is not None:
        try:
            return _argon2.verify(stored_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
    if stored_hash.startswith("$2") and _bcrypt is not None:
        try:
            return _bcrypt.checkpw(password.encode(), stored_hash.encode())
        except ValueError:
            return False
    if stored_hash.startswith("pbkdf2-sha256$"):
        return _pbkdf2_verify(password, stored_hash)
    return False


def needs_rehash(stored_hash: str) -> bool:
    """Indica que a senha deve ser regravada com o algoritmo atual."""
    if _argon2 is not None and stored_hash.startswith("$argon2"):
        try:
            return bool(_argon2.check_needs_rehash(stored_hash))
        except InvalidHashError:  # pragma: no cover
            return True
    if _argon2 is not None:
        return True
    if _bcrypt is not None:
        return not stored_hash.startswith("$2")
    return not stored_hash.startswith("pbkdf2-sha256$")


def _pbkdf2_hash(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return (
        f"pbkdf2-sha256${_PBKDF2_ROUNDS}$"
        f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"
    )


def _pbkdf2_verify(password: str, stored_hash: str) -> bool:
    try:
        _, rounds, salt_b64, digest_b64 = stored_hash.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
    except (ValueError, TypeError):
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds))
    return hmac.compare_digest(candidate, expected)

import hashlib
import secrets
import string

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError

from zxcvbn import zxcvbn

ph = PasswordHasher(
    time_cost=2,
    memory_cost=19456,
    parallelism=1,
    hash_len=32,
    salt_len=16,
    encoding="utf-8",
)


def hash_password(plain: str) -> str:
    return ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        ph.verify(hashed, plain)
        return True
    except (VerificationError, InvalidHashError):
        return False


def validate_password_strength(password: str) -> tuple[bool, str | None]:
    """Returns (valid, error_message_key)."""
    if len(password) < 8:
        return False, "errors.password_too_short"
    if len(password) > 128:
        return False, "errors.password_too_short"

    has_upper = any(c in string.ascii_uppercase for c in password)
    has_lower = any(c in string.ascii_lowercase for c in password)
    has_digit = any(c in string.digits for c in password)

    if not (has_upper and has_lower and has_digit):
        return False, "errors.password_too_weak"

    # zxcvbn has a 72-char limit; truncating is safe — entropy won't decrease with length
    truncated = password[:72]
    result = zxcvbn(truncated)
    # 30 bits entropy = 2^30 guesses = log10(2^30) ≈ 9.03 guesses_log10
    if result["guesses_log10"] < 9.03:
        return False, "errors.password_too_weak"

    return True, None

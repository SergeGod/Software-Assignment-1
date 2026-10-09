"""Password hashing and session tokens, using only the standard library."""

import hashlib
import hmac
import secrets

# scrypt cost settings: about 16 MB of memory and a few milliseconds per hash.
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LENGTH = 64


def hash_password(password: str) -> str:
    """Return 'scrypt$n$r$p$salt$hash', so the settings travel with the hash."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=KEY_LENGTH
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algorithm != "scrypt":
        return False
    expected = bytes.fromhex(digest_hex)
    digest = hashlib.scrypt(
        password.encode(),
        salt=bytes.fromhex(salt_hex),
        n=int(n),
        r=int(r),
        p=int(p),
        dklen=len(expected),
    )
    # Constant-time comparison so response timing leaks nothing about the hash.
    return hmac.compare_digest(digest, expected)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

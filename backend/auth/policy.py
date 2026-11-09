"""Password policy enforcement: length, 72-byte ceiling, email dissimilarity, and common dictionary."""

from __future__ import annotations

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_BYTES = 72

# Bundled list of frequently compromised passwords
COMMON_PASSWORDS: frozenset[str] = frozenset({
    "password",
    "password123",
    "1234567890",
    "123456789012",
    "admin12345",
    "administrator",
    "qwertyuiop",
    "welcome123",
    "letmein123",
    "changeme123",
    "iloveyou123",
    "nexus12345",
    "retailcopilot",
    "consulting123",
})


def validate_password_policy(password: str, email: str | None = None) -> None:
    """Validate password against structural policy rules.
    
    Raises ValueError with a user-facing explanation on violation.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

    pwd_bytes = password.encode("utf-8")
    if len(pwd_bytes) > MAX_PASSWORD_BYTES:
        raise ValueError("Password exceeds maximum length of 72 bytes.")

    if email:
        clean_email = email.strip().lower()
        if password.strip().lower() == clean_email:
            raise ValueError("Password cannot match your email address.")
        email_local = clean_email.split("@")[0]
        if len(email_local) >= 4 and email_local in password.strip().lower():
            raise ValueError("Password cannot contain your email username.")

    if password.strip().lower() in COMMON_PASSWORDS:
        raise ValueError("This password is too common. Please choose a more unique phrase.")

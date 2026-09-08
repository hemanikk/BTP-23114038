"""
email_utils.py
--------------
Shared, low-level email parsing utilities.

These helpers are intentionally kept simple and side-effect-free so they
can be reused by the alias, phishing, and risk modules without creating
circular dependencies.
"""

from __future__ import annotations
import re
from typing import Optional


# ---------------------------------------------------------------------------
# Basic validation
# ---------------------------------------------------------------------------

# Minimal RFC-5322-compatible pattern for the purposes of this project.
# Full RFC-5322 validation is intentionally out of scope; the goal here is
# to reject obviously malformed strings before further processing.
_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


def is_valid_email_format(email: str) -> bool:
    """
    Return True if *email* matches a basic well-formed email pattern.

    This is a format check only — it does NOT verify deliverability or
    existence.

    Parameters
    ----------
    email : str
        The email address string to validate.

    Returns
    -------
    bool
        True when the format is acceptable, False otherwise.
    """
    if not isinstance(email, str):
        return False
    return bool(_EMAIL_REGEX.match(email.strip()))


# ---------------------------------------------------------------------------
# Splitting
# ---------------------------------------------------------------------------

def split_email(email: str) -> tuple[str, str]:
    """
    Split an email address into its local part and domain.

    Parameters
    ----------
    email : str
        A well-formed email address, e.g. ``"user+tag@gmail.com"``.

    Returns
    -------
    tuple[str, str]
        ``(local_part, domain)`` both in their original case.

    Raises
    ------
    ValueError
        If the address cannot be split (no '@' or multiple '@' signs).
    """
    email = email.strip()
    parts = email.split("@")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Cannot split email address: {email!r}")
    return parts[0], parts[1]


def get_domain(email: str) -> str:
    """
    Extract and lowercase the domain from an email address.

    Parameters
    ----------
    email : str
        A well-formed email address.

    Returns
    -------
    str
        The domain portion, lowercased.
    """
    _, domain = split_email(email)
    return domain.lower()


def get_local_part(email: str) -> str:
    """
    Extract the local part (everything before '@') from an email address.

    The value is returned as-is (original case preserved) because some
    provider rules are case-sensitive in their transformations.  Callers
    are responsible for applying case-folding when appropriate.

    Parameters
    ----------
    email : str
        A well-formed email address.

    Returns
    -------
    str
        The local part of the address.
    """
    local, _ = split_email(email)
    return local


def normalize_email_input(email: str) -> str:
    """
    Apply only universally safe, RFC-compliant pre-processing:
    strip whitespace and lowercase the domain.

    No provider-specific transformations are applied here.

    Parameters
    ----------
    email : str
        Raw email address string (possibly with surrounding whitespace).

    Returns
    -------
    str
        Cleaned email string with a lowercased domain.
    """
    email = email.strip()
    local, domain = split_email(email)
    return f"{local}@{domain.lower()}"

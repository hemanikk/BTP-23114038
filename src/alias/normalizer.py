"""
normalizer.py
-------------
Provider-aware email normalization engine.

Responsibility
--------------
Given an email address and a resolved ProviderConfig, derive the
**canonical form** of that address by applying only the provider's
*verified* and *enabled* alias rules.

Design decisions
----------------
- Normalization is purely deterministic — no ML, no heuristics.
- Rules are applied in a defined order so results are reproducible.
- If a provider is unrecognised, only RFC-safe transformations are applied
  (domain lowercasing, whitespace stripping) and the result is marked as
  having unknown/unverified normalization.
- No rule is invented.  If a provider's rule is not verified, it is skipped
  with an explicit note in the returned metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.alias.providers import ProviderConfig, ProviderRegistry
from src.utils.email_utils import (
    split_email,
    normalize_email_input,
    is_valid_email_format,
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class NormalizationResult:
    """
    The outcome of normalizing a single email address.

    Attributes
    ----------
    original_email : str
        The address exactly as supplied by the caller.
    canonical_email : str
        The normalized canonical form, or the cleaned original if normalization
        was not possible.
    provider_key : str | None
        The provider key (e.g. ``"gmail.com"``), or None if unrecognised.
    provider_name : str | None
        The human-readable provider name, or None if unrecognised.
    provider_verified : bool
        True only if the provider's overall entry is marked verified.
    transformations_applied : list[str]
        Human-readable list of transformation names that were applied,
        in order.
    skipped_rules : list[str]
        Rules that exist in the config but were skipped because they are
        unverified or disabled.
    is_valid_format : bool
        Whether the original email passed basic format validation.
    notes : list[str]
        Any informational messages generated during normalization.
    """
    original_email: str
    canonical_email: str
    provider_key: Optional[str]
    provider_name: Optional[str]
    provider_verified: bool
    transformations_applied: list[str] = field(default_factory=list)
    skipped_rules: list[str] = field(default_factory=list)
    is_valid_format: bool = True
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------

class EmailNormalizer:
    """
    Applies provider-specific normalization to derive a canonical email.

    Parameters
    ----------
    registry : ProviderRegistry
        A loaded provider registry.  Pass an explicit instance to make
        dependency injection easy in tests.

    Examples
    --------
    >>> from src.alias.providers import ProviderRegistry
    >>> registry = ProviderRegistry()
    >>> normalizer = EmailNormalizer(registry)
    >>> result = normalizer.normalize("User.Name+tag@gmail.com")
    >>> result.canonical_email
    'username@gmail.com'
    >>> result.transformations_applied
    ['case_fold_local', 'strip_plus_tag', 'remove_dots']
    """

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def normalize(self, email: str) -> NormalizationResult:
        """
        Derive the canonical form of *email*.

        Parameters
        ----------
        email : str
            The raw email address to normalize.

        Returns
        -------
        NormalizationResult
            A structured result containing the canonical address and full
            audit trail of what was (and was not) applied.
        """
        # 1. Basic format check
        valid_format = is_valid_email_format(email)
        notes: list[str] = []
        transformations: list[str] = []
        skipped: list[str] = []

        if not valid_format:
            notes.append(f"Email '{email}' failed basic format validation.")
            return NormalizationResult(
                original_email=email,
                canonical_email=email,
                provider_key=None,
                provider_name=None,
                provider_verified=False,
                is_valid_format=False,
                notes=notes,
            )

        # 2. RFC-safe pre-processing: strip whitespace, lowercase domain
        cleaned = normalize_email_input(email)
        local, domain = split_email(cleaned)

        # 3. Identify provider
        provider = self._registry.get_provider_for_domain(domain)

        if provider is None:
            notes.append(
                f"Domain '{domain}' is not recognised. "
                "Only RFC-safe transformations applied (domain lowercase)."
            )
            canonical = f"{local}@{domain}"
            return NormalizationResult(
                original_email=email,
                canonical_email=canonical,
                provider_key=None,
                provider_name=None,
                provider_verified=False,
                transformations_applied=["domain_lowercase"],
                notes=notes,
            )

        # 4. Apply provider-specific rules in a defined order
        canonical_local = local
        canonical_domain = self._registry.get_canonical_domain(domain) or domain

        # --- Rule: case_insensitive ---
        if self._registry.is_rule_active(provider, "case_insensitive"):
            new_local = canonical_local.lower()
            if new_local != canonical_local:
                transformations.append("case_fold_local")
            canonical_local = new_local
        else:
            rule = provider.rules.get("case_insensitive")
            if rule and not rule.verified:
                skipped.append("case_insensitive (unverified)")

        # --- Rule: plus_addressing ---
        if self._registry.is_rule_active(provider, "plus_addressing"):
            stripped = _strip_plus_tag(canonical_local, provider.key)
            if stripped != canonical_local:
                transformations.append("strip_plus_tag")
            canonical_local = stripped
        else:
            rule = provider.rules.get("plus_addressing")
            if rule and (not rule.verified or rule.enabled is False):
                skipped.append(
                    f"plus_addressing "
                    f"(verified={rule.verified}, enabled={rule.enabled})"
                )

        # --- Rule: dot_insensitive ---
        if self._registry.is_rule_active(provider, "dot_insensitive"):
            stripped = canonical_local.replace(".", "")
            if stripped != canonical_local:
                transformations.append("remove_dots")
            canonical_local = stripped
        else:
            rule = provider.rules.get("dot_insensitive")
            if rule and (not rule.verified or rule.enabled is False):
                skipped.append(
                    f"dot_insensitive "
                    f"(verified={rule.verified}, enabled={rule.enabled})"
                )

        # --- Rule: domain aliasing (googlemail / protonmail) ---
        canonical_domain = _resolve_canonical_domain(
            domain, canonical_domain, provider, self._registry, transformations
        )

        canonical = f"{canonical_local}@{canonical_domain}"
        transformations_with_base = ["domain_lowercase"] + transformations

        return NormalizationResult(
            original_email=email,
            canonical_email=canonical,
            provider_key=provider.key,
            provider_name=provider.name,
            provider_verified=provider.verified,
            transformations_applied=transformations_with_base,
            skipped_rules=skipped,
            is_valid_format=True,
            notes=notes,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _strip_plus_tag(local: str, provider_key: str) -> str:
    """
    Remove the plus-addressing tag from *local*.

    Gmail/Outlook/Proton use ``+`` as the separator.
    Yahoo uses ``-`` as the separator (documented disposable address format).

    Parameters
    ----------
    local : str
        The local part of the email address (already case-folded if applicable).
    provider_key : str
        The canonical provider key to select the correct separator.

    Returns
    -------
    str
        Local part with the tag removed, or the original string if no tag found.
    """
    if provider_key == "yahoo.com":
        # Yahoo's documented separator for disposable addresses is '-'
        separator = "-"
    else:
        separator = "+"

    if separator in local:
        return local.split(separator, 1)[0]
    return local


def _resolve_canonical_domain(
    original_domain: str,
    current_canonical: str,
    provider: ProviderConfig,
    registry: ProviderRegistry,
    transformations: list[str],
) -> str:
    """
    Apply domain-alias rules where a provider uses multiple equivalent domains.

    For example, Gmail treats ``googlemail.com`` as identical to ``gmail.com``.
    Proton treats ``protonmail.com`` / ``pm.me`` as identical to ``proton.me``.

    The function only applies these mappings when the relevant rule is both
    verified and enabled.

    Parameters
    ----------
    original_domain : str
        The domain from the input email (already lowercased).
    current_canonical : str
        The canonical domain key resolved from the domain index.
    provider : ProviderConfig
        The loaded provider config.
    registry : ProviderRegistry
        Used to check rule status.
    transformations : list[str]
        Mutable list that will be appended to if a domain alias is applied.

    Returns
    -------
    str
        The canonical domain to use in the final address.
    """
    rule_name_map = {
        "gmail.com": "googlemail_alias",
        "proton.me": "protonmail_domain_alias",
    }

    rule_name = rule_name_map.get(provider.key)
    if rule_name and registry.is_rule_active(provider, rule_name):
        if original_domain != current_canonical:
            transformations.append("canonical_domain_alias")
        return current_canonical

    # No domain alias rule — keep the original domain (lowercased)
    return original_domain

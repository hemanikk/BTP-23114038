"""
detector.py
-----------
Alias / same-identity detection engine.

Responsibility
--------------
Given two email addresses, determine whether they represent the same
underlying mailbox identity, according to the relevant provider's verified
alias rules.

Design decisions
----------------
- The detector delegates all normalization work to EmailNormalizer.
- Identity comparison is a simple string equality check on canonical forms.
- A structured, JSON-serialisable result dict is returned so the API layer
  can forward it to callers without transformation.
- No ML is used here.  This is an explicit, deterministic rule engine.
- The confidence field is deliberately categorical ('high' / 'medium' /
  'low' / 'unknown') rather than a numeric probability, because the
  rule-based engine does not have a meaningful probability estimate.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

from src.alias.normalizer import EmailNormalizer, NormalizationResult
from src.alias.providers import ProviderRegistry


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class AliasDetectionResult:
    """
    Structured result of comparing two email addresses for identity.

    Attributes
    ----------
    email_a : str
        First input email (original, as supplied).
    email_b : str
        Second input email (original, as supplied).
    same_identity : bool | None
        True  → the two addresses map to the same canonical identity.
        False → they do not.
        None  → could not be determined (e.g. provider unrecognised).
    provider : str | None
        Provider key if both addresses share the same verified provider,
        otherwise None.
    provider_name : str | None
        Human-readable provider name.
    canonical_a : str | None
        Canonical form of email_a, or None if normalization failed.
    canonical_b : str | None
        Canonical form of email_b, or None if normalization failed.
    alias_detected : bool
        True when same_identity is True AND the original addresses differ.
    alias_type : str | None
        A description of the alias transformation that produced the match,
        e.g. 'plus_addressing', 'dot_insensitive', 'domain_alias', or a
        combination string.  None when no alias is detected.
    transformations_a : list[str]
        Transformations applied to email_a during normalization.
    transformations_b : list[str]
        Transformations applied to email_b during normalization.
    confidence : str
        'high'    → both providers verified, same canonical result
        'medium'  → one or both providers not fully verified
        'low'     → providers differ or cannot be identified
        'unknown' → normalization failed for at least one address
    reason : str
        A plain-English explanation of the result.
    notes : list[str]
        Any additional informational messages from the normalization steps.
    """
    email_a: str
    email_b: str
    same_identity: Optional[bool]
    provider: Optional[str]
    provider_name: Optional[str]
    canonical_a: Optional[str]
    canonical_b: Optional[str]
    alias_detected: bool
    alias_type: Optional[str]
    transformations_a: list[str]
    transformations_b: list[str]
    confidence: str
    reason: str
    notes: list[str]

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dictionary representation."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class AliasDetector:
    """
    Determines whether two email addresses represent the same identity.

    Parameters
    ----------
    registry : ProviderRegistry | None
        If None, a default ProviderRegistry is instantiated automatically.

    Examples
    --------
    >>> detector = AliasDetector()
    >>> result = detector.detect("user.name+tag@gmail.com", "username@gmail.com")
    >>> result.same_identity
    True
    >>> result.alias_type
    'strip_plus_tag,remove_dots'
    """

    def __init__(self, registry: Optional[ProviderRegistry] = None) -> None:
        if registry is None:
            registry = ProviderRegistry()
        self._registry = registry
        self._normalizer = EmailNormalizer(registry)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, email_a: str, email_b: str) -> AliasDetectionResult:
        """
        Compare *email_a* and *email_b* and return a structured result.

        Parameters
        ----------
        email_a : str
            First email address.
        email_b : str
            Second email address.

        Returns
        -------
        AliasDetectionResult
        """
        norm_a: NormalizationResult = self._normalizer.normalize(email_a)
        norm_b: NormalizationResult = self._normalizer.normalize(email_b)

        all_notes = list(norm_a.notes) + list(norm_b.notes)

        # ---- Guard: invalid format ----------------------------------------
        if not norm_a.is_valid_format or not norm_b.is_valid_format:
            bad = []
            if not norm_a.is_valid_format:
                bad.append(email_a)
            if not norm_b.is_valid_format:
                bad.append(email_b)
            return AliasDetectionResult(
                email_a=email_a,
                email_b=email_b,
                same_identity=None,
                provider=None,
                provider_name=None,
                canonical_a=None,
                canonical_b=None,
                alias_detected=False,
                alias_type=None,
                transformations_a=norm_a.transformations_applied,
                transformations_b=norm_b.transformations_applied,
                confidence="unknown",
                reason=f"Invalid email format: {', '.join(bad)}",
                notes=all_notes,
            )

        # ---- Guard: unrecognised provider(s) --------------------------------
        if norm_a.provider_key is None or norm_b.provider_key is None:
            unrecognised = []
            if norm_a.provider_key is None:
                unrecognised.append(email_a)
            if norm_b.provider_key is None:
                unrecognised.append(email_b)
            return AliasDetectionResult(
                email_a=email_a,
                email_b=email_b,
                same_identity=None,
                provider=None,
                provider_name=None,
                canonical_a=norm_a.canonical_email,
                canonical_b=norm_b.canonical_email,
                alias_detected=False,
                alias_type=None,
                transformations_a=norm_a.transformations_applied,
                transformations_b=norm_b.transformations_applied,
                confidence="unknown",
                reason=(
                    f"Provider not recognised for: {', '.join(unrecognised)}. "
                    "Cannot apply provider-specific alias rules."
                ),
                notes=all_notes,
            )

        # ---- Guard: different providers -------------------------------------
        if norm_a.provider_key != norm_b.provider_key:
            return AliasDetectionResult(
                email_a=email_a,
                email_b=email_b,
                same_identity=False,
                provider=None,
                provider_name=None,
                canonical_a=norm_a.canonical_email,
                canonical_b=norm_b.canonical_email,
                alias_detected=False,
                alias_type=None,
                transformations_a=norm_a.transformations_applied,
                transformations_b=norm_b.transformations_applied,
                confidence="high",
                reason=(
                    f"Different providers: '{norm_a.provider_key}' vs "
                    f"'{norm_b.provider_key}'. "
                    "Cross-provider alias detection is not supported."
                ),
                notes=all_notes,
            )

        # ---- Core comparison ------------------------------------------------
        provider_key = norm_a.provider_key
        provider_name = norm_a.provider_name

        same_identity = norm_a.canonical_email == norm_b.canonical_email
        # Two addresses are "aliases" if they are the same identity but are
        # not literally the same string after basic RFC-safe normalization
        # (domain lowercase + whitespace strip).  Case differences in the
        # local part count as an alias because the provider normalizes them.
        def _basic_normalize(addr: str) -> str:
            addr = addr.strip()
            local_part, dom = addr.split("@", 1)
            return f"{local_part}@{dom.lower()}"

        alias_detected = same_identity and (
            _basic_normalize(email_a) != _basic_normalize(email_b)
        )

        alias_type = _derive_alias_type(norm_a, norm_b) if alias_detected else None

        confidence = _derive_confidence(norm_a, norm_b)

        reason = _build_reason(
            same_identity=same_identity,
            alias_detected=alias_detected,
            alias_type=alias_type,
            provider_name=provider_name,
            norm_a=norm_a,
            norm_b=norm_b,
        )

        return AliasDetectionResult(
            email_a=email_a,
            email_b=email_b,
            same_identity=same_identity,
            provider=provider_key,
            provider_name=provider_name,
            canonical_a=norm_a.canonical_email,
            canonical_b=norm_b.canonical_email,
            alias_detected=alias_detected,
            alias_type=alias_type,
            transformations_a=norm_a.transformations_applied,
            transformations_b=norm_b.transformations_applied,
            confidence=confidence,
            reason=reason,
            notes=all_notes,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _derive_alias_type(
    norm_a: NormalizationResult,
    norm_b: NormalizationResult,
) -> Optional[str]:
    """
    Derive a description of the alias transformation(s) responsible for the
    identity match.

    The alias type is inferred from the transformations that differ between
    the two normalizations.  Only transformations that appear in at least one
    address (and that meaningfully changed the canonical form) are reported.
    """
    # Transformations that are *meaningful* alias indicators
    alias_indicators = {
        "strip_plus_tag": "plus_addressing",
        "remove_dots": "dot_insensitive",
        "canonical_domain_alias": "domain_alias",
        "case_fold_local": "case_insensitive",
    }

    found: list[str] = []
    all_transforms = set(norm_a.transformations_applied) | set(
        norm_b.transformations_applied
    )
    for transform, label in alias_indicators.items():
        if transform in all_transforms:
            found.append(label)

    if not found:
        return "unknown_alias"
    return ",".join(found)


def _derive_confidence(
    norm_a: NormalizationResult,
    norm_b: NormalizationResult,
) -> str:
    """
    Assign a confidence level to the detection result.

    Rules
    -----
    - Both providers verified → 'high'
    - At least one provider entry verified but has unverified rules → 'medium'
    - Provider entry itself not verified → 'low'
    """
    if norm_a.provider_verified and norm_b.provider_verified:
        # If any rules were skipped due to being unverified, lower confidence
        if norm_a.skipped_rules or norm_b.skipped_rules:
            return "medium"
        return "high"
    return "low"


def _build_reason(
    same_identity: bool,
    alias_detected: bool,
    alias_type: Optional[str],
    provider_name: Optional[str],
    norm_a: NormalizationResult,
    norm_b: NormalizationResult,
) -> str:
    """Construct a plain-English explanation of the detection result."""
    if same_identity and alias_detected:
        return (
            f"Both addresses belong to the same {provider_name} identity. "
            f"Alias type(s) detected: {alias_type}. "
            f"Canonical form: '{norm_a.canonical_email}'."
        )
    if same_identity and not alias_detected:
        return (
            f"Both addresses are identical after normalization "
            f"({provider_name}). "
            f"Canonical form: '{norm_a.canonical_email}'."
        )
    return (
        f"The two addresses do not map to the same {provider_name} identity. "
        f"Canonical A: '{norm_a.canonical_email}', "
        f"Canonical B: '{norm_b.canonical_email}'."
    )

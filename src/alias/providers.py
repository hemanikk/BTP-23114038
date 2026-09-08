"""
providers.py
------------
Provider identification and rule loading.

Responsibility
--------------
- Load the structured provider configuration from ``config/providers.json``.
- Given an email domain, identify which provider (if any) governs it.
- Expose the provider's verified rules in a typed, query-able form.

Design decisions
----------------
- Configuration lives in a single JSON file so that adding a provider never
  requires touching Python source code.
- Rules whose ``verified`` flag is False are loaded but never applied by the
  normalizer.  This makes the system's uncertainty explicit and auditable.
- The module raises clear errors when the config file is missing rather than
  silently degrading.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

# Locate config/providers.json relative to this file's location so the
# project works regardless of the current working directory.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_DEFAULT_CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config", "providers.json")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ProviderRule:
    """Represents a single alias/normalization rule for a provider."""
    name: str
    enabled: Optional[bool]   # None means "unknown / not verified"
    description: str
    verified: bool
    source: Optional[str]


@dataclass
class ProviderConfig:
    """All configuration for a single email provider."""
    key: str                          # e.g. "gmail.com"
    name: str                         # e.g. "Gmail"
    domains: list[str]
    verified: bool                    # whether the provider entry itself is verified
    rules: dict[str, ProviderRule] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ProviderRegistry:
    """
    Loads provider rules from a JSON config file and answers domain-lookup
    queries.

    Usage
    -----
    >>> registry = ProviderRegistry()
    >>> provider = registry.get_provider_for_domain("gmail.com")
    >>> provider.name
    'Gmail'
    """

    def __init__(self, config_path: str = _DEFAULT_CONFIG_PATH) -> None:
        """
        Initialise the registry by loading the provider config file.

        Parameters
        ----------
        config_path : str
            Absolute or relative path to ``providers.json``.

        Raises
        ------
        FileNotFoundError
            If the config file does not exist at ``config_path``.
        ValueError
            If the JSON structure is malformed.
        """
        self._providers: dict[str, ProviderConfig] = {}
        # domain → provider key  (e.g. "googlemail.com" → "gmail.com")
        self._domain_index: dict[str, str] = {}
        self._load(config_path)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self, config_path: str) -> None:
        """Parse the JSON file and populate internal data structures."""
        if not os.path.isfile(config_path):
            raise FileNotFoundError(
                f"Provider config not found: {config_path}\n"
                "Ensure config/providers.json exists in the project root."
            )

        with open(config_path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)

        providers_raw = raw.get("providers", {})
        if not providers_raw:
            raise ValueError("providers.json contains no 'providers' section.")

        for key, data in providers_raw.items():
            rules: dict[str, ProviderRule] = {}
            for rule_name, rule_data in data.get("rules", {}).items():
                rules[rule_name] = ProviderRule(
                    name=rule_name,
                    enabled=rule_data.get("enabled"),      # may be None
                    description=rule_data.get("description", ""),
                    verified=rule_data.get("verified", False),
                    source=rule_data.get("source"),
                )

            provider = ProviderConfig(
                key=key,
                name=data["name"],
                domains=data.get("domains", [key]),
                verified=data.get("verified", False),
                rules=rules,
            )
            self._providers[key] = provider

            # Build a flat domain → provider-key lookup
            for domain in provider.domains:
                self._domain_index[domain.lower()] = key

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_provider_for_domain(self, domain: str) -> Optional[ProviderConfig]:
        """
        Return the ``ProviderConfig`` for *domain*, or ``None`` if the domain
        is not recognised.

        The lookup is case-insensitive.

        Parameters
        ----------
        domain : str
            The email domain, e.g. ``"googlemail.com"``.

        Returns
        -------
        ProviderConfig | None
        """
        key = self._domain_index.get(domain.lower())
        if key is None:
            return None
        return self._providers.get(key)

    def is_rule_active(self, provider: ProviderConfig, rule_name: str) -> bool:
        """
        Return True only if *rule_name* exists, is verified, and is enabled.

        A rule is **not** applied if:
        - it does not exist in the provider's rule set, or
        - its ``verified`` flag is False, or
        - its ``enabled`` value is False or None.

        Parameters
        ----------
        provider : ProviderConfig
            The provider whose rules to inspect.
        rule_name : str
            The rule identifier string (e.g. ``"plus_addressing"``).

        Returns
        -------
        bool
        """
        rule = provider.rules.get(rule_name)
        if rule is None:
            return False
        return rule.verified is True and rule.enabled is True

    def list_providers(self) -> list[str]:
        """Return the list of provider keys currently loaded."""
        return list(self._providers.keys())

    def get_canonical_domain(self, domain: str) -> Optional[str]:
        """
        Return the canonical (primary) domain key for a given domain.

        For example, ``"googlemail.com"`` maps to ``"gmail.com"`` because
        Gmail treats these as the same provider.

        Parameters
        ----------
        domain : str
            An email domain.

        Returns
        -------
        str | None
            The canonical provider key, or None if not recognised.
        """
        return self._domain_index.get(domain.lower())

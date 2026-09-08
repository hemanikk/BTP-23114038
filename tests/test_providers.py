"""
tests/test_providers.py
-----------------------
Unit tests for src/alias/providers.py
"""

import pytest
from src.alias.providers import ProviderRegistry, ProviderConfig, ProviderRule


@pytest.fixture(scope="module")
def registry() -> ProviderRegistry:
    """Shared registry instance for the entire test module."""
    return ProviderRegistry()


class TestProviderRegistryLoading:
    def test_registry_loads_without_error(self, registry):
        assert registry is not None

    def test_providers_are_loaded(self, registry):
        providers = registry.list_providers()
        assert len(providers) > 0

    def test_expected_providers_present(self, registry):
        expected = ["gmail.com", "yahoo.com", "outlook.com", "proton.me", "yandex.ru"]
        for key in expected:
            assert key in registry.list_providers(), f"Missing provider: {key}"


class TestDomainLookup:
    def test_gmail_primary_domain(self, registry):
        provider = registry.get_provider_for_domain("gmail.com")
        assert provider is not None
        assert provider.key == "gmail.com"
        assert provider.name == "Gmail"

    def test_googlemail_resolves_to_gmail(self, registry):
        provider = registry.get_provider_for_domain("googlemail.com")
        assert provider is not None
        assert provider.key == "gmail.com"

    def test_hotmail_resolves_to_outlook(self, registry):
        provider = registry.get_provider_for_domain("hotmail.com")
        assert provider is not None
        assert provider.key == "outlook.com"

    def test_live_com_resolves_to_outlook(self, registry):
        provider = registry.get_provider_for_domain("live.com")
        assert provider is not None
        assert provider.key == "outlook.com"

    def test_protonmail_resolves_to_proton(self, registry):
        provider = registry.get_provider_for_domain("protonmail.com")
        assert provider is not None
        assert provider.key == "proton.me"

    def test_pm_me_resolves_to_proton(self, registry):
        provider = registry.get_provider_for_domain("pm.me")
        assert provider is not None
        assert provider.key == "proton.me"

    def test_ymail_resolves_to_yahoo(self, registry):
        provider = registry.get_provider_for_domain("ymail.com")
        assert provider is not None
        assert provider.key == "yahoo.com"

    def test_unknown_domain_returns_none(self, registry):
        assert registry.get_provider_for_domain("unknowndomain.xyz") is None

    def test_lookup_is_case_insensitive(self, registry):
        assert registry.get_provider_for_domain("GMAIL.COM") is not None
        assert registry.get_provider_for_domain("Gmail.Com") is not None


class TestCanonicalDomain:
    def test_googlemail_canonical_is_gmail(self, registry):
        assert registry.get_canonical_domain("googlemail.com") == "gmail.com"

    def test_gmail_canonical_is_gmail(self, registry):
        assert registry.get_canonical_domain("gmail.com") == "gmail.com"

    def test_unknown_returns_none(self, registry):
        assert registry.get_canonical_domain("notreal.com") is None


class TestIsRuleActive:
    """
    Verify that is_rule_active correctly gates on verified AND enabled flags.
    """

    def test_gmail_plus_addressing_active(self, registry):
        provider = registry.get_provider_for_domain("gmail.com")
        assert registry.is_rule_active(provider, "plus_addressing") is True

    def test_gmail_dot_insensitive_active(self, registry):
        provider = registry.get_provider_for_domain("gmail.com")
        assert registry.is_rule_active(provider, "dot_insensitive") is True

    def test_yahoo_dot_insensitive_NOT_active(self, registry):
        # Yahoo explicitly has dot_insensitive: false
        provider = registry.get_provider_for_domain("yahoo.com")
        assert registry.is_rule_active(provider, "dot_insensitive") is False

    def test_outlook_dot_insensitive_NOT_active(self, registry):
        provider = registry.get_provider_for_domain("outlook.com")
        assert registry.is_rule_active(provider, "dot_insensitive") is False

    def test_yandex_plus_addressing_NOT_active(self, registry):
        # Yandex rules are unverified — must NOT be applied
        provider = registry.get_provider_for_domain("yandex.ru")
        assert registry.is_rule_active(provider, "plus_addressing") is False

    def test_yandex_dot_insensitive_NOT_active(self, registry):
        provider = registry.get_provider_for_domain("yandex.ru")
        assert registry.is_rule_active(provider, "dot_insensitive") is False

    def test_nonexistent_rule_returns_false(self, registry):
        provider = registry.get_provider_for_domain("gmail.com")
        assert registry.is_rule_active(provider, "this_rule_does_not_exist") is False

    def test_proton_plus_addressing_active(self, registry):
        provider = registry.get_provider_for_domain("proton.me")
        assert registry.is_rule_active(provider, "plus_addressing") is True

    def test_proton_dot_insensitive_NOT_active(self, registry):
        provider = registry.get_provider_for_domain("proton.me")
        assert registry.is_rule_active(provider, "dot_insensitive") is False

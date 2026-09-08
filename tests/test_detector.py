"""
tests/test_detector.py
----------------------
Unit tests for src/alias/detector.py
"""

import pytest
from src.alias.providers import ProviderRegistry
from src.alias.detector import AliasDetector


@pytest.fixture(scope="module")
def detector() -> AliasDetector:
    return AliasDetector(ProviderRegistry())


# ===========================================================================
# POSITIVE: same identity
# ===========================================================================

class TestGmailSameIdentity:
    def test_plus_addressing(self, detector):
        r = detector.detect("testuser@gmail.com", "testuser+newsletter@gmail.com")
        assert r.same_identity is True
        assert r.alias_detected is True
        assert "plus_addressing" in r.alias_type

    def test_dot_insensitive(self, detector):
        r = detector.detect("testuser@gmail.com", "test.user@gmail.com")
        assert r.same_identity is True
        assert r.alias_detected is True
        assert "dot_insensitive" in r.alias_type

    def test_case_insensitive(self, detector):
        r = detector.detect("testuser@gmail.com", "TestUser@gmail.com")
        assert r.same_identity is True
        assert r.alias_detected is True

    def test_combined_plus_and_dots(self, detector):
        r = detector.detect("testuser@gmail.com", "t.e.s.t.u.s.e.r+tag@gmail.com")
        assert r.same_identity is True

    def test_googlemail_alias(self, detector):
        r = detector.detect("testuser@gmail.com", "testuser@googlemail.com")
        assert r.same_identity is True
        assert "domain_alias" in r.alias_type

    def test_identical_addresses(self, detector):
        r = detector.detect("user@gmail.com", "user@gmail.com")
        assert r.same_identity is True
        assert r.alias_detected is False  # same string → not an alias

    def test_confidence_is_high_for_gmail(self, detector):
        r = detector.detect("user@gmail.com", "user+tag@gmail.com")
        assert r.confidence == "high"


class TestYahooSameIdentity:
    def test_dash_addressing(self, detector):
        r = detector.detect("testbase@yahoo.com", "testbase-shopping@yahoo.com")
        assert r.same_identity is True
        assert r.alias_detected is True


class TestOutlookSameIdentity:
    def test_plus_addressing(self, detector):
        r = detector.detect("testuser@outlook.com", "testuser+shopping@outlook.com")
        assert r.same_identity is True

    def test_hotmail_plus_addressing(self, detector):
        r = detector.detect("testuser@hotmail.com", "testuser+tag@hotmail.com")
        assert r.same_identity is True


class TestProtonSameIdentity:
    def test_plus_addressing(self, detector):
        r = detector.detect("testuser@proton.me", "testuser+secure@proton.me")
        assert r.same_identity is True

    def test_protonmail_domain_alias(self, detector):
        r = detector.detect("testuser@proton.me", "testuser@protonmail.com")
        assert r.same_identity is True

    def test_pm_me_alias(self, detector):
        r = detector.detect("testuser@proton.me", "testuser@pm.me")
        assert r.same_identity is True


# ===========================================================================
# NEGATIVE: different identities
# ===========================================================================

class TestDifferentIdentities:
    def test_different_gmail_usernames(self, detector):
        r = detector.detect("alice@gmail.com", "bob@gmail.com")
        assert r.same_identity is False
        assert r.alias_detected is False

    def test_gmail_vs_number_suffix(self, detector):
        r = detector.detect("testuser@gmail.com", "testuser2@gmail.com")
        assert r.same_identity is False

    def test_yahoo_dots_NOT_ignored(self, detector):
        r = detector.detect("test.user@yahoo.com", "testuser@yahoo.com")
        # Yahoo does NOT remove dots → these are different addresses
        assert r.same_identity is False

    def test_outlook_dots_NOT_ignored(self, detector):
        r = detector.detect("test.user@outlook.com", "testuser@outlook.com")
        assert r.same_identity is False

    def test_proton_dots_NOT_ignored(self, detector):
        r = detector.detect("test.user@proton.me", "testuser@proton.me")
        assert r.same_identity is False

    def test_homoglyph_are_different(self, detector):
        r = detector.detect("alice@gmail.com", "a1ice@gmail.com")
        assert r.same_identity is False


# ===========================================================================
# CROSS-PROVIDER: always different
# ===========================================================================

class TestCrossProvider:
    def test_gmail_vs_outlook(self, detector):
        r = detector.detect("testuser@gmail.com", "testuser@outlook.com")
        assert r.same_identity is False
        assert "Different providers" in r.reason

    def test_gmail_vs_yahoo(self, detector):
        r = detector.detect("testuser@gmail.com", "testuser@yahoo.com")
        assert r.same_identity is False

    def test_outlook_vs_proton(self, detector):
        r = detector.detect("testuser@outlook.com", "testuser@proton.me")
        assert r.same_identity is False


# ===========================================================================
# YANDEX: unverified provider
# ===========================================================================

class TestYandexUnverified:
    def test_yandex_plus_NOT_considered_alias(self, detector):
        """Plus addressing for Yandex is unverified — must not be applied."""
        r = detector.detect("user@yandex.ru", "user+tag@yandex.ru")
        # Because the rule is unverified, the '+tag' is NOT stripped →
        # canonical forms differ → same_identity is False
        assert r.same_identity is False

    def test_yandex_confidence_is_low(self, detector):
        r = detector.detect("user@yandex.ru", "user@yandex.ru")
        assert r.confidence == "low"


# ===========================================================================
# UNKNOWN PROVIDER
# ===========================================================================

class TestUnknownProvider:
    def test_unknown_provider_returns_none_identity(self, detector):
        r = detector.detect("user@unknowndomain.xyz", "user@unknowndomain.xyz")
        assert r.same_identity is None
        assert r.confidence == "unknown"

    def test_known_vs_unknown_provider(self, detector):
        r = detector.detect("user@gmail.com", "user@unknowndomain.xyz")
        assert r.same_identity is None


# ===========================================================================
# INVALID FORMAT
# ===========================================================================

class TestInvalidFormat:
    def test_both_invalid(self, detector):
        r = detector.detect("notanemail", "alsoinvalid")
        assert r.same_identity is None
        assert r.confidence == "unknown"

    def test_one_invalid(self, detector):
        r = detector.detect("user@gmail.com", "notanemail")
        assert r.same_identity is None

    def test_result_is_serialisable(self, detector):
        r = detector.detect("user@gmail.com", "user+tag@gmail.com")
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["same_identity"] is True
        assert d["email_a"] == "user@gmail.com"

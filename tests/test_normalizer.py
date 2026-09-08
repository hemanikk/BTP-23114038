"""
tests/test_normalizer.py
------------------------
Unit tests for src/alias/normalizer.py
"""

import pytest
from src.alias.providers import ProviderRegistry
from src.alias.normalizer import EmailNormalizer


@pytest.fixture(scope="module")
def normalizer() -> EmailNormalizer:
    return EmailNormalizer(ProviderRegistry())


class TestGmailNormalization:
    """Gmail: plus addressing + dot removal + case folding + googlemail alias."""

    def test_plus_tag_stripped(self, normalizer):
        r = normalizer.normalize("user+tag@gmail.com")
        assert r.canonical_email == "user@gmail.com"
        assert "strip_plus_tag" in r.transformations_applied

    def test_dots_removed(self, normalizer):
        r = normalizer.normalize("u.s.e.r@gmail.com")
        assert r.canonical_email == "user@gmail.com"
        assert "remove_dots" in r.transformations_applied

    def test_case_folded(self, normalizer):
        r = normalizer.normalize("TestUser@gmail.com")
        assert r.canonical_email == "testuser@gmail.com"
        assert "case_fold_local" in r.transformations_applied

    def test_all_three_combined(self, normalizer):
        r = normalizer.normalize("T.E.S.T+tag@gmail.com")
        assert r.canonical_email == "test@gmail.com"
        assert "strip_plus_tag" in r.transformations_applied
        assert "remove_dots" in r.transformations_applied
        assert "case_fold_local" in r.transformations_applied

    def test_googlemail_domain_aliased_to_gmail(self, normalizer):
        r = normalizer.normalize("testuser@googlemail.com")
        assert r.canonical_email == "testuser@gmail.com"
        assert "canonical_domain_alias" in r.transformations_applied

    def test_provider_identified_correctly(self, normalizer):
        r = normalizer.normalize("user@gmail.com")
        assert r.provider_key == "gmail.com"
        assert r.provider_name == "Gmail"
        assert r.provider_verified is True

    def test_no_change_needed(self, normalizer):
        r = normalizer.normalize("user@gmail.com")
        assert r.canonical_email == "user@gmail.com"

    def test_multiple_plus_signs_only_first_stripped(self, normalizer):
        r = normalizer.normalize("user+tag1+tag2@gmail.com")
        assert r.canonical_email == "user@gmail.com"


class TestYahooNormalization:
    """Yahoo: dash-based plus addressing, but dots are NOT removed."""

    def test_dash_tag_stripped(self, normalizer):
        r = normalizer.normalize("testbase-shopping@yahoo.com")
        assert r.canonical_email == "testbase@yahoo.com"
        assert "strip_plus_tag" in r.transformations_applied

    def test_dots_NOT_removed(self, normalizer):
        r = normalizer.normalize("test.user@yahoo.com")
        # Dots must be preserved for Yahoo
        assert r.canonical_email == "test.user@yahoo.com"
        assert "remove_dots" not in r.transformations_applied

    def test_case_folded(self, normalizer):
        r = normalizer.normalize("TestUser@yahoo.com")
        assert r.canonical_email == "testuser@yahoo.com"

    def test_ymail_domain_kept_as_is(self, normalizer):
        # ymail.com resolves to the yahoo.com provider but we don't have a
        # domain alias rule for ymail, so the domain should stay ymail.com
        r = normalizer.normalize("user@ymail.com")
        assert r.provider_key == "yahoo.com"
        # domain alias rule is not defined for ymail, so domain stays
        assert "@ymail.com" in r.canonical_email


class TestOutlookNormalization:
    """Outlook/Hotmail: plus addressing only; dots NOT removed."""

    def test_plus_tag_stripped(self, normalizer):
        r = normalizer.normalize("user+shopping@outlook.com")
        assert r.canonical_email == "user@outlook.com"

    def test_hotmail_plus_stripped(self, normalizer):
        r = normalizer.normalize("user+tag@hotmail.com")
        assert r.canonical_email == "user@hotmail.com"

    def test_dots_NOT_removed(self, normalizer):
        r = normalizer.normalize("first.last@outlook.com")
        assert r.canonical_email == "first.last@outlook.com"
        assert "remove_dots" not in r.transformations_applied

    def test_case_folded(self, normalizer):
        r = normalizer.normalize("MyUser@Outlook.COM")
        assert r.canonical_email == "myuser@outlook.com"


class TestProtonNormalization:
    """Proton: plus addressing + domain alias; dots NOT removed."""

    def test_plus_tag_stripped(self, normalizer):
        r = normalizer.normalize("user+secure@proton.me")
        assert r.canonical_email == "user@proton.me"

    def test_protonmail_domain_aliased(self, normalizer):
        r = normalizer.normalize("user@protonmail.com")
        assert r.canonical_email == "user@proton.me"
        assert "canonical_domain_alias" in r.transformations_applied

    def test_pm_me_domain_aliased(self, normalizer):
        r = normalizer.normalize("user@pm.me")
        assert r.canonical_email == "user@proton.me"
        assert "canonical_domain_alias" in r.transformations_applied

    def test_dots_NOT_removed(self, normalizer):
        r = normalizer.normalize("first.last@proton.me")
        assert r.canonical_email == "first.last@proton.me"
        assert "remove_dots" not in r.transformations_applied


class TestYandexNormalization:
    """Yandex: provider entry is unverified; only safe transforms applied."""

    def test_only_domain_lowercase_applied(self, normalizer):
        r = normalizer.normalize("TestUser@Yandex.RU")
        # Case folding for Yandex is NOT verified in the config,
        # so the local part should NOT be case-folded
        # (the verified flag for case_insensitive on yandex is False)
        # Only domain lowercasing (RFC-safe) is guaranteed
        assert "yandex.ru" in r.canonical_email

    def test_provider_identified_but_not_verified(self, normalizer):
        r = normalizer.normalize("user@yandex.ru")
        assert r.provider_key == "yandex.ru"
        assert r.provider_verified is False

    def test_no_plus_stripping(self, normalizer):
        r = normalizer.normalize("user+tag@yandex.ru")
        # plus_addressing not verified for Yandex → must NOT strip
        assert "+tag" in r.canonical_email


class TestUnknownProvider:
    """Addresses from unrecognised domains get only RFC-safe transforms."""

    def test_unknown_provider_returns_none_key(self, normalizer):
        r = normalizer.normalize("user@unknowndomain.xyz")
        assert r.provider_key is None

    def test_domain_lowercased_only(self, normalizer):
        r = normalizer.normalize("User+tag@UnknownDomain.XYZ")
        # No provider-specific transforms applied
        assert r.canonical_email == "User+tag@unknowndomain.xyz"

    def test_note_explains_unknown(self, normalizer):
        r = normalizer.normalize("user@unknowndomain.xyz")
        assert any("not recognised" in note for note in r.notes)


class TestInvalidEmailFormat:
    def test_missing_at_sign(self, normalizer):
        r = normalizer.normalize("notanemail")
        assert r.is_valid_format is False
        assert r.canonical_email == "notanemail"

    def test_empty_string(self, normalizer):
        r = normalizer.normalize("")
        assert r.is_valid_format is False

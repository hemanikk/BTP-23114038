"""
tests/test_email_utils.py
--------------------------
Unit tests for src/utils/email_utils.py
"""

import pytest
from src.utils.email_utils import (
    is_valid_email_format,
    split_email,
    get_domain,
    get_local_part,
    normalize_email_input,
)


class TestIsValidEmailFormat:
    def test_simple_valid(self):
        assert is_valid_email_format("user@example.com") is True

    def test_plus_valid(self):
        assert is_valid_email_format("user+tag@gmail.com") is True

    def test_dot_in_local_valid(self):
        assert is_valid_email_format("first.last@domain.org") is True

    def test_subdomain_valid(self):
        assert is_valid_email_format("user@mail.domain.co.uk") is True

    def test_no_at_sign(self):
        assert is_valid_email_format("nodomain.com") is False

    def test_no_domain(self):
        assert is_valid_email_format("user@") is False

    def test_no_local(self):
        assert is_valid_email_format("@domain.com") is False

    def test_double_at(self):
        assert is_valid_email_format("user@@domain.com") is False

    def test_spaces(self):
        assert is_valid_email_format("user @domain.com") is False

    def test_empty_string(self):
        assert is_valid_email_format("") is False

    def test_non_string(self):
        assert is_valid_email_format(None) is False  # type: ignore
        assert is_valid_email_format(123) is False    # type: ignore

    def test_leading_whitespace_stripped_before_check(self):
        # is_valid_email_format strips whitespace internally
        assert is_valid_email_format("  user@example.com  ") is True


class TestSplitEmail:
    def test_basic_split(self):
        assert split_email("user@example.com") == ("user", "example.com")

    def test_plus_preserved(self):
        assert split_email("user+tag@gmail.com") == ("user+tag", "gmail.com")

    def test_whitespace_stripped(self):
        assert split_email("  user@example.com  ") == ("user", "example.com")

    def test_no_at_raises(self):
        with pytest.raises(ValueError):
            split_email("nodomain.com")

    def test_double_at_raises(self):
        with pytest.raises(ValueError):
            split_email("user@@domain.com")

    def test_empty_local_raises(self):
        with pytest.raises(ValueError):
            split_email("@domain.com")


class TestGetDomain:
    def test_lowercase_returned(self):
        assert get_domain("user@Gmail.COM") == "gmail.com"

    def test_basic(self):
        assert get_domain("a@b.com") == "b.com"


class TestGetLocalPart:
    def test_case_preserved(self):
        # Case is NOT folded by this helper — normalization is provider-specific
        assert get_local_part("User+Tag@Gmail.com") == "User+Tag"

    def test_basic(self):
        assert get_local_part("hello@world.org") == "hello"


class TestNormalizeEmailInput:
    def test_domain_lowercased(self):
        assert normalize_email_input("User@GMAIL.COM") == "User@gmail.com"

    def test_local_case_preserved(self):
        # This function only lowercases the domain — not the local part
        assert normalize_email_input("MyUser@Outlook.COM") == "MyUser@outlook.com"

    def test_whitespace_stripped(self):
        assert normalize_email_input("  user@example.com  ") == "user@example.com"

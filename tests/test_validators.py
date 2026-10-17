import pytest
from utils.validators import (
    validate_text_input,
    validate_url_input,
    is_private_or_local_hostname,
    ValidationError
)


class TestTextInputValidation:
    def test_valid_text(self):
        text = "This is a legitimate news headline about space exploration."
        result = validate_text_input(text)
        assert result == text

    def test_empty_text_raises_validation_error(self):
        with pytest.raises(ValidationError, match="Input cannot be empty"):
            validate_text_input("   ")

    def test_non_string_raises_validation_error(self):
        with pytest.raises(ValidationError, match="Input must be a string"):
            validate_text_input(12345)

    def test_too_short_text(self):
        with pytest.raises(ValidationError, match="at least"):
            validate_text_input("abc")

    def test_null_bytes_blocked(self):
        with pytest.raises(ValidationError, match="invalid control characters"):
            validate_text_input("Breaking news\x00malicious payload")

    def test_whitespace_normalized(self):
        raw = "  Multiple    spaces   between words   "
        assert validate_text_input(raw) == "Multiple spaces between words"


class TestUrlValidation:
    def test_valid_https_url(self):
        url = "https://www.bbc.com/news/world"
        assert validate_url_input(url) == url

    def test_valid_http_url(self):
        url = "http://reuters.com/article/123"
        assert validate_url_input(url) == url

    def test_non_http_scheme_blocked(self):
        with pytest.raises(ValidationError, match="must use http or https"):
            validate_url_input("ftp://example.com/file.txt")

    def test_javascript_scheme_blocked(self):
        with pytest.raises(ValidationError, match="must use http or https"):
            validate_url_input("javascript:alert(1)")

    def test_empty_url_blocked(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_url_input("")


class TestSSRFHostnameValidation:
    def test_localhost_blocked(self):
        assert is_private_or_local_hostname("localhost") is True
        assert is_private_or_local_hostname("127.0.0.1") is True
        assert is_private_or_local_hostname("0.0.0.0") is True

    def test_local_domain_suffix_blocked(self):
        assert is_private_or_local_hostname("test.local") is True
        assert is_private_or_local_hostname("app.localhost") is True

    def test_private_ips_blocked(self):
        assert is_private_or_local_hostname("192.168.1.1") is True
        assert is_private_or_local_hostname("10.0.0.1") is True
        assert is_private_or_local_hostname("172.16.0.1") is True

    def test_public_domain_allowed(self):
        # A known public DNS domain
        assert is_private_or_local_hostname("bbc.com") is False

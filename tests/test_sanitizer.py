import pytest
from utils.sanitizer import sanitize_html, sanitize_url


class TestSanitizeHtml:
    def test_plain_text_untouched(self):
        text = "Breaking News: Economy grew by 5 percent."
        assert sanitize_html(text) == text

    def test_html_tags_escaped(self):
        html_input = "<b>Breaking</b> <script>alert(1)</script>"
        result = sanitize_html(html_input)
        assert "<script>" not in result
        assert "&lt;b&gt;" in result

    def test_event_handlers_stripped(self):
        malicious = "<img src='x' onerror='alert(1)'>"
        result = sanitize_html(malicious)
        assert "onerror=" not in result

    def test_non_string_handled(self):
        assert sanitize_html(12345) == "12345"


class TestSanitizeUrl:
    def test_valid_urls_allowed(self):
        assert sanitize_url("https://bbc.com") == "https://bbc.com"
        assert sanitize_url("http://reuters.com") == "http://reuters.com"

    def test_javascript_protocol_rejected(self):
        assert sanitize_url("javascript:alert(1)") == ""

    def test_data_protocol_rejected(self):
        assert sanitize_url("data:text/html,<script>alert(1)</script>") == ""

    def test_non_string_rejected(self):
        assert sanitize_url(None) == ""
        assert sanitize_url(123) == ""

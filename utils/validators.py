# utils/validators.py
import re
import socket
import ipaddress
from urllib.parse import urlparse
from config import config


class ValidationError(ValueError):
    """Custom validation error."""
    pass


def validate_text_input(text):
    """
    Validate text input for analysis.

    Args:
        text: Raw user input text

    Returns:
        Cleaned and validated text

    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(text, str):
        raise ValidationError("Input must be a string")

    text = text.strip()

    if len(text) == 0:
        raise ValidationError("Input cannot be empty")

    if len(text) > config.MAX_TEXT_LENGTH:
        raise ValidationError(
            f"Input exceeds maximum length of {config.MAX_TEXT_LENGTH} characters"
        )

    if len(text) < config.MIN_TEXT_LENGTH:
        raise ValidationError(
            f"Input must be at least {config.MIN_TEXT_LENGTH} characters long"
        )

    # Prevent null bytes and dangerous control characters
    if any(char in text for char in "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f"):
        raise ValidationError("Input contains invalid control characters")

    # Normalize whitespace
    text = " ".join(text.split())

    return text


def is_private_or_local_hostname(hostname):
    """
    Block local/private/internal hostnames and IPs to prevent SSRF.
    """
    if not hostname:
        return True

    hostname = hostname.strip().lower().rstrip(".")

    blocked_hostnames = {
        "localhost",
        "0.0.0.0",
        "127.0.0.1",
        "::1"
    }

    if hostname in blocked_hostnames:
        return True

    if hostname.endswith(".localhost") or hostname.endswith(".local"):
        return True

    # Case 1: hostname itself is an IP address
    try:
        ip_obj = ipaddress.ip_address(hostname)

        return (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        )
    except ValueError:
        pass

    # Case 2: hostname is a domain, resolve it and check IPs
    try:
        resolved_ips = socket.getaddrinfo(hostname, None)

        for result in resolved_ips:
            ip = result[4][0]
            ip_obj = ipaddress.ip_address(ip)

            if (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_link_local
                or ip_obj.is_multicast
                or ip_obj.is_reserved
                or ip_obj.is_unspecified
            ):
                return True

    except socket.gaierror:
        # If DNS cannot resolve, block it
        return True

    return False


def validate_url_input(url):
    """
    Validate URL input for scraping and block SSRF-risk targets.

    Args:
        url: Raw URL string

    Returns:
        Cleaned and validated URL

    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(url, str):
        raise ValidationError("URL must be a string")

    url = url.strip()

    if len(url) == 0:
        raise ValidationError("URL cannot be empty")

    if len(url) > config.MAX_URL_LENGTH:
        raise ValidationError(
            f"URL exceeds maximum length of {config.MAX_URL_LENGTH} characters"
        )

    try:
        parsed = urlparse(url)

        if parsed.scheme not in {"http", "https"}:
            raise ValidationError("URL must use http or https")

        if not parsed.netloc or not parsed.hostname:
            raise ValidationError("URL must include a valid domain")

        if parsed.username or parsed.password:
            raise ValidationError("URL must not contain username or password")

        if is_private_or_local_hostname(parsed.hostname):
            raise ValidationError("Private, local, or internal URLs are not allowed")

    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Invalid URL: {str(e)}")

    return url


def validate_headline(headline):
    """
    Validate headline input.

    Args:
        headline: Raw headline string

    Returns:
        Cleaned headline

    Raises:
        ValidationError: If validation fails
    """
    return validate_text_input(headline)
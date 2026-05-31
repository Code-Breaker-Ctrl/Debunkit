# utils/sanitizer.py
import re
import html as html_module

def sanitize_html(text):
    """
    Sanitize HTML content to prevent XSS.
    
    Args:
        text: HTML string to sanitize
    
    Returns:
        Sanitized text safe for display
    """
    if not isinstance(text, str):
        return str(text)
    
    # Escape HTML special characters
    text = html_module.escape(text)
    
    # Remove any remaining script tags
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    
    return text.strip()

def sanitize_url(url):
    """
    Sanitize URL to prevent injection attacks.
    
    Args:
        url: URL string
    
    Returns:
        Safe URL string
    """
    if not isinstance(url, str):
        return ""
    
    # Only allow http and https
    if not url.startswith(('http://', 'https://')):
        return ""
    
    # Remove javascript: and data: protocols
    if re.match(r'^\s*(javascript|data|vbscript):', url, re.IGNORECASE):
        return ""
    
    return url.strip()
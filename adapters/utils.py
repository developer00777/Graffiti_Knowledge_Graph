"""
Shared adapter utilities.
"""
import re
from html import unescape


def strip_html(html: str) -> str:
    """Strip HTML tags and return clean plain text."""
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<[^>]+>', ' ', html)
    html = unescape(html)
    html = re.sub(r'\s+', ' ', html).strip()
    return html

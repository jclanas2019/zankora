from __future__ import annotations
import re
from typing import Tuple

URL_RE = re.compile(r"(https?://\S+)", re.IGNORECASE)

def sanitize_text(text: str) -> Tuple[str, list[str]]:
    """Basic input sanitization:
    - strips control chars
    - extracts URLs for metadata/logging
    - truncates overly long messages
    """
    issues: list[str] = []
    # remove control chars except \n and \t
    cleaned = "".join(ch for ch in text if ch >= " " or ch in "\n\t")
    if cleaned != text:
        issues.append("control_chars_removed")
    urls = URL_RE.findall(cleaned)
    if len(cleaned) > 4000:
        cleaned = cleaned[:4000]
        issues.append("truncated")
    # Redact long query params
    cleaned = re.sub(r"(https?://\S{120,})", "[link_redacted]", cleaned)
    if urls:
        issues.append(f"urls:{len(urls)}")
    return cleaned, issues

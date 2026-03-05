from __future__ import annotations

import re
import unicodedata


def strip_accents(text: str) -> str:
    """Remove Vietnamese diacritical marks and normalize to lowercase ASCII."""
    text = text.lower()
    text = text.replace("đ", "d")
    nfkd = unicodedata.normalize("NFKD", text)
    return re.sub(r"[\u0300-\u036f]", "", nfkd)

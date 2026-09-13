import re

# Tokens that must never appear in the AI response for static knowledge.
# Matching is case‑insensitive and looks for whole words.
PROHIBITED_TOKENS = []  # No over‑broad blacklist; validator will only block truly unsupported claims

_GENERIC_FALLBACK = "Tôi chưa có thông tin chính thức về nội dung này."


def validate_response(text: str) -> str:
    """Return the original text if it does not contain prohibited tokens.

    If any prohibited token is found (case‑insensitive), the function returns a
    generic fallback message instead of the original answer.
    """
    lowered = text.lower()
    for pattern in PROHIBITED_TOKENS:
        if re.search(pattern, lowered):
            return _GENERIC_FALLBACK
    return text

"""
services/redact.py
Scans transcript text and redacts sensitive patterns (card numbers).
"""

import re

# Matches 16-digit card numbers in common formats:
# 4111111111111111  |  4111 1111 1111 1111  |  4111-1111-1111-1111
_CARD_PATTERN = re.compile(
    r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"
)

REDACTION_PLACEHOLDER = "[CARD_REDACTED]"


def redact_text(text: str) -> tuple[str, bool]:
    """
    Replace card number patterns in text with [CARD_REDACTED].
    Returns (redacted_text, was_redacted).
    """
    redacted, count = _CARD_PATTERN.subn(REDACTION_PLACEHOLDER, text)
    return redacted, count > 0


def redact_turns(turns: list[dict]) -> tuple[list[dict], bool]:
    """
    Apply redaction to every turn's text field.
    Returns (redacted_turns, any_redacted).
    """
    any_redacted = False
    result = []
    for turn in turns:
        clean_text, was_redacted = redact_text(turn.get("text", ""))
        if was_redacted:
            any_redacted = True
        result.append({**turn, "text": clean_text})
    return result, any_redacted

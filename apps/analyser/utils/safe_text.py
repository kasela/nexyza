import re
from typing import Any

SUSPICIOUS_PATTERNS = [
    r'(?i)adult',
    r'(?i)explicit',
    r'(?i)sex(?:ual)?',
    r'(?i)porn(?:ography)?',
    r'(?i)nude',
    r'(?i)xxx',
    r'(?i)escort',
    r'(?i)fetish',
    r'(?i)intimate',
]

_compiled = [re.compile(p) for p in SUSPICIOUS_PATTERNS]


def sanitize_text(value: Any, limit: int = 180, preview: bool = False) -> str:
    if value is None:
        return ''
    text = str(value)
    text = re.sub(r'\s+', ' ', text).strip()
    if preview:
        text = re.sub(r'[^\w\s%+\-_/.,()]+', '', text)
    for pattern in _compiled:
        text = pattern.sub('[redacted]', text)
    if len(text) > limit:
        text = text[: max(0, limit - 1)].rstrip() + '…'
    return text

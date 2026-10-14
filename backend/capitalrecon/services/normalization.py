import re

NON_ALNUM = re.compile(r"[^A-Za-z0-9]")
SUFFIXES = ("LLC", "LP", "LTD", "INC")


def normalize_reference(value: str) -> str:
    """Uppercase and keep only letters/digits. e.g. 'cc-1003' -> 'CC1003'."""
    if value is None:
        return ""
    return NON_ALNUM.sub("", str(value).upper())


def normalize_name(value: str) -> str:
    """Uppercase, non-alnum -> space, collapse spaces, drop trailing LLC/LP/LTD/INC."""
    if value is None:
        return ""
    text = NON_ALNUM.sub(" ", str(value).upper())
    text = re.sub(r"\s+", " ", text).strip()
    # Drop trailing entity suffixes (one pass; e.g. 'HALLER CAPITAL LLC' -> 'HALLER CAPITAL')
    for suffix in SUFFIXES:
        if text.endswith(" " + suffix):
            text = text[: -(len(suffix) + 1)].strip()
            break
    return text


def name_found_in(name_norm: str, description: str) -> bool:
    """Return True if the normalized name appears as whole words in the description."""
    if not name_norm:
        return False
    desc_norm = NON_ALNUM.sub(" ", str(description).upper())
    desc_norm = re.sub(r"\s+", " ", desc_norm).strip()
    name_words = name_norm.split()
    if not name_words:
        return False
    desc_words = desc_norm.split()
    if len(name_words) > len(desc_words):
        return False
    # Sliding window over whole words
    for i in range(len(desc_words) - len(name_words) + 1):
        if desc_words[i : i + len(name_words)] == name_words:
            return True
    return False

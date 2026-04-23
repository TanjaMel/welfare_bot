import re


def normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def remove_noise(text: str) -> str:
    text = re.sub(r"[^\w\s.,!?]", "", text)
    return text


def is_spam(text: str) -> bool:
    if len(text) < 2:
        return True
    if len(set(text)) == 1:
        return True
    return False


def deduplicate(current: str, previous: list[str]) -> bool:
    return current in previous[-3:]
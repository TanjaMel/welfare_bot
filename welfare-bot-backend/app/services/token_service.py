from __future__ import annotations

from dataclasses import dataclass
import re


MAX_MESSAGE_LENGTH = 1500


@dataclass
class ValidationResult:
    is_valid: bool
    cleaned_text: str
    error: str | None = None
    warning: str | None = None


def normalize_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def is_spam_like(text: str) -> bool:
    stripped = text.strip()

    if len(stripped) < 2:
        return True

    if len(set(stripped.lower())) == 1 and len(stripped) > 6:
        return True

    if stripped.count("http") > 3:
        return True

    return False


def is_repeated_message(text: str, recent_user_messages: list[str]) -> bool:
    cleaned = normalize_text(text).lower()
    recent_cleaned = [normalize_text(item).lower() for item in recent_user_messages[-3:]]

    return cleaned in recent_cleaned


def validate_user_message(text: str, recent_user_messages: list[str]) -> ValidationResult:
    cleaned = normalize_text(text)

    if not cleaned:
        return ValidationResult(
            is_valid=False,
            cleaned_text="",
            error="Message is empty.",
        )

    if len(cleaned) > MAX_MESSAGE_LENGTH:
        return ValidationResult(
            is_valid=False,
            cleaned_text="",
            error=f"Message is too long. Maximum length is {MAX_MESSAGE_LENGTH} characters.",
        )

    if is_spam_like(cleaned):
        return ValidationResult(
            is_valid=False,
            cleaned_text="",
            error="Message looks invalid or spam-like.",
        )

    if is_repeated_message(cleaned, recent_user_messages):
        return ValidationResult(
            is_valid=False,
            cleaned_text="",
            error="Please avoid sending the exact same message repeatedly.",
        )

    return ValidationResult(
        is_valid=True,
        cleaned_text=cleaned,
    )
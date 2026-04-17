from __future__ import annotations

from dataclasses import dataclass
import re


MAX_MESSAGE_LENGTH = 500
MIN_MEANINGFUL_LENGTH = 2
MAX_REPEATED_CHAR_RUN = 8
MAX_WORD_REPEAT_RATIO = 0.7


@dataclass
class ValidationResult:
    cleaned_text: str
    is_valid: bool
    warnings: list[str]
    error: str | None = None


def normalize_message_text(text: str) -> str:
    """
    Basic normalization:
    - strip outer spaces
    - collapse repeated whitespace/newlines into single spaces
    """
    return " ".join(text.strip().split())


def has_excessive_repeated_characters(text: str) -> bool:
    """
    Detect cases like:
    'heyyyyyyyyyyyy'
    'aaaaaaa'
    '!!!!!'
    """
    return re.search(r"(.)\1{" + str(MAX_REPEATED_CHAR_RUN - 1) + r",}", text) is not None


def has_too_little_meaningful_content(text: str) -> bool:
    """
    Reject empty or almost empty content after cleanup.
    """
    return len(text.strip()) < MIN_MEANINGFUL_LENGTH


def has_high_word_repetition(text: str) -> bool:
    """
    Detect spammy repeated word patterns like:
    'help help help help help'
    """
    words = re.findall(r"\w+", text.lower())
    if not words:
        return False

    unique_words = set(words)
    most_common_count = max(words.count(word) for word in unique_words)
    repeat_ratio = most_common_count / len(words)

    return repeat_ratio >= MAX_WORD_REPEAT_RATIO and len(words) >= 4


def is_nearly_same_message(current_text: str, previous_text: str) -> bool:
    """
    Very simple duplicate detection based on normalized exact match.
    """
    return normalize_message_text(current_text).lower() == normalize_message_text(previous_text).lower()


def validate_user_message(
    text: str,
    recent_user_messages: list[str] | None = None,
) -> ValidationResult:
    recent_user_messages = recent_user_messages or []
    warnings: list[str] = []

    cleaned = normalize_message_text(text)

    if has_too_little_meaningful_content(cleaned):
        return ValidationResult(
            cleaned_text=cleaned,
            is_valid=False,
            warnings=[],
            error="Message is too short or empty.",
        )

    if len(cleaned) > MAX_MESSAGE_LENGTH:
        return ValidationResult(
            cleaned_text=cleaned,
            is_valid=False,
            warnings=[],
            error=f"Message is too long. Maximum length is {MAX_MESSAGE_LENGTH} characters.",
        )

    if has_excessive_repeated_characters(cleaned):
        return ValidationResult(
            cleaned_text=cleaned,
            is_valid=False,
            warnings=[],
            error="Message looks like spam or contains too many repeated characters.",
        )

    if has_high_word_repetition(cleaned):
        return ValidationResult(
            cleaned_text=cleaned,
            is_valid=False,
            warnings=[],
            error="Message looks repetitive and may be spam.",
        )

    if recent_user_messages:
        last_message = recent_user_messages[-1]
        if is_nearly_same_message(cleaned, last_message):
            warnings.append("This message is very similar to the previous one.")

    return ValidationResult(
        cleaned_text=cleaned,
        is_valid=True,
        warnings=warnings,
        error=None,
    )
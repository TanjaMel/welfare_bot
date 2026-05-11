from __future__ import annotations

from dataclasses import dataclass
import re

# ─────────────────────────────────────────────────────────────────────────────
# MESSAGE VALIDATION
#
# This module validates and cleans user messages before they are processed
# by the conversation pipeline and risk detection engine.
#
# It runs before every message is saved to the database or sent to OpenAI.
# The goal is to filter out empty, spam-like, or repeated messages early
# so the ML models and LLM only receive meaningful input.
# ─────────────────────────────────────────────────────────────────────────────

# Maximum allowed message length in characters.
# Long messages are rejected to prevent prompt injection attacks
# and to keep OpenAI API costs predictable.
MAX_MESSAGE_LENGTH = 1500


@dataclass
class ValidationResult:
    """
    The result of validating a single user message.

    Fields:
        is_valid     — True if the message passed all checks and can be processed
        cleaned_text — the normalised version of the message (whitespace cleaned)
        error        — human-readable error message if validation failed
        warning      — optional warning for edge cases that still pass validation
    """
    is_valid: bool
    cleaned_text: str
    error: str | None = None
    warning: str | None = None


def normalize_text(text: str) -> str:
    """
    Cleans whitespace from a message.

    - Strips leading and trailing whitespace
    - Collapses multiple spaces/newlines/tabs into a single space

    This ensures consistent comparison and length checking
    regardless of how the user formatted their input.
    """
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def is_spam_like(text: str) -> bool:
    """
    Detects messages that are invalid or spam-like.

    Three checks:
    1. Too short — less than 2 characters after stripping is not a real message
    2. Single repeated character — e.g. "aaaaaaa" or "........."
       Detected by checking if the set of unique characters has only 1 element
       and the message is longer than 6 characters.
    3. URL flooding — more than 3 URLs in one message suggests spam or
       prompt injection attempt.

    Returns True if the message should be rejected.
    """
    stripped = text.strip()

    # Check 1: too short to be meaningful
    if len(stripped) < 2:
        return True

    # Check 2: single repeated character (e.g. "aaaaaaaaaa")
    if len(set(stripped.lower())) == 1 and len(stripped) > 6:
        return True

    # Check 3: too many URLs — likely spam or injection attempt
    if stripped.count("http") > 3:
        return True

    return False


def is_repeated_message(text: str, recent_user_messages: list[str]) -> bool:
    """
    Checks if the user is sending the same message repeatedly.

    Compares the current message against the last 3 user messages.
    Both are normalised and lowercased before comparison so that
    minor whitespace differences do not bypass the check.

    This prevents users from spamming the same message and helps
    avoid duplicate risk analyses for identical content.
    """
    cleaned = normalize_text(text).lower()
    # Only check the last 3 messages — not the full history
    recent_cleaned = [normalize_text(item).lower() for item in recent_user_messages[-3:]]

    return cleaned in recent_cleaned


def validate_user_message(text: str, recent_user_messages: list[str]) -> ValidationResult:
    """
    Main validation function — runs all checks on a user message.

    Called before every message is processed by the conversation pipeline.
    Returns a ValidationResult with is_valid=False and an error message
    if any check fails, or is_valid=True with the cleaned text if all pass.

    Checks in order:
        1. Empty message
        2. Message too long (> 1500 characters)
        3. Spam-like content (too short, repeated characters, URL flooding)
        4. Exact duplicate of a recent message

    The cleaned_text in the result is always used downstream — never the
    raw input — to ensure consistent whitespace handling throughout the pipeline.
    """
    # Normalise first so all subsequent checks work on clean input
    cleaned = normalize_text(text)

    # Check 1: empty message after normalisation
    if not cleaned:
        return ValidationResult(
            is_valid=False,
            cleaned_text="",
            error="Message is empty.",
        )

    # Check 2: message exceeds maximum allowed length
    if len(cleaned) > MAX_MESSAGE_LENGTH:
        return ValidationResult(
            is_valid=False,
            cleaned_text="",
            error=f"Message is too long. Maximum length is {MAX_MESSAGE_LENGTH} characters.",
        )

    # Check 3: spam-like content
    if is_spam_like(cleaned):
        return ValidationResult(
            is_valid=False,
            cleaned_text="",
            error="Message looks invalid or spam-like.",
        )

    # Check 4: exact duplicate of a recent message
    if is_repeated_message(cleaned, recent_user_messages):
        return ValidationResult(
            is_valid=False,
            cleaned_text="",
            error="Please avoid sending the exact same message repeatedly.",
        )

    # All checks passed — return the cleaned text for further processing
    return ValidationResult(
        is_valid=True,
        cleaned_text=cleaned,
    )
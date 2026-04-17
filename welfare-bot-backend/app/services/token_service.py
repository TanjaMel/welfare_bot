from __future__ import annotations
from typing import Any
import tiktoken


def get_encoding_for_model(model_name: str):
    try:
        return tiktoken.encoding_for_model(model_name)
    except KeyError:
        # Safe fallback for unknown model names
        return tiktoken.get_encoding("o200k_base")


def count_text_tokens(text: str, model_name: str) -> int:
    encoding = get_encoding_for_model(model_name)
    return len(encoding.encode(text or ""))


def count_input_items_tokens(items: list[dict[str, Any]], model_name: str) -> int:
    """
    Approximate token count for our text-only input items.
    Good enough for trimming plain text chat history.
    """
    encoding = get_encoding_for_model(model_name)
    total = 0

    for item in items:
        role = str(item.get("role", ""))
        content = str(item.get("content", ""))

        total += len(encoding.encode(role))
        total += len(encoding.encode(content))

        # small structural overhead
        total += 4

    return total


def trim_input_items_to_token_budget(
    items: list[dict[str, Any]],
    model_name: str,
    max_input_tokens: int,
) -> list[dict[str, Any]]:
    """
    Keep the first item (developer/system prompt),
    then keep only the newest messages that fit the token budget.
    """
    if not items:
        return items

    if len(items) == 1:
        return items

    head = items[0]
    tail = items[1:]

    trimmed_tail: list[dict[str, Any]] = []

    # add newest first, then reverse back
    for item in reversed(tail):
        candidate = [head] + list(reversed([item] + list(reversed(trimmed_tail))))
        token_count = count_input_items_tokens(candidate, model_name)

        if token_count <= max_input_tokens:
            trimmed_tail.insert(0, item)
        else:
            break

    return [head] + trimmed_tail
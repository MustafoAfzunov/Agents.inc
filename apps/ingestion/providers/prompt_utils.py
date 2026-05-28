"""Helpers for parsing the rendered extraction prompt.

Both the offline providers (mock + spaCy) need to recover the article's
title / author / content from the prompt text the extractor builds. Keeping
the parser in one place avoids drift between providers.
"""
from __future__ import annotations

import re

_JSON_MARKER = "Return JSON with exactly this shape:"


def split_prompt(user_prompt: str) -> tuple[str, str, str]:
    """Split the rendered prompt into ``(title, author, content)``.

    The extractor renders prompts from a fixed template:

        Article URL: ...
        TITLE: <title>
        AUTHOR: <author>

        CONTENT:
        <content>

        Return JSON with exactly this shape:
        { ... }

    We isolate each region so the JSON-shape example never leaks into
    extraction and the header labels / author line can't be mistaken for
    article sentences.
    """

    text = user_prompt
    if _JSON_MARKER in text:
        text = text.split(_JSON_MARKER, 1)[0]

    title = ""
    author = ""
    title_match = re.search(r"^TITLE:\s*(.+)$", text, flags=re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
    author_match = re.search(r"^AUTHOR:\s*(.+)$", text, flags=re.MULTILINE)
    if author_match:
        author = author_match.group(1).strip()

    content = ""
    content_match = re.search(r"CONTENT:\s*(.*)$", text, flags=re.DOTALL)
    if content_match:
        content = content_match.group(1).strip()

    return title, author, content

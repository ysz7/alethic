"""Cutting a document into passages, in the domain because it decides recall.

Where the cut falls decides what a retrieved passage means: a chunk that ends
mid-sentence is quoted mid-sentence, and one that spans two sections answers
about neither. So this is a rule of the platform rather than a detail of a
store - and it is a pure function, which is what makes it testable without a
database and identical across backends.

Two decisions, each rejecting the simpler version.

**Cut on structure first, characters second.** Blank lines separate paragraphs
in every format the extractor produces, so passages are built by accumulating
paragraphs up to a size rather than by slicing the text at a fixed offset. A
paragraph longer than the budget on its own is split on sentence ends, and only
a sentence longer than the budget is cut mid-word - by then, the text is a
table or a minified file, and any cut is arbitrary.

**Overlap, because a fact can straddle a boundary.** The last part of one
passage begins the next, so a sentence naming the subject and the following
sentence stating the number are retrievable together whichever half matched.
"""

from __future__ import annotations

import re

#: About a page of text. Small enough that several passages fit in a run's
#: context beside everything else it carries, large enough to hold an argument
#: rather than a sentence.
DEFAULT_CHUNK_CHARS = 1_200
#: Roughly a paragraph of it, carried into the next passage.
DEFAULT_OVERLAP_CHARS = 160

_PARAGRAPH = re.compile(r"\n\s*\n")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _sentences(paragraph: str, limit: int) -> list[str]:
    parts: list[str] = []
    for sentence in _SENTENCE.split(paragraph):
        if len(sentence) <= limit:
            parts.append(sentence)
            continue
        # A "sentence" this long is not prose. Cut it, and say so by doing it
        # last rather than pretending the boundary means anything.
        parts.extend(
            sentence[index : index + limit] for index in range(0, len(sentence), limit)
        )
    return [part for part in parts if part.strip()]


def chunk(
    text: str,
    *,
    size: int = DEFAULT_CHUNK_CHARS,
    overlap: int = DEFAULT_OVERLAP_CHARS,
) -> list[str]:
    """Split extracted text into passages worth retrieving on their own."""
    if size <= 0:
        raise ValueError("A chunk has to have a size")
    overlap = max(0, min(overlap, size // 2))
    pieces: list[str] = []
    for paragraph in _PARAGRAPH.split(text.strip()):
        cleaned = paragraph.strip()
        if not cleaned:
            continue
        pieces.extend(_sentences(cleaned, size) if len(cleaned) > size else [cleaned])

    passages: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current}\n\n{piece}" if current else piece
        if len(candidate) <= size or not current:
            current = candidate
            continue
        passages.append(current.strip())
        tail = current[-overlap:].lstrip() if overlap else ""
        current = f"{tail}\n\n{piece}".strip() if tail else piece
    if current.strip():
        passages.append(current.strip())
    return passages

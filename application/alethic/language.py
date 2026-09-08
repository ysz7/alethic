"""The language the user is answered in, applied where the user is answered.

`ALETHIC_RESPONSE_LANGUAGE` has existed since Phase 2 and was honoured by
exactly one CLI command. Everything a person actually reads - what Alethic says
when a request needs no work, and the answer at the end of one that did - was
written in whatever language the model felt like, which for a request typed in
Russian is English. Phase 13 made that impossible to ignore: a conversational
window that replies in another language is not a conversation.

Two things this is deliberately not.

**Not a translation step.** Nothing is generated and then converted; the model
is told once, before it writes, and writes in that language. A translation pass
would be a second model call whose only job is to lose the specifics that
`Synthesizer` exists to keep.

**Not in the prompt files.** Prompts are English, like the rest of the codebase,
and the language a user is answered in is configuration - the rule the
English-only check states in so many words. So it arrives as a system message
beside the prompt, which is also where the CLI has always put it.
"""

from __future__ import annotations

from domain.llm.models import Message

#: What needs no instruction. The prompts are written in English, so a run
#: configured for English pays nothing - no extra message, no extra tokens.
DEFAULT_LANGUAGE = "en"


def instruction(language: str, *, about: str = "your answer") -> tuple[Message, ...]:
    """The system message telling a model what language to write for the user in.

    Empty for English, and empty is the point: this is a value most
    installations never set, and it should not add a line to every prompt to
    say so.

    `about` names the part that is for the user, because not everything a model
    returns here is: an intent reading is JSON whose keys and structure must
    stay as declared, and only one of its fields is a sentence anybody reads.
    """
    if not language or language.strip().lower() in (DEFAULT_LANGUAGE, "english"):
        return ()
    return (
        Message.system(
            f"Write {about} in {language.strip()}. "
            "Keep names, numbers, paths, links and any JSON keys or values "
            "that are not prose exactly as they are."
        ),
    )

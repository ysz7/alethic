"""Turning what an employee said into something worth remembering.

A finished task hands back the model's last message, and that message is written
to be read now, by the person who asked: it opens with "Perfect, I have
everything I need", it narrates what the employee is about to do, it ends with a
heading and a byte count. Stored as it stands, it is a transcript. Handed to the
next run as what this workspace knows, it reads as a record of somebody writing
reports - and the next plan is about writing a report.

That is not a hypothetical. It is what the second validation run did twice, with
two different models, and it is why one cheap model call per finished task is
worth making here when it is not worth making anywhere else in the recorder:
the alternative is not a slightly worse memory, it is a memory that misleads.

The fall-back matters as much as the call. A distiller that cannot be reached
returns the raw summary, trimmed - a memory that reads badly beats no memory,
and remembering must not be able to fail the work.
"""

from __future__ import annotations

import structlog

from application.prompts import render
from domain.capabilities.models import CapabilityRequirement
from domain.llm.models import LLMRequest, Message, RoutingHints, TaskKind
from domain.llm.protocols import LLM
from domain.tasks.task import Task

log = structlog.get_logger(__name__)

#: Two or three sentences. Long enough to carry a path, a schema and a number;
#: short enough that six of them still leave room for the work.
MAX_LENGTH = 600


class OutcomeDistiller:
    """One finished task in, one durable statement out."""

    def __init__(self, llm: LLM) -> None:
        self._llm = llm

    async def distil(self, task: Task, raw: str) -> str:
        if not raw.strip():
            return ""
        try:
            response = await self._llm.generate(
                LLMRequest(
                    messages=(
                        Message.user(
                            render(
                                "memory_outcome",
                                goal=task.goal,
                                status=task.status.value,
                                result=raw[:4000],
                            )
                        ),
                    ),
                    temperature=0.0,
                )
            )
        except Exception as error:
            log.warning("memory.distillation_failed", task_id=str(task.id), error=str(error))
            return raw
        distilled = " ".join(response.content.split())[:MAX_LENGTH]
        return distilled or raw

    @staticmethod
    def routing() -> tuple[TaskKind, CapabilityRequirement, RoutingHints]:
        """The cheapest model that can read a page and state what it found.

        EXTRACTION, like consolidation: this is housekeeping after somebody
        else's task, and it runs once per task, so its cost is paid by every
        run whether or not anything ever recalls it.
        """
        return (
            TaskKind.EXTRACTION,
            CapabilityRequirement(),
            RoutingHints(quality=0.4, cost_sensitivity=0.9),
        )

"""What a task needs from whoever takes it.

Routing was by capability alone until Phase 18, and a validation run showed
where that stops working. `Capability` is a closed vocabulary - it has to be,
because a model, a tool and an employee all declare into it and a term nobody
else understands routes nothing - and every one of its terms is already claimed
by somebody the platform ships with. So an integration the user connected can
only contribute a capability that four employees already declare: the notes
server is FILE_ACCESS, FILE_ACCESS is what reading a file needs, and the work
goes to whoever the delegating model liked the look of. It went to the one that
could run code, which searched for the notes with a script and was refused.

The fix is not a new capability term. It is that **a connected service is a
second axis of the same question**: what must this person be able to do, and
what must they hold. A service is named rather than enumerated, because the set
of them is whatever the user connected this morning.

Two rules keep it from becoming a way to route work nowhere:

**A service term is only kept if somebody holds it.** The planner reads the
names off the workforce cards, so an invented one is dropped exactly as an
invented capability is - a task routed imperfectly beats a task routed nowhere.

**It can only narrow.** Nothing here adds a candidate, and holding a service
grants no tool that the grant did not already grant.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from domain.capabilities.models import CapabilityRequirement
from domain.employees.definition import EmployeeDefinition

#: The floor under the model that chooses who does a task.
#:
#: Delegation used to be routed as cheap extraction - "picking from a short list
#: of cards, done once per task" - and on the local catalog that meant the
#: smallest entry in it. A Phase 18 run showed what that buys: the task "create
#: a short Markdown document at figures/comparison.md" was offered five
#: employees including one whose entire declaration is writing documents from
#: findings, and went to the one that had just done the analysis, with a reason
#: about data analysis. Every task in every plan went to the same person.
#:
#: It is a requirement rather than a hint for the same reason verification's is
#: (ADR 0003): hints only rank what survives the filter, and the configured
#: default beats them, so a default pointing at the cheapest entry keeps winning
#: the work it has just been shown unfit for. The choice cannot be undone
#: cheaply - it commits an entire employee run, its budget and its tools - which
#: is what separates it from the extraction work it was grouped with.
MIN_DELEGATION_QUALITY = 0.5


@dataclass(frozen=True, slots=True)
class Requirement:
    """The two things a task can ask of whoever takes it.

    Kept apart from `CapabilityRequirement` rather than added to it: that value
    is also what a piece of work asks of a *model*, and a model holds no
    connected services. One field there that is meaningless in half its uses is
    how a vocabulary stops being one.
    """

    capabilities: CapabilityRequirement = field(default_factory=CapabilityRequirement)
    #: Names of connected integrations whoever takes this must have been
    #: granted. Names, not values: the set is whatever this machine is
    #: connected to.
    services: frozenset[str] = field(default_factory=frozenset)

    @property
    def narrows(self) -> bool:
        """Whether this says anything at all about who should take the task."""
        return bool(self.capabilities.required) or bool(self.services)

    def describe(self) -> str:
        """Why a field of one is a field of one, in words a person reads."""
        parts = [item.value for item in sorted(self.capabilities.required)]
        parts += sorted(self.services)
        return ", ".join(parts)


def holders(
    definitions: Iterable[EmployeeDefinition], services: Iterable[str]
) -> list[EmployeeDefinition]:
    """Those granted every service named, in the order they arrived.

    A grant is the declaration, not the connection: an employee that names a
    service this machine cannot currently reach is still the right person for
    work that needs it, and will fail with a missing tool rather than with a
    plausible answer produced by the wrong route.
    """
    wanted = {name.strip().lower() for name in services if name.strip()}
    if not wanted:
        return list(definitions)
    return [
        definition
        for definition in definitions
        if wanted <= {name.lower() for name in definition.integrations}
    ]

"""The boundary every interface talks to.

A page, a terminal, a desktop shell and - later - a chat bot all want the same
six things: state a goal, watch it happen, answer a question, stop it, read what
happened before, and see who is available. Before Phase 13 those six lived in
`app/ui/`, above the application layer, which meant a second interface would
have had to reimplement them or import the first one's HTTP module.

They live here now. Nothing in this package knows about HTTP, SSE, a socket, a
window or a process boundary; it imports `domain/` and the rest of
`application/`, exactly like every other application module. What an adapter
adds is transport and nothing else.
"""

from application.interface.activity import Activity, ActivityEvent
from application.interface.contracts import (
    Attachment,
    InputType,
    RequestSource,
    UserRequest,
)
from application.interface.service import AlethicService

__all__ = [
    "Activity",
    "ActivityEvent",
    "AlethicService",
    "Attachment",
    "InputType",
    "RequestSource",
    "UserRequest",
]

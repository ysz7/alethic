"""Remembering and recalling, in the terms the work is done in.

Nothing here knows where memory is kept. It is reached through
`domain.memory.protocols.Memory`, which is the whole point of the phase: the
backend can be a table, an index or a vector store, and this layer does not
change (§9.9).
"""

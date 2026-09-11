# Workflows

A predefined process: named steps, each delegated to an employee, with declared
dependencies between them. Adding one is adding a file here - no Python, and no
change to any employee.

```bash
uv run prometheus workflows                      # what is declared, and whether it can run
uv run prometheus run-workflow <name> --input key=value
```

A step reads what earlier steps produced through `{steps.<name>}`, and the run's
inputs through `{key}`. `max_attempts` says how many times a step is worth
repeating - which depends on what it does, not on the engine - and
`on_failure: CONTINUE` says a step's failure is survivable. The default is to
stop, because the step after a failed one usually reads what it produced.

Everything below the decomposition is the same as for work Prometheus planned
itself: the same employees, the same limits, the same approval gate. A workflow
cannot do anything an employee could not have been asked to do directly.

Two ship as examples. `inbox-triage` is Phase 10's validation task - read what
came in, draft the replies, and stop before sending anything. `weekly-report` is
the shape most workflows have: gather, compute, write up.

Scheduled and event triggers are Phase 12; the vocabulary is already in
`domain/workflows/definition.py`, and only `MANUAL` runs today.

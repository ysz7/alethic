# Phase 13 validation - the window as the way in

**Capability under test:** the interface layer. Phase 13's Definition of Done is
a sentence about a person again: *a person opens Prometheus, says what they need,
and the platform does it* - through a surface that is an adapter over one
application-level boundary rather than a second copy of the platform.

So there are two things to establish, and they fail differently. Does a request
that arrives through the interface path reach real work and come back with a
real result? And does the packaged window itself talk to a real runtime? The
first is about the boundary; the second is about the shell, and nothing in the
test suite can see it.

## How it was run

Against local models, so the phase could be validated without a provider key:

```bash
export PROMETHEUS_MODEL_CATALOG_PATH=infrastructure/llm/models.local.toml
uv run alembic upgrade head
uv run prometheus serve                                   # the runtime
./desktop/src-tauri/target/release/prometheus-desktop      # the window
```

The workspace held one file, `notes/standup.md` - eleven lines of meeting notes
recording three decisions.

## 1. A request through the interface path - passed, 2026-09-08

Driven over exactly the HTTP and server-sent events the window uses: open a
conversation, post one message with `source: desktop`, subscribe to
`/api/events?objective=...`, read the answer back off the thread.

> Read notes/standup.md and leave me notes/summary.md: a short Markdown list of
> the decisions it records. Do not change the original file.

**DONE in 113 seconds.** 30 model calls, 32,752 prompt tokens, 4,549 output
tokens, $0.00 (local). 36 events on the stream.

What actually happened, and the interesting part is that it did not go straight:

| | |
|---|---|
| Acceptance criteria, written before the work | "Provide a Markdown list summarizing decisions from notes/standup.md", "Do not change original file" |
| Plan revision 1 | one task - FAILED verification: *"fails to demonstrate that the source file was actually read"* |
| Plan revision 2 | two tasks - extract the decisions, then write the file. Both COMPLETED |
| Tool calls | `fs.read` ×3, `fs.write` ×1 (`notes/summary.md`, 112 bytes, `overwritten: false`) |
| Approvals | none - a new file is LOW risk, and nothing else touched the world |
| Result on disk | three decisions, correctly extracted; `notes/standup.md` byte-identical |

The replanning is the platform behaving as designed and is visible in the trace
the window draws: a verdict against the objective's own criteria sent the work
back once, and the second attempt was accepted. A person watching the window saw
the manager change its mind, which is the thing a log-free surface is for.

## 2. The packaged window against a real runtime - passed, 2026-09-08

The built application, started with no arguments, against a runtime already
serving on the default address:

```
POST /api/conversations   ×1     opened a thread
GET  /api/employees       ×1     drew the workforce
GET  /api/approvals       ×4     polling for anything waiting on the person
```

No problems reported. The window renders - greeting, composer, workforce panel -
and its own code drives the same endpoints the browser page does.

## 3. A person typing into the window - passed, 2026-09-08

The developer typed `Hello` into the field and got an answer back in the window.
The capability the phase exists for is therefore confirmed by a person, not by a
harness. What that person got, however, was bad enough to be its own finding.

## 4. What "Hello" cost before it was fixed

`Hello`, typed into the window, produced:

| | |
|---|---|
| Constraints, invented | `{"format": "a file", "where": "somewhere named"}` |
| Acceptance criteria | two, about the shape of the reply rather than the request |
| Plans | two revisions |
| Delegated to | `analyst` |
| Written to disk | `request_documentation.txt` - for a greeting |
| Time | 92 seconds |

The constraints are the tell: they are the *example values from the prompt*,
copied verbatim. `prompts/prometheus_intent/v2.md` showed
`{"count": 20, "format": "a file", "where": "somewhere named"}` as an
illustration, and the model returned it as its answer. That is the first
validation run's third finding exactly - the one that made the v2 verification
prompts show an empty form - still present in the prompt that reads every
request the platform receives.

**Fixed** by `prompts/prometheus_intent/v3.md` (digest `5597e2e6`): an empty form
rather than a filled example, and a section saying in so many words that not
everything said to a manager is work. `tests/unit/test_prompt_forms.py` now
fails the build on any current prompt that shows a value a model could copy -
and found the same trap in five more prompts, listed there as a queue rather
than fixed blind, because each of those forms is what a weak model leans on to
produce a shape at all and changing them is a behaviour change to be measured.

Afterwards, on the same local model:

| Typed | Before | After |
|---|---|---|
| `privet` (Russian for "hello") | 92 s, 2 plans, a file on disk | **18 s, no plan, no file, no invented constraints** |
| the same, plus "what can you help with?" | - | 42 s, still one plan, but a correct answer and nothing written |
| "thank you!" | - | 50 s, still one plan, correct answer, nothing written |

The two remaining plans are a model limit, not a platform one: the reading is
`needs_work: true` for small talk that a stronger model classifies correctly.
Nothing is delegated that touches anything, nothing is written, and no criteria
are invented - the damage the first run did is gone. Worth re-measuring on the
shipping catalog before deciding whether more prompt work is warranted.

## 5. The language the user is answered in

`PROMETHEUS_RESPONSE_LANGUAGE` has existed since Phase 2 and was honoured by
exactly one CLI command (`prometheus ask`). The manager - which writes the answer
every user of the window and the page actually reads - never saw it. A request
typed in Russian came back in English, and the setting documented a behaviour
the product did not have.

**Fixed** in `application/prometheus/language.py`: the instruction is a system
message beside the prompt, applied where the user is answered - `IntentReader`
(its `answer` field only, because a restatement in another language would reach
the planner rather than the person) and `Synthesizer` (all of it). English adds
no message at all, so the default costs nothing. Verified on the local model:
setting the language returns answers in it.

## What this found that the tests did not

Nine defects, none of which any green test could have seen, because every one of
them lives in a gap between parts that each believed the other was handling:

1. **`PROMETHEUS_BASE_URL` was a lie.** The shell read it; the page hard-coded the
   default. Documented, tested, and wrong. The window now asks the shell where
   the runtime is (`resolveBaseUrl`), because the shell is the only one that
   knows.
2. **The CSP named one port.** `ui_port` is a setting, so a window pointed at
   any other runtime was blocked before the request left the page.
3. **CORS did not include the packaged window's origin.** A built application
   serves its page from `tauri://localhost`; the allow-list held only the
   development port. Every `npm run dev` session worked and every shipped one
   would not - the shape of bug that reaches a user.
4. **The runtime was started twice.** `ensure` asked "is anything answering"
   and got "no" twice in the second it takes to bind a port. The second engine
   could only fail with *address already in use*. It now remembers its own child.
5. **A packaged window cannot reach `http://127.0.0.1` from its own page at
   all.** WebKit refuses it before the network, which is why the runtime's log
   stayed empty while the window said only "Load failed". Requests now go
   through the shell (`tauri-plugin-http`, scoped to loopback in
   `capabilities/default.json`), and the event stream is read off the response
   body rather than through `EventSource` - one transport for both, in the one
   file that is allowed to know what the transport is.
6. **The window asked before the engine was listening.** It started a runtime,
   asked it a question half a second later, got a closed socket, and never tried
   again. The shell now waits for readiness before telling the page where to
   talk - it started the process, so it is the one that knows.
7. **A window that fails says nothing.** Every failure was caught and turned
   into one friendly sentence, identical for a transport error, a missing
   schema and an absent runtime. `describe` now reports what actually happened,
   and the page tells the shell, which prints it where whoever started it can
   read it. This is what turned the five preceding items from guesses into
   findings.

8. **The prompt that reads every request showed a filled example**, and a model
   copied it into a greeting's constraints. See §4.
9. **The manager ignored the response language.** See §5.

The first seven are the same shape: a boundary that both sides believed the
other was handling. The last two are the other shape this phase was built to
expose - a surface being used the way a person uses it, where "obviously fine"
turns out to be neither. That is what §1.2 means by real work being worth more than a
green suite - and it is the argument for this phase existing at all, since a
second interface would have hit all seven again.

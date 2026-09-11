# Phase 17 validation - a provider somebody added, doing the work

**Capability under test:** the model catalog stops being a file only a developer
edits. A person adds a way in to a provider, gives it a key, picks a model from
what that provider actually has, and says which kind of work goes to it - and
the next run uses exactly that.

**What would count as done, written before the run:** a provider added through
the platform's own boundary, one kind of work routed to a model reached through
it, and the recorded calls showing that model answering - not the summary
saying so.

## How it was run

Through the CLI, which is the same application service the settings window
calls, on a machine whose only local runner is Ollama:

```bash
uv run prometheus provider-add local-runner --kind local \
  --base-url http://127.0.0.1:11434/v1
uv run prometheus model-add picked-strong --model gemma4:31b-cloud \
  --connection local-runner --capabilities TEXT_REASONING,TOOL_CALLING,...
uv run prometheus model-add picked-small --model lfm2:24b --connection local-runner
uv run prometheus send-work-to planning picked-strong    # and execution, synthesis,
uv run prometheus send-work-to verification picked-small # conversation, extraction
uv run prometheus ask-prometheus "What is the capital of Australia?"
```

Nothing in that sequence names a file. `models.toml` was not edited, and
`PROMETHEUS_MODEL_CATALOG_PATH` was deliberately not set - the catalog came from
the store.

## What happened

The run went through, and `llm_calls` says what answered:

    local  gemma4:31b   x8    (planning, execution, synthesis, conversation)
    local  lfm2:24b     x10   (verification, extraction)

Two models, both added minutes earlier by a person, both reached through a
connection that did not exist when the platform started. That is the phase.

**The objective itself escalated**, and that is not this phase's failure: a 24B
model read "what is the capital of Australia" as work and produced a plan. It is
the same limit Phase 16 recorded and the reason the plan says to measure small
talk on the shipped catalog.

## What the run found that the tests did not

**A model nothing can reach was still a candidate.** One call in the first run
went to a shipped hosted entry and came back 401. The mechanism: verification
declares a quality floor as a *requirement*, the floor filtered out the routed
entry, and the hints then ranked an entry whose provider needs a key. Every unit
test passed, because no unit test knows which entries this machine can call.

Fixed in `StoredCatalogSource`: an entry is dropped from the catalog when
nothing can reach it - a connection that is missing or has no credential, a
provider this build has no adapter for, or a hosted entry on a machine with no
configured key. **The row is not deleted.** It is the user's, Settings still
lists it, and it comes back the moment a key is added. Routing and listing are
different questions and this is the one place where they had been the same.

**And the second finding is the phase's own reason for existing.** The two
failed calls that remained were not a defect: this machine's `.env` carries
`PROMETHEUS_LLM_API_KEY=sk-ant...` while `llm_base_url` points at OpenRouter and
the shipped entries are OpenRouter entries. One key and one address for every
provider is exactly the arrangement Phase 17 replaces, and the platform had been
quietly failing that way for as long as the file has looked like that.

## What is not tested here

Adding a provider through the *window* rather than through the CLI. Both call
the same `ProviderService` through the same interface boundary, and
`tests/e2e/test_provider_settings.py` exercises the HTTP path end to end -
including that no response body ever contains a key, and that what lands in the
database does not contain one either. What has not happened is a person doing it
with a mouse, which belongs to Phase 20.

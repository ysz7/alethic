# What Prometheus can actually do

Generated from 106 recorded run(s) on 2026-09-09 by `prometheus validation-report`. Every line below is a verdict on scenarios declared in `validation/scenarios/`, measured against criteria written before each run.

- Completed to the stated standard: **58%** of attempts
- Spent across every attempt: **$0.0000**
- Times a person had to answer something: **116**

## Works reliably

Every recorded attempt met the criteria written before it, and there was more than one attempt.

- `nothing-sent-without-consent` - 8/8 passed, median 3 step(s)
- `answer-from-a-document` - 5/5 passed
- `knowledge-stays-in-its-workspace` - 5/5 passed

## Works sometimes

It has done this and it has failed to do this - or it has done it exactly once, which is the same state of knowledge.

- `research-from-the-web` - 8/9 passed, median 4 step(s), usually MODEL
- `sort-a-folder` - 5/9 passed, median 5 step(s), usually MODEL
- `answer-a-question` - 8/9 passed, usually NEEDED_APPROVAL
- `state-a-goal` - 5/9 passed, median 6 step(s), usually MODEL
- `compute-from-a-csv` - 3/9 passed, median 5 step(s), usually MODEL
- `remember-what-was-learned` - 2/8 passed, median 9 step(s), usually NEEDED_APPROVAL
- `triage-an-inbox` - 4/8 passed, median 10 step(s), usually MODEL
- `a-team-on-one-objective` - 7/18 passed, median 7 step(s), usually NEEDED_APPROVAL
- `use-a-connected-service` - 1/9 passed, median 4 step(s), usually MODEL

## Not available on this machine

Skipped: a capability the scenario needs is switched off here.

- `operate-a-screen`

## What went wrong, by kind

The list the roadmap is argued from: the categories at the top are where the next piece of work is, whatever was planned instead.

- **NEEDED_APPROVAL** x21 - the brake held and nobody was there to answer
- **MODEL** x17 - the model lost the thread, or the provider did
- **PLANNING** x5 - the decomposition was wrong or absent
- **TOOL** x1 - a tool was reached for and did not do its job
- **EXPECTATION** x1 - it finished, and produced something other than what was asked

## The regression set

Scenarios that have passed here at least once. Each is expected to keep passing; `prometheus validate --regression` runs exactly these.

- `research-from-the-web`
- `sort-a-folder`
- `answer-a-question`
- `state-a-goal`
- `compute-from-a-csv`
- `remember-what-was-learned`
- `nothing-sent-without-consent`
- `triage-an-inbox`
- `a-team-on-one-objective`
- `use-a-connected-service`
- `answer-from-a-document`
- `knowledge-stays-in-its-workspace`

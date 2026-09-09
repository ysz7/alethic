# What Alethic can actually do

Generated from 77 recorded run(s) on 2026-09-09 by `alethic validation-report`. Every line below is a verdict on scenarios declared in `validation/scenarios/`, measured against criteria written before each run.

- Completed to the stated standard: **62%** of attempts
- Spent across every attempt: **$0.0000**
- Times a person had to answer something: **55**

## Works reliably

Every recorded attempt met the criteria written before it, and there was more than one attempt.

- `nothing-sent-without-consent` - 7/7 passed, median 3 step(s)
- `answer-from-a-document` - 4/4 passed
- `knowledge-stays-in-its-workspace` - 4/4 passed

## Works sometimes

It has done this and it has failed to do this - or it has done it exactly once, which is the same state of knowledge.

- `research-from-the-web` - 7/8 passed, median 4 step(s), usually MODEL
- `sort-a-folder` - 5/8 passed, median 5 step(s), usually MODEL
- `answer-a-question` - 7/8 passed, usually NEEDED_APPROVAL
- `state-a-goal` - 5/8 passed, median 6 step(s), usually MODEL
- `compute-from-a-csv` - 3/8 passed, median 5 step(s), usually NEEDED_APPROVAL
- `remember-what-was-learned` - 1/7 passed, median 9 step(s), usually NEEDED_APPROVAL
- `triage-an-inbox` - 3/7 passed, median 9 step(s), usually MODEL
- `a-team-on-one-objective` - 2/4 passed, median 9 step(s), usually NEEDED_APPROVAL

## Does not work

Attempted here and never once finished to the standard set beforehand.

- `use-a-connected-service` - 0/4 passed, median 16 step(s), usually NEEDED_APPROVAL

## Not available on this machine

Skipped: a capability the scenario needs is switched off here.

- `operate-a-screen`

## What went wrong, by kind

The list the roadmap is argued from: the categories at the top are where the next piece of work is, whatever was planned instead.

- **NEEDED_APPROVAL** x15 - the brake held and nobody was there to answer
- **MODEL** x11 - the model lost the thread, or the provider did
- **PLANNING** x2 - the decomposition was wrong or absent
- **EXPECTATION** x1 - it finished, and produced something other than what was asked

## The regression set

Scenarios that have passed here at least once. Each is expected to keep passing; `alethic validate --regression` runs exactly these.

- `research-from-the-web`
- `sort-a-folder`
- `answer-a-question`
- `state-a-goal`
- `compute-from-a-csv`
- `remember-what-was-learned`
- `nothing-sent-without-consent`
- `triage-an-inbox`
- `a-team-on-one-objective`
- `answer-from-a-document`
- `knowledge-stays-in-its-workspace`

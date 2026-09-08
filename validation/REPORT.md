# What Alethic can actually do

Generated from 24 recorded run(s) on 2026-09-08 by `alethic validation-report`. Every line below is a verdict on scenarios declared in `validation/scenarios/`, measured against criteria written before each run.

- Completed to the stated standard: **50%** of attempts
- Spent across every attempt: **$0.0000**
- Times a person had to answer something: **0**

## Works reliably

Every recorded attempt met the criteria written before it, and there was more than one attempt.

- `research-from-the-web` - 3/3 passed, median 4 step(s)
- `nothing-sent-without-consent` - 3/3 passed, median 3 step(s)

## Works sometimes

It has done this and it has failed to do this - or it has done it exactly once, which is the same state of knowledge.

- `sort-a-folder` - 2/3 passed, median 5 step(s), usually NEEDED_APPROVAL
- `answer-a-question` - 3/4 passed, usually NEEDED_APPROVAL
- `state-a-goal` - 1/3 passed, median 5 step(s), usually NEEDED_APPROVAL

## Does not work

Attempted here and never once finished to the standard set beforehand.

- `compute-from-a-csv` - 0/3 passed, median 16 step(s), usually NEEDED_APPROVAL
- `remember-what-was-learned` - 0/3 passed, median 11 step(s), usually NEEDED_APPROVAL
- `triage-an-inbox` - 0/2 passed, median 6 step(s), usually NEEDED_APPROVAL

## Not available on this machine

Skipped: a capability the scenario needs is switched off here.

- `operate-a-screen`

## What went wrong, by kind

The list the roadmap is argued from: the categories at the top are where the next piece of work is, whatever was planned instead.

- **NEEDED_APPROVAL** x8 - the brake held and nobody was there to answer
- **MODEL** x2 - the model lost the thread, or the provider did
- **PLANNING** x1 - the decomposition was wrong or absent
- **EXPECTATION** x1 - it finished, and produced something other than what was asked

## The regression set

Scenarios that have passed here at least once. Each is expected to keep passing; `alethic validate --regression` runs exactly these.

- `research-from-the-web`
- `sort-a-folder`
- `answer-a-question`
- `state-a-goal`
- `nothing-sent-without-consent`

# ADR 0019: The platform is called Prometheus, and the old name is read but never written

## Status

Accepted - 2026-09-11

## Context

The platform shipped for eighteen phases as Alethic, and it is now Prometheus:
the command, the package, the manager, the window, the environment variables,
the data directory and every sentence that names it. This is the second rename;
the first (KAI to Alethic) is migration 008.

A rename of a product is a text replacement everywhere except in three places,
and those three are where it can do damage without anybody noticing:

- **Values written into rows.** `ActorKind` and `TaskCreatedBy` are StrEnums
  whose values are stored. A database made before the rename holds `ALETHIC`
  and `alethic`, and `audit_log` has a CHECK constraint (since 009) listing the
  actor kinds by value - so after a naive rename the old rows fail to read and
  the first audit line the manager writes is refused by the database.
- **Settings a person already wrote down.** A machine set up before the rename
  has `ALETHIC_*` in its `.env`: the provider key, the data directory, and on a
  server the master key that opens every stored credential.
- **Files a person already has.** `~/.alethic/alethic.db` is the whole history
  of that machine's work, and `~/.alethic/master.key` decrypts the credentials
  stored in it.

## Decision

**Rows are rewritten; the enums do not keep an alias.** Migration 022 does what
008 did, plus the one thing 008 did not need: it drops the CHECK constraint,
rewrites the rows, and puts the constraint back with the new list - in that
order, because on SQLite putting it back rebuilds the table and a row still
holding the old value would stop the rebuild. History that is prose - an
answer, a memory, a log line - keeps the name it was written under.

**The old names are read as a fallback, below the new ones, and never
written.** `Settings` has two more sources after the current ones: the
environment and the `.env` file under the `ALETHIC_` prefix. The old aliases
for the file root are still accepted, as `WORKSPACE_DIR` already was.
`ALETHIC_SECRET_<NAME>` is looked up between the current prefix and the bare
name. Where both a new and an old name are set, the new one wins.

**Nothing is moved.** The default data directory is `~/.prometheus`, unless it
does not exist and `~/.alethic` does; the database is `prometheus.db`, unless it
does not exist and `alethic.db` does. The platform works in the old place until
a person moves the files, and from the moment the new ones exist it uses them.

## Consequences

- An installation from before the rename starts after `alembic upgrade head`
  (which `start.sh` runs) with its history, its key and its credentials, and
  nothing on screen about any of it.
- The string `alethic` survives in exactly four places: migrations 008 and 009,
  which are history, migration 022, which is the rename, and the fallback in
  `app/config/settings.py` and `infrastructure/secrets/env.py`. The fallback is
  deliberately small enough to delete in one change once no installation needs
  it; `tests/unit/test_the_name_before_prometheus.py` says what it promises.
- Past validation reports now read "Prometheus" where they were written under
  the old name. They describe the same system, and a report whose prompt names
  (`prometheus_verifier/v3`) no longer matched the files would be worse.

## Alternatives considered

**Move `~/.alethic` to `~/.prometheus` on first start.** Cleaner, and it acts on
a person's files without asking - including the master key, where a failure
halfway leaves stored credentials that nothing on the machine can open.

**Keep the old enum values under the new names** (`PROMETHEUS = "ALETHIC"`).
No migration, and a stored token that names a product that no longer exists,
forever; 008 already rejected this shape once.

**Rename only what a person sees.** The window and the prose would say one
name and the command, the variables and the database another - which is two
names, and the next person to read the code would have to learn both.

## Update - the same day: the fallback is gone

The one installation that needed it was this machine, and it has moved:
`~/.alethic` became `~/.prometheus`, `alethic.db` became `prometheus.db`, and
the `.env` keys were renamed. With nothing left to read the old names from, the
fallback in `app/config/settings.py` and `infrastructure/secrets/env.py` was
deleted in one change, as the Consequences above said it could be, along with
the test that described it. An installation from before the rename now has to
do the same three things by hand; migration 022 still carries its rows.

`alethic` survives only in migrations 008, 009 and 022, which are history.

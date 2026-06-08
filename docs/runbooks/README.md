# Runbooks

Operational procedures for the GB10 single-node deployment. To be written alongside the
relevant epics:

- **deploy.md** — Docker Compose deploy / upgrade / rollback (PRD2 §13.1, epic E12).
- **backup-restore.md** — Postgres backup + vector-DB snapshot/restore drill (PRD2 §10.2
  "Vector DB snapshot restore monthly"; epic E3 GB10).
- **release-gate.md** — eval gate, smoke tests, continuous verification thresholds
  (PRD2 §13, `tests/eval/thresholds.toml`).

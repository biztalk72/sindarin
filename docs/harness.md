# Hybrid IDP — Harness Framework / 하네스 프레임워크

> Practical operating manual for the file-based AI-collaboration framework.
> Source of intent: `docs/prd.md`. Project guidance: `CLAUDE.md`. Architecture: `docs/architecture/overview.md`.

---

## 1. What the Harness Is / 하네스란 무엇인가

**EN:** The harness is a lightweight, file-based control loop that gives AI collaborators (Claude via Warp/Oz, or any LLM agent) a shared memory and a clear notion of "current work state." It is **not** a separate binary or CLI — it is a set of conventions and config files that structure how work is planned, tracked, and recorded.

Concretely:

- **`harness.toml`** — project config: safety permissions, sandbox rules, hook definitions.
- **`Plans.md`** — work ledger with explicit task states (`cc:TODO` / `cc:WIP` / `cc:完了`).
- **`.claude/memory/`** — persistent memory: ADRs (`decisions.md`), reusable patterns (`patterns.md`), session log (`session-log.md`).
- **`.claude-plugin/`** — generated runtime config derived from `harness.toml` + `hooks/hooks.json`. Do not hand-edit.
- **`hooks/hooks.json`** — hook definitions (extend as needed).

The harness is intentionally minimal. It does not replace your IDE, your CI, or your repo — it gives AI collaborators memory and a shared notion of "what is the current state of the work."

**KO:** 하네스는 AI 협업자(Warp/Oz의 Claude, 또는 기타 LLM 에이전트)에게 공유 메모리와 "현재 작업 상태"의 명확한 정의를 부여하는 가벼운 파일 기반 제어 루프다. 별도의 바이너리나 CLI가 **아니라**, 작업의 계획·추적·기록을 구조화하는 규약과 설정 파일의 집합이다.

---

## 2. File Layout / 파일 배치

```
hybrid-IDP/
├── CLAUDE.md                  # always-loaded project guidance (~87 lines)
├── Plans.md                   # work ledger
├── backlog.md                 # post-launch follow-ups (prioritized)
├── harness.toml               # harness config (you edit this)
├── hooks/
│   └── hooks.json             # hook definitions (source of truth)
├── .claude/
│   ├── memory/
│   │   ├── decisions.md       # SSOT for ADRs (6 accepted)
│   │   ├── patterns.md        # reusable solutions / idioms
│   │   └── session-log.md     # per-session work log
│   └── settings.local.json    # local user overrides (gitignored)
├── .claude-plugin/            # ★ generated — do not hand-edit
│   ├── plugin.json
│   ├── hooks.json
│   └── settings.json
├── docs/
│   ├── prd.md                 # PRD (intent)
│   ├── harness.md             # ← you are here
│   ├── architecture/          # overview + per-component design docs
│   ├── runbooks/              # aws-deploy, backup, release-gate
│   └── _archive/              # superseded partner-first SaaS docs
├── api/                       # FastAPI app (product code)
├── ui/                        # Next.js app (chat + admin dashboard)
├── sdk/                       # client SDK + web component
├── ops/                       # docker-compose, Makefile, aws/ buildspecs
└── tests/                     # unit, integration, e2e, eval regression
```

**Rules / 규칙:**
1. Edit `harness.toml`, `hooks/hooks.json`, `Plans.md`, and `.claude/memory/` files directly.
2. Never hand-edit `.claude-plugin/` — it is derived state.
3. `CLAUDE.md` is loaded into every AI conversation. Keep it lean; link to `docs/` for detail.

---

## 3. Setup / 셋업

### Prerequisites / 사전 요건

- Git repository cloned
- Python 3.12+ with `uv` for the API
- Node.js 20+ for the UI
- Docker (or Colima) for local Postgres + MinIO

### Bootstrap / 부트스트랩

```bash
# 1. Install API deps
make -C ops install

# 2. Start local Postgres + MinIO
make -C ops dev-up
make -C ops db-upgrade

# 3. Validate (full test suite)
make -C ops test

# 4. Start the API
uv run uvicorn api.main:app --reload --port 8000

# 5. Start the UI (separate shell)
cd ui && pnpm install && pnpm dev
```

No separate "harness" binary is needed — the harness is the file conventions + config described here.

---

## 4. Operating Loop / 운영 루프

**EN:** Day-to-day work follows a four-step cycle:

```
Plan  →  Implement  →  Verify  →  Record
```

| Step | What happens | Key files |
|---|---|---|
| **Plan** | Pick or add a `cc:TODO` in `Plans.md`. Check ADRs + patterns. | `Plans.md`, `.claude/memory/decisions.md` |
| **Implement** | Mark `cc:WIP`. Write code + tests. | `api/`, `ui/`, `tests/` |
| **Verify** | Run `uv run pytest`, `ruff check`, `mypy`. Check eval thresholds. | `tests/`, `Makefile` |
| **Record** | Mark `cc:完了`. Add ADR if non-obvious choice. Update session log. | `Plans.md`, `.claude/memory/` |

**KO:** 일상 작업은 네 단계 사이클을 따른다: 계획 → 구현 → 검증 → 기록.

### Verification commands / 검증 명령

```bash
uv run pytest -q                    # full test suite
uv run ruff check api tests          # lint
uv run mypy                          # type check
cd ui && npm run typecheck           # UI types
cd sdk && npm test                   # SDK tests
make eval-gate-deep                  # eval regression (CI gate)
```

---

## 5. Plans.md Conventions / Plans.md 규약

`Plans.md` is the work ledger. Format:

- **Open**: `- [ ] cc:TODO — <id> <description>`
- **In flight**: `- [ ] cc:WIP — <id>`
- **Done**: `- [x] cc:完了 — <id>`
- **IDs**: `<phase>-<bucket><nn>` — e.g. `P0-S01` (Phase 0 / Scaffolding / 01)
- Tasks live under phase headings matching the PRD release sequence
- When `Plans.md` exceeds ~200 lines, archive completed phases to `.claude/memory/archive/`

Current state: Phases 0–5 complete (107 tasks archived). Phase 6 has 3 remaining operator-tier tasks.

---

## 6. Memory System / 메모리 시스템

Three files, three jobs:

| File | Write when | Content |
|---|---|---|
| `decisions.md` | Non-obvious architectural choice | ADR: Context / Decision / Consequences / Reversibility (bilingual) |
| `patterns.md` | Solution used in 2+ places | Pattern name, when to use, code shape, anti-patterns |
| `session-log.md` | Each work session | Date, scope, changed files, key decisions, handoff notes |

**Promotion rules:**
- A pattern cited by an ADR stays in `patterns.md`; the ADR links to it.
- A "decision" without trade-offs is documentation → put it under `docs/`.
- Session log entries are never promoted — they stay as historical record.

---

## 7. Hooks / 훅

Source of truth: `hooks/hooks.json`. Currently empty — hooks should be added deliberately.

**Recommended hooks (not yet enabled):**

| Hook type | Trigger | Action |
|---|---|---|
| `PostToolUse` | `harness.toml` edited | Regenerate `.claude-plugin/` |
| `PreCommit` | `api/routers/` or `api/models/` touched | Run contract tests |
| `PostUserPrompt` | Task crosses AWS + local boundaries | Warn if no `ops/` change in plan |

To add a hook, edit `hooks/hooks.json`, then manually copy changes to `.claude-plugin/hooks.json` or regenerate.

---

## 8. Safety & Permissions / 안전·권한

Defined in `harness.toml`:

- **`deny`**: hard-blocked — `sudo:*`, `rm -rf /:*`
- **`ask`**: prompts user — `rm -r:*`, `git push --force[*]`, `terraform destroy:*`, `aws iam:*`, `kubectl delete:*`
- **`denyRead`**: secrets — `.env`, `.env.*`, `secrets/**`, `**/credentials/**`, `**/*.pem`, `**/*.key`
- **`allowRead`**: `.env.example` (read the schema, not values)

When adding high-blast-radius tools (e.g. DB migration commands), add them to `ask` proactively.

---

## 9. Commit & PR Conventions / 커밋·PR 규약

Conventional Commits with scope:

| Prefix | Scopes |
|---|---|
| `feat` | `api`, `ui`, `ingest`, `pageindex`, `models`, `chat`, `guardrails`, `eval`, `admin`, `auth`, `ops`, `infra` |
| `fix` | same as `feat` |
| `docs(adr)` | ADR acceptance |
| `chore` | dependencies, tooling |

**PR rules:**
- API contract changes → update UI client in the same PR
- New model → capability descriptor + connection test
- New parser → fixture + e2e test in `tests/e2e/`
- No vendor-SDK imports in `api/` (CLAUDE.md §2)
- No vector DBs or embedding services (CLAUDE.md §2)

---

## 10. Common Workflows / 흔한 작업 흐름

### Pick up a task and ship it

```bash
# 1. Check what's open
grep "cc:TODO" Plans.md

# 2. Pick a task, mark cc:WIP in Plans.md
# 3. Implement + test
uv run pytest -q
uv run ruff check api tests

# 4. Commit
git add -A && git commit -m "feat(scope): description"

# 5. Mark cc:完了 in Plans.md
```

### Check project status

```bash
grep -c "cc:TODO\|cc:WIP\|cc:完了" Plans.md
uv run pytest -q --tb=no
git --no-pager log --oneline -10
```

### Capture a decision

Edit `.claude/memory/decisions.md` with the four-section ADR template: Context / Decision / Consequences / Reversibility. Bilingual: EN first, then KO.

### Deploy to AWS

Follow `docs/runbooks/aws-deploy.md` — reproducible procedure for ECS Fargate + RDS + S3 in ap-northeast-2 (Seoul).

### Release

```bash
# Tag + GitHub Release
git tag v1.x.x && git push --tags
gh release create v1.x.x --title "v1.x.x" --notes-file CHANGELOG.md
```

See `docs/runbooks/release-gate.md` for the eval-gate procedure.

---

## 11. Automation Opportunities / 자동화 기회

Concrete next steps to extend the harness:

1. **CI eval regression** — wire `make eval-gate-deep` into GitHub Actions on PRs touching `api/chat/`, `api/eval/`, or `api/guardrails/`.
2. **Plans.md drift detector** — pre-commit hook that warns when `cc:WIP` tasks are stale >24h.
3. **Session log auto-append** — on each commit, append a summary line to `.claude/memory/session-log.md`.
4. **ADR linter** — validate every ADR has all four required sections + an index entry.
5. **OpenAPI contract sync** — CI check that `ui/lib/` generated client matches the current FastAPI OpenAPI spec.

---

## 12. References / 참조

- **Product requirements** → `docs/prd.md`
- **Architecture** → `docs/architecture/overview.md` + per-component docs
- **AWS deployment** → `docs/runbooks/aws-deploy.md`
- **Release gate** → `docs/runbooks/release-gate.md`
- **Backup** → `docs/runbooks/backup.md`
- **ADRs** → `.claude/memory/decisions.md`

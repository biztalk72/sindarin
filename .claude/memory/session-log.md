# Session Log

セッション単位の作業ログ（基本はローカル運用向け）。
重要な意思決定は `.claude/memory/decisions.md`、再利用できる解法は `.claude/memory/patterns.md` に昇格してください。

## Index

- （必要に応じて追記）

---

## セッション: 2026-06-02T08:35:12Z

- session_id: `session-1780389285967654000`
- project: `sindarin`
- branch: `(no git)`
- started_at: `2026-06-02T08:34:45Z`
- ended_at: `2026-06-02T08:35:12Z`
- changes: 0

### 変更ファイル
- （なし）

### 重要な変更（important=true）
- （なし）

### 次回への引き継ぎ（任意）
- （必要に応じて追記）

---

## セッション: 2026-06-04T23:10:22Z

- session_id: `session-1780614598209599000`
- project: `sindarin`
- branch: `(no git)`
- started_at: `2026-06-04T23:09:58Z`
- ended_at: `2026-06-04T23:10:22Z`
- changes: 0

### 変更ファイル
- （なし）

### 重要な変更（important=true）
- （なし）

### 次回への引き継ぎ（任意）

**Plans.md のWIP/依頼中（抜粋）**:

```
| `cc:WIP` | Impl (Claude Code) in progress | Impl |
State flow: `pm:requested → cc:TODO → cc:WIP → cc:完了 → pm:approved`.
- `cc:WIP` **PageIndex tree build** — per-document tree + cross-document synthetic TOC. No vector DB (invariant #2).
- `cc:WIP` **TOC → tree traversal retrieval** — narrow candidate docs via TOC, descend to leaf nodes, assemble evidence.
- `cc:WIP` **Runtime guardrails** — Presidio PII input filter + LLM-judge output filter + audit log on every model call (invariant #4). _Done: interfaces + interim regex PII redactor (email/phone/RRN/card, EN+KO) + output empty-guard + `AuditSink` (in-memory); enforced in `ChatService`. 6 tests. Pending: swap regex→Presidio, empty-guard→LLM-judge, in-memory sink→Postgres._
- `cc:WIP` **Single-org auth** — JWT + optional OIDC (ADR-0005); admin vs user scoping (invariant #7). _Done: `auth/jwt.py` mint/`decode_token` + `Principal`, `current_user`/`require_admin` deps, 3 tests. Pending: wire deps onto routes; OIDC path._
```

---

## セッション: 2026-06-05T04:25:12Z

- session_id: `session-1780633475255946000`
- project: `sindarin`
- branch: `(no git)`
- started_at: `2026-06-05T04:24:35Z`
- ended_at: `2026-06-05T04:25:12Z`
- changes: 0

### 変更ファイル
- （なし）

### 重要な変更（important=true）
- （なし）

### 次回への引き継ぎ（任意）

**Plans.md のWIP/依頼中（抜粋）**:

```
| `cc:WIP` | Impl (Claude Code) in progress | Impl |
State flow: `pm:requested → cc:TODO → cc:WIP → cc:完了 → pm:approved`.
- `cc:WIP` **Runtime guardrails** — Presidio PII input filter + LLM-judge output filter + audit log on every model call (invariant #4). _Done: interfaces + interim regex PII redactor (email/phone/RRN/card, EN+KO) + output empty-guard + `AuditSink` (in-memory); enforced in `ChatService`. 6 tests. Pending: swap regex→Presidio, empty-guard→LLM-judge, in-memory sink→Postgres._
- `cc:WIP` **Single-org auth** — JWT + optional OIDC (ADR-0005); admin vs user scoping (invariant #7). _Done: `auth/jwt.py` mint/`decode_token` + `Principal`, `current_user`/`require_admin` deps, 3 tests. Pending: wire deps onto routes; OIDC path._
```

---

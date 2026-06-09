# Hybrid IDP

> 단일 조직용 **자체 호스팅** 지능형 문서 처리(IDP) + 채팅 워크스페이스.
> 인용 기반 RAG, 런타임 가드레일, 데이터 거버넌스를 한 노드에서 끝낸다.
> 타깃 플랫폼: NVIDIA GB10 단일 노드. 데이터는 박스를 떠나지 않는다.

> 🇺🇸 **English:** [`README.md`](README.md)

- **PRD / SSOT:** [`docs/PRD2.md`](docs/PRD2.md)
- **개요 및 아키텍처 요약:** [`docs/OVERVIEW.md`](docs/OVERVIEW.md)
- **아키텍처 결정 기록(ADR):** [`.claude/memory/decisions.md`](.claude/memory/decisions.md) (ADR 0001–0011)
- **런북:** [`docs/runbooks/`](docs/runbooks/) — go-live, Nemotron Phase 0
- **프로젝트 가이드:** [`CLAUDE.md`](CLAUDE.md)

---

## 핵심 기능

- **3-pane 워크스페이스** — 문서 라이브러리, 인용이 부착된 채팅 + 원문 미리보기, 그래프/메타 인사이트 패널
- **다포맷 ingestion** — docx · xlsx · pptx · html · csv · json · xml · hwpx · pdf. 포맷별 워커가 검증된 `DocumentIR`을 산출
- **하이브리드 검색** — vector(Qdrant) + BM25 + PageIndex 보조 + ACL payload filter + Postgres double-check
- **Proof beats fluency** — 클레임 단위 JSON, 토큰 overlap 검증, 근거 못 찾은 클레임은 **drop**(답변이 정직하게 "근거를 찾을 수 없음")
- **런타임 가드레일** — PII(주민/사업자/카드/email/한국 휴대폰) + prompt injection 탐지·제거 (ADR-0006)
- **이중언어(KO/EN) 1급** — UI, 시스템 프롬프트, BM25 토크나이저 모두 한국어 인지
- **데이터 거버넌스 UI** — SecurityLevel 4단계 분류, DSR(export/forget), 가드레일 override 워크플로(사유+TTL), Compliance Report(요약+CSV), 외부 egress 감시 배너
- **채팅 단위 관측성** — 모든 호출에 ULID `event_id` + `trace_id` + JSONB metrics. DB row와 일별 JSON-Lines 파일이 같은 event_id로 매핑
- **자체 호스팅 LLM** — vLLM 0.11 (`nvcr.io/nvidia/vllm` sm_100 빌드), `Llama-3.1-Nemotron-Nano-8B-v1` 챗 + `bge-m3` 임베딩
- **토크나이저 인지 컨텍스트 budget** — HuggingFace `tokenizers`를 api 빌드 시점에 prefetch. 미지원 시 글자수 fallback
- **Eval-gated 릴리스** — citation_precision ≥ 0.90, recall_at_10 ≥ 0.90 등 기준선 미달 시 릴리스 차단

## 기술 스택

| 계층 | 기술 |
|---|---|
| API | Python 3.12 · FastAPI · SQLAlchemy 2.0 · Alembic · pydantic 2 · psycopg 3 · PyJWT · openai SDK · `tokenizers`(HF) |
| RAG 코어 (in-house) | `rag_core` — chunker, retrieval, BM25, vectorstore, generator, trust, guardrails, pipeline |
| 워커 | markitdown · ocr(PaddleOCR + PaddleOCR-VL) · hwpx · embedding · eval |
| 웹 | Next.js 15 (App Router, standalone) · React 19 · TypeScript 5.5 · Bootstrap 4.6 + shards-ui 3.0 CSS · `@tabler/icons-react` · next-intl · vitest |
| 모델 | Nemotron Nano-8B(챗) · BAAI/bge-m3(임베딩) · vLLM 0.11 (nvcr.io/nvidia/vllm:25.11-py3) |
| 인프라 | PostgreSQL 16 · Qdrant · MinIO · Docker Compose |
| 워크스페이스 | uv (Python) · npm (web) |

## 디렉터리 구조

```
apps/        web (Next.js 15) · api (FastAPI)
workers/     markitdown · ocr · hwpx · embedding · eval
packages/    shared · document_ir · rag_core · db
infra/       docker · compose · harness · migrations
tests/       unit · integration · e2e · performance · eval
docs/        adr · architecture · runbooks · OVERVIEW
```

## 빠른 시작

```bash
make install          # uv sync (Python workspace) + web 의존성
make up               # docker compose up -d (api, web, postgres, qdrant, minio, workers)
# 라이브 모드 (GB10에서 vLLM 자체 호스팅):
docker compose --env-file .env -f infra/compose/dev.yml -f infra/compose/llm.yml up -d
make migrate          # alembic upgrade head
make test             # pytest + 웹 테스트
make lint typecheck   # ruff + tsc
```

dev → live LLM 전환 절차는 [`docs/runbooks/go-live.md`](docs/runbooks/go-live.md) 참고.
권장 경로는 **Option B (GB10 자체 호스팅 vLLM)** — 데이터 egress 없음.

## 최소 시스템 요구사항

| 항목 | 요구사항 |
|---|---|
| GPU | NVIDIA GB10 (Grace Blackwell, sm_100, 128 GB 통합 메모리). A100 40/80 GB에서도 `gpu_memory_utilization` 조정 후 동작. |
| 메모리 | ≥ 64 GiB 호스트 RAM |
| 디스크 | ≥ 100 GiB (HF 모델 캐시 ≈ 48 GiB + Postgres + Qdrant + MinIO + 로그) |
| 드라이버 | NVIDIA 580.x+ · CUDA 13.0 |
| OS | Linux 6.x · Docker 27+ with NVIDIA Container Toolkit |
| 호스트 툴체인 | Python 3.12 · `uv` ≥ 0.4 · Node 20+ (웹 개발 시) |
| 네트워크 | 1 Gbps (최초 HF 모델 다운로드 시만 — 이후 오프라인 가능) |

## 일반 RAG 챗봇과의 차이

| 축 | 일반 RAG 챗봇 | Hybrid IDP |
|---|---|---|
| Retrieval | 벡터 유사도, 단일 단계 | 하이브리드: vector + BM25 + PageIndex + ACL 필터 + Postgres double-check |
| 인용 | 사후 참조 리스트 | 클레임 단위 JSON, 토큰 overlap 검증, 미지원 클레임은 **drop** |
| 가드레일 | 외부(Guardrails AI / NeMo 등) | 모든 호출에 런타임 PII regex + injection strip, override 워크플로 포함 |
| 감사 | 옵션, 앱별 구현 | 1급 시민: `audit_logs` row + 일별 JSON-Lines 파일 (ULID 공유) |
| 데이터 거버넌스 | 최소 | SecurityLevel 4단계 · ACL · DSR(export/forget) · Compliance Report · egress 감시 |
| 호스팅 | 클라우드 LLM API | 단일 GB10 노드에서 완전 자체 호스팅, sm_100 vLLM |
| 모델 교체 | 수동 config 수정 | ADR 기반 컷오버 + 토크나이저 인지 budget · `audit_logs.metrics.model` 로 사전/사후 diff |
| 한국어 지원 | 토크나이저 미인지 | Hangul-aware BM25 · KO 시스템 프롬프트 · 양언어 UI |
| 실패 철학 | 유창한 답변 우선 | **Proof beats fluency** — 검증 통과 못 하면 정직하게 "근거를 찾을 수 없음" |

전체 14-축 비교 + "각 쪽이 이기는 지점"은 [`docs/OVERVIEW.md`](docs/OVERVIEW.md) §4 참고.

## 라이선스

내부용 — 소속 조직 정책 따름.

# Hybrid IDP 통합 개발용 PRD

작성자: **Manus AI**  
작성일: **2026-06-05**  
문서 목적: **Claude 기반 구현 작업 분해 및 Harness 기반 CI/CD·테스트·배포에 바로 활용 가능한 단일 개발 기준 문서**

---

## 1. Executive Summary

**Hybrid IDP**는 단일 조직이 자체 호스팅으로 운용하는 **지능형 문서 처리 및 근거 기반 RAG 챗봇 시스템**이다. 사용자는 PDF, DOCX, XLSX, PPTX, HWPX, 이미지, HTML, CSV, JSON, XML 등 다양한 문서를 업로드하고 자연어로 질문한다. 시스템은 문서를 포맷별 최적 전처리 엔진에 라우팅하고, 정규화된 Document IR을 생성하며, 의미 키워드와 메타데이터를 추출한 뒤, Vector DB와 키워드 인덱스에 저장한다. 이후 RAG 챗봇은 권한 필터, 검색 재랭킹, citation validation, groundedness evaluation을 거쳐 신뢰 가능한 답변을 제공한다.

본 PRD의 핵심 변경은 기존의 단순 문서 질의응답 시스템을 **실제 운영 가능한 문서 AI 워크스페이스**로 확장하는 것이다. Microsoft OSS **MarkItDown**은 Office 및 MarkItDown 지원 포맷의 전처리 전담 계층으로 사용하고, **PaddleOCR-VL/PaddleOCR**는 digital-native PDF, 일반 PDF, 스캔 PDF, 이미지 문서의 OCR 및 레이아웃 분석을 담당한다. **HWPX**는 한국 기업·공공 문서의 1급 포맷으로 다루며, XML 구조, 문단, 표, 스타일, 문서 속성, semantic keyword, metadata를 추출한다. 추출 결과는 Vector DB payload와 관계형 DB metadata로 저장되어 RAG 검색, 권한 필터, UI 시각화, 감사 로그에 활용된다.

> **제품 방향 정의**: Hybrid IDP는 “채팅창이 붙은 문서 검색기”가 아니라, “문서의 구조와 의미를 시각적으로 이해하고, 근거가 검증된 답변을 생성하는 자체 호스팅 문서 AI 플랫폼”이다.

| 항목 | 최종 방향 |
|---|---|
| 서비스 유형 | 단일 조직 자체 호스팅 IDP + RAG 챗봇 + 문서 AI 워크스페이스 |
| 타깃 플랫폼 | NVIDIA GB10 계열, 128GB unified memory 단일 노드 우선 |
| 전처리 | MarkItDown, PaddleOCR-VL/PaddleOCR, HWPX native parser 조합 |
| 검색 | Vector DB + metadata filtering + keyword/BM25 + 구조 인덱스 + reranking |
| 답변 생성 | Model Router 기반 LLM/VLM 라우팅, streaming, citation validation |
| UI | 3-pane workspace, 문서 아이콘 라이브러리, 목차 트리뷰, 워드 클라우드, 키워드 그래프, 근거 중심 챗봇 |
| 개발 방식 | Claude가 모듈 단위로 구현 가능한 monorepo, 명확한 요구사항 ID와 수용 기준 제공 |
| 배포 방식 | Harness CI/CD 파이프라인으로 빌드, 테스트, 보안 검사, 이미지 배포, smoke test, rollback 자동화 |

---

## 2. Product Scope

### 2.1 Problem Statement

문서 RAG 시스템의 실제 품질은 LLM의 응답 능력보다 **전처리 품질, 청킹 전략, 메타데이터 보존, 권한 필터, 검색 재랭킹, 인용 검증**에 의해 크게 좌우된다. Office 파일은 표, 슬라이드, 주석, 숨김 시트, 수식 구조가 손실되기 쉽고, PDF는 digital-native PDF와 스캔 PDF가 혼재하며, HWPX는 한국 조직에서 중요하지만 일반적인 RAG 파이프라인에서 안정적으로 처리되지 않는다. 이러한 문제를 해결하지 않고 단순 텍스트 청크를 임베딩하면 Vector DB를 사용하더라도 운영 환경에서 검색 누락, 잘못된 인용, 권한 노출, 품질 회귀가 발생한다.

또한 사용자는 “어떤 문서가 처리되었는지”, “문서가 제대로 읽혔는지”, “질문이 어떤 문서를 대상으로 수행되는지”, “답변의 근거가 어디인지”를 UI에서 즉시 확인할 수 있어야 한다. 따라서 Hybrid IDP는 단순 백엔드 RAG 엔진이 아니라 **문서 라이브러리, 구조 탐색, 키워드 인사이트, 근거 기반 채팅, 관리자 관찰성**을 하나로 제공해야 한다.

### 2.2 Goals

| 목표 | 설명 | 성공 기준 |
|---|---|---|
| 포맷별 최적 전처리 | MarkItDown, PaddleOCR-VL/PaddleOCR, HWPX parser를 파일 유형별로 라우팅한다. | P0에서 PDF, DOCX, HWPX end-to-end 처리 성공 |
| 운영 가능한 RAG | Vector DB에 chunk embedding, metadata, semantic keyword, citation anchor를 저장한다. | 권한 필터가 적용된 RAG 답변 생성 |
| 근거 기반 답변 | 답변의 주장과 문서, 페이지, 섹션, bbox, 표 셀을 연결한다. | citation anchor accuracy 0.90 이상 |
| 한국어·영어 동등 지원 | HWPX, 한국어 OCR, 한국어 PII, 한영 혼합 질의를 1급 경로로 처리한다. | golden query set에서 한국어 Recall@10 0.90 이상 |
| 문서 중심 UI | 문서 아이콘 뷰, 목차 트리뷰, 워드 클라우드, 키워드 그래프를 제공한다. | 사용자가 문서 선택 후 3분 내 질문 전환율 50% 이상 |
| GB10 단일 노드 최적화 | 128GB unified memory에서 워커 큐, 동시성, 모델 리소스를 제어한다. | P3에서 p95 first-token 6초 이하, ingestion retry success 98% 이상 |
| Harness 기반 운영 | CI/CD, 보안 검사, smoke test, rollback을 파이프라인화한다. | main branch merge 후 dev 자동 배포 및 smoke test 통과 |

### 2.3 Non-Goals

초기 버전은 멀티테넌트 SaaS를 목표로 하지 않는다. 단일 조직 자체 호스팅을 전제로 하며, 내부 문서의 보안, 접근 제어, 감사 가능성, 복구 가능성을 우선한다. 모바일 네이티브 앱, 로컬 모델 파인튜닝, 완전 자동 정책 판단, 고급 문서 편집기는 초기 범위에서 제외한다.

| 제외 범위 | 제외 이유 |
|---|---|
| 멀티테넌트 SaaS | 초기 보안·운영 복잡도를 낮추고 단일 조직 배포에 집중한다. |
| 모바일 네이티브 앱 | 웹 UI와 반응형 레이아웃으로 MVP 요구를 충족한다. |
| 로컬 모델 파인튜닝 | GB10 단일 노드에서 서비스 운영과 학습을 동시에 수행하면 리소스 경합이 커진다. |
| 문서 원문 편집기 | 핵심은 문서 이해, 검색, 답변, 검증이지 문서 작성이 아니다. |
| 완전 자동 권한 판단 | 민감 문서 접근, override, egress는 관리자 승인 흐름을 요구한다. |

### 2.4 User Roles

| Role | 주요 권한 | 제한 사항 |
|---|---|---|
| `admin` | 전체 설정, 사용자·권한 관리, 모델 라우팅, Vector DB 관리, 가드레일 override | 모든 override는 audit log와 사유가 필요하다. |
| `document_manager` | 문서 업로드, 재처리, 태그, 보존 정책, 문서별 권한 관리 | 시스템 설정과 모델 라우팅은 변경할 수 없다. |
| `auditor` | 감사 로그, 질의 이력, 인용 근거, PII 탐지 이벤트 조회 | 문서 원문 접근은 별도 권한이 필요하다. |
| `user` | 권한이 있는 문서 검색, 채팅, citation 확인, 피드백 제출 | 접근 권한이 없는 문서의 키워드·그래프도 볼 수 없다. |

---

## 3. Target Platform: NVIDIA GB10 128GB RAM

타깃 서비스 플랫폼은 **NVIDIA GB10 계열 128GB unified memory 단일 노드**로 정의한다. NVIDIA DGX Spark 계열은 Grace Blackwell 아키텍처, 20-core Arm CPU, 128GB LPDDR5x unified system memory, NVMe storage, 10GbE 및 ConnectX-7 연결성을 제공하는 로컬 AI 개발·검증 플랫폼으로 설명된다.[3] [4] 이 플랫폼은 PoC와 소규모 운영에는 적합하지만, OCR/VLM, embedding, reranking, LLM inference, Vector DB, Postgres, object store, API 서버가 동시에 실행될 경우 unified memory와 NVMe I/O 경합이 발생한다.

| 리소스 | 설계 기준 | 운영 정책 |
|---|---|---|
| CPU | Arm 기반 Python wheel, DB extension, OCR 의존성 호환성 확인 | clean install CI와 base image 고정 |
| Memory | 128GB unified memory를 API, DB, Vector DB, OCR/VLM, LLM이 공유 | worker별 memory limit와 concurrency cap 적용 |
| Storage | 원본, page image, OCR, Markdown IR, embeddings, snapshot 저장 | 4TB NVMe 권장, retention policy와 compaction 적용 |
| GPU/Accelerator | OCR/VLM, embedding, reranker, local LLM이 공유 | priority queue, batch window, model offload policy 적용 |
| Network | 외부 LLM/VLM 사용 시 egress 통제 필요 | 문서 보안 등급별 external call policy 적용 |
| Thermal | 장시간 OCR batch 처리 시 throttling 가능 | thermal soak test와 batch scheduling 적용 |

초기 배포는 운영 단순성을 위해 **Docker Compose**를 기본으로 한다. 다만 컨테이너 이미지, 환경 변수, 볼륨, healthcheck, snapshot 경로, secret 관리 구조는 추후 단일 노드 Kubernetes 또는 GitOps로 전환 가능하도록 분리한다.

| 서비스 | 배포 단위 | 설명 |
|---|---|---|
| `ui` | Next.js container | 3-pane 문서 AI 워크스페이스 |
| `api` | FastAPI container | auth, ACL, upload, chat orchestration, admin API |
| `postgres` | container 또는 managed local | metadata, users, ACL, audit, eval |
| `object-store` | MinIO 또는 S3-compatible | 원본 파일과 중간 산출물 저장 |
| `vector-db` | Qdrant 또는 pgvector | chunk embedding, payload filtering, snapshot |
| `worker-markitdown` | Python worker | Office 및 MarkItDown target preprocessing |
| `worker-ocr` | Python worker | PaddleOCR-VL/PaddleOCR PDF·image 처리 |
| `worker-hwpx` | Python worker | HWPX XML parsing, metadata, keyword extraction |
| `worker-embedding` | Python worker | embedding batching, retry, versioning |
| `worker-eval` | Python worker | citation, groundedness, retrieval eval |
| `monitoring` | Prometheus/Grafana 또는 경량 수집기 | GB10 telemetry, latency, queue, quality 지표 |

---

## 4. End-to-End Architecture

전체 처리 흐름은 `upload → format detection → preprocessing route → normalized Document IR → enrichment → chunking → embedding → Vector DB indexing → retrieval → reranking → answer generation → citation validation → UI source navigation`으로 정의한다. PageIndex 또는 TOC는 벡터 검색을 대체하는 레이어가 아니라 **구조 인덱스, 인용 정렬, 검색 후보 검증, UI 탐색**을 위한 보조 인덱스로 사용한다.

| 계층 | 구성 요소 | 책임 |
|---|---|---|
| UI | Document Library, Chat Workspace, Insight Panel, Admin Dashboard | 문서 선택, 채팅, 원문 확인, 시각화, 운영 상태 표시 |
| API | `/upload`, `/documents`, `/ingest`, `/chat`, `/visualizations`, `/admin`, `/eval` | 인증, 권한, 요청 검증, orchestration, 감사 기록 |
| Preprocessing Router | MIME detector, magic bytes, PDF classifier, HWPX detector | 전처리 경로 결정과 fallback chain 실행 |
| MarkItDown Worker | MarkItDown adapter, table extractor, metadata extractor | Office 및 지원 포맷을 Markdown 중심 IR로 변환 |
| OCR Worker | PDF renderer, PaddleOCR, PaddleOCR-VL, image enhancer | PDF·이미지의 텍스트, bbox, 표, 레이아웃 추출 |
| HWPX Worker | XML parser, style resolver, table extractor, keyword extractor | HWPX 구조, 메타데이터, semantic keyword 추출 |
| Enrichment | language detection, PII tagging, keyword/entity extractor, summarizer | 검색과 UI에 필요한 의미 정보 생성 |
| Indexing | chunker, embedding worker, vector writer, BM25 indexer | 검색 가능한 색인 생성과 버전 관리 |
| Retrieval | query understanding, metadata filter, vector search, keyword search, reranker | 후보 문맥 검색과 정렬 |
| Generation | model router, LLM/VLM client, streaming manager | 답변 생성, 중지, 재시도, fallback |
| Trust | citation validator, groundedness judge, audit log | 근거 검증, 평가, 품질 추적 |
| Storage | Postgres, object store, Vector DB, cache | 원본, IR, 임베딩, 로그, 상태, snapshot 저장 |

---

## 5. Document Processing Requirements

### 5.1 Preprocessing Routing Policy

전처리 라우터는 확장자만 보지 않고 MIME type, magic bytes, 내부 구조, PDF text layer ratio, image coverage, 암호화 여부, OCR 필요성, HWPX package structure를 함께 확인한다. MarkItDown은 Microsoft가 공개한 Markdown 변환 도구로, LLM 및 텍스트 분석 파이프라인에서 활용 가능한 Markdown 변환을 목표로 한다.[1] PaddleOCR는 OCR 및 Document AI 생태계이며, PaddleOCR-VL은 문서 파싱용 VLM으로 텍스트, 표, 수식, 차트 등 복합 요소와 다국어 문서 처리를 지원한다고 설명된다.[2]

| 입력 유형 | 기본 경로 | 보조 경로 | 필수 산출물 |
|---|---|---|---|
| DOCX | MarkItDown | LibreOffice headless 변환 후 재시도 | Markdown, heading tree, table blocks, metadata |
| XLSX | MarkItDown + sheet/table extractor | CSV export fallback | sheet metadata, table JSON, formulas if available |
| PPTX | MarkItDown | slide image render + OCR fallback | slide text, notes, image captions, slide metadata |
| HTML/CSV/JSON/XML | MarkItDown 또는 native parser | encoding repair, schema inference | Markdown/JSON IR, field metadata |
| Digital-native PDF | text/layout extraction + PaddleOCR-VL layout analysis | PaddleOCR fallback | page text, layout blocks, table anchors, bbox |
| Scanned/general PDF | page render → PaddleOCR/PaddleOCR-VL | deskew, denoise, DPI normalization | OCR text, bbox, confidence, page images |
| Image | PaddleOCR/PaddleOCR-VL | VLM captioning for complex figures | OCR text, figure description, coordinates |
| HWPX | native HWPX XML parser | LibreOffice render → OCR/VLM fallback | sections, paragraphs, tables, styles, metadata, keywords |
| Legacy HWP | hwp5txt/pyhwp if available | LibreOffice render → OCR/VLM fallback | best-effort text, page images, OCR anchors |

### 5.2 MarkItDown Worker

MarkItDown worker는 Office 파일과 MarkItDown target file의 전처리를 전담한다. 단, MarkItDown 결과만으로 표나 엑셀 구조가 충분히 보존되지 않을 수 있으므로 Markdown IR과 함께 table JSON, sheet metadata, slide metadata를 별도 저장한다.

| 요구사항 ID | 요구사항 | 수용 기준 |
|---|---|---|
| MD-001 | MarkItDown adapter 구현 | DOCX, XLSX, PPTX, HTML, CSV, JSON, XML 샘플을 처리한다. |
| MD-002 | Markdown block ID 생성 | heading, paragraph, list, table, slide, sheet 단위 block ID가 생성된다. |
| MD-003 | Table JSON 보존 | 표 헤더, 셀, 병합 정보, sheet/slide 위치가 구조화 저장된다. |
| MD-004 | 변환 품질 측정 | text extraction coverage, table preservation score, warning count를 기록한다. |
| MD-005 | fallback chain | 실패 시 LibreOffice 변환 또는 native parser로 재시도하고 상태를 저장한다. |

### 5.3 PaddleOCR-VL/PaddleOCR Worker

PDF와 이미지 처리 계층은 digital-native PDF와 스캔 PDF를 모두 다룬다. Digital-native PDF라도 표, 그림, 레이아웃, 다단 구조가 중요한 경우에는 PaddleOCR-VL 기반 layout-sensitive path를 적용한다. 일반 스캔 문서는 page render 후 OCR과 이미지 전처리를 수행한다.

| 요구사항 ID | 요구사항 | 수용 기준 |
|---|---|---|
| OCR-001 | PDF classifier 구현 | digital-native, scanned, hybrid PDF를 분류한다. |
| OCR-002 | page render pipeline | 페이지 이미지, DPI, 회전, deskew, denoise 결과가 저장된다. |
| OCR-003 | PaddleOCR text extraction | 페이지별 텍스트, bbox, confidence가 저장된다. |
| OCR-004 | PaddleOCR-VL layout extraction | 표, 차트, 수식, 그림, 복합 레이아웃 후보를 구조화한다. |
| OCR-005 | quality gate | confidence threshold 미만 문서는 `재처리 필요` 상태와 warning을 표시한다. |
| OCR-006 | citation anchor | page number, bbox, block ID가 chunk payload와 UI preview에 연결된다. |

### 5.4 HWPX Worker

HWPX는 한국어 업무 문서의 핵심 포맷으로 취급한다. HWPX worker는 zip package 내부 XML을 분석하여 문단, 표, 스타일, 제목 계층, 이미지 참조, 문서 속성, 작성자, 생성일, 보안 태그, semantic keyword를 추출한다.

| 요구사항 ID | 요구사항 | 수용 기준 |
|---|---|---|
| HWPX-001 | HWPX package parser | HWPX 내부 XML 파일을 파싱하고 본문 section을 추출한다. |
| HWPX-002 | style-based TOC | 제목 스타일과 문단 속성으로 목차 트리를 생성한다. |
| HWPX-003 | table extractor | 표 row, cell, merged cell, caption을 구조화한다. |
| HWPX-004 | metadata extractor | 문서 속성, 작성자, 생성일, 수정일, security label 후보를 추출한다. |
| HWPX-005 | semantic keyword extractor | 법령명, 기관명, 제품명, 날짜, 금액, 약어, 업무 키워드를 추출한다. |
| HWPX-006 | fallback path | XML 파싱 실패 시 render + OCR/VLM 경로로 전환한다. |

---

## 6. Document IR, Data Model, and Storage

모든 전처리 결과는 공통 **Document IR**로 정규화한다. 이 IR은 RAG 검색뿐 아니라 UI 목차 트리뷰, 워드 클라우드, 키워드 그래프, citation chip, 원문 미리보기, 감사 로그에 동일하게 사용된다.

### 6.1 Document IR Fields

| 필드 | 타입 | 설명 |
|---|---|---|
| `document_id` | UUID | 원본 문서 내부 식별자 |
| `source_uri` | string | object store 내 원본 파일 위치 |
| `document_type` | enum | PDF, DOCX, XLSX, PPTX, HWPX, image, HTML 등 |
| `page_no` | integer nullable | 페이지 기반 문서의 페이지 번호 |
| `section_id` | UUID/string | 장, 절, 슬라이드, 시트 등 구조 단위 ID |
| `section_path` | string[] | 문서 내 목차 경로 |
| `block_id` | string | 문단, 표, 그림, 셀 등 검색·인용 단위 |
| `text` | string | 정규화된 본문 텍스트 |
| `markdown` | string nullable | 구조를 보존한 Markdown 표현 |
| `bbox` | object nullable | PDF/이미지 기반 문서의 좌표 정보 |
| `table_schema` | object nullable | 표 헤더, 열 타입, 셀 좌표, 병합 셀 정보 |
| `metadata` | object | 작성자, 날짜, 부서, 보존 정책, 권한 태그 |
| `semantic_keywords` | object[] | 업무 키워드, 엔터티, 약어, 제품명, 법령명 |
| `quality` | object | OCR confidence, parse warnings, fallback 여부, parser version |

### 6.2 Relational Data Model

Postgres는 문서 메타데이터, 사용자·권한, ingestion job, audit log, evaluation result, UI visualization cache의 기준 저장소다.

| 테이블 | 주요 필드 | 목적 |
|---|---|---|
| `documents` | `id`, `name`, `type`, `owner_id`, `security_level`, `status`, `created_at` | 문서 기본 정보 |
| `document_versions` | `id`, `document_id`, `version_no`, `source_uri`, `checksum` | 버전 관리와 재처리 추적 |
| `document_blocks` | `id`, `document_id`, `section_id`, `page_no`, `block_type`, `text`, `bbox` | IR block 저장 |
| `document_tables` | `id`, `document_id`, `block_id`, `schema_json`, `cells_json` | 표 구조 보존 |
| `document_keywords` | `id`, `document_id`, `section_id`, `keyword`, `weight`, `confidence` | 워드 클라우드와 추천 질문 |
| `document_entities` | `id`, `document_id`, `entity`, `entity_type`, `source_block_id` | entity graph와 검색 필터 |
| `keyword_edges` | `source_keyword`, `target_keyword`, `weight`, `scope` | 키워드 관계 그래프 |
| `ingestion_jobs` | `id`, `document_id`, `stage`, `status`, `logs`, `metrics` | 비동기 처리 상태 |
| `acl_entries` | `resource_id`, `resource_type`, `principal_id`, `permission` | 문서·컬렉션 권한 |
| `audit_logs` | `actor_id`, `action`, `resource_id`, `payload_hash`, `created_at` | 보안·운영 감사 |
| `eval_runs` | `id`, `dataset`, `metric`, `score`, `created_at` | 품질 회귀 추적 |

### 6.3 Vector DB Payload Contract

Vector DB에는 embedding만 저장하지 않는다. 검색 정확도, 권한 필터, citation, UI interaction을 위해 모든 chunk payload는 다음 정보를 포함해야 한다.

| Payload 필드 | 예시 | 활용 |
|---|---|---|
| `chunk_id` | `chk_01` | 검색 결과 식별 |
| `document_id` | UUID | 문서 연결과 ACL 검증 |
| `document_version_id` | UUID | 재색인·버전 충돌 방지 |
| `section_id` | `sec_03` | 목차 트리뷰와 scope 검색 |
| `toc_path` | `["계약", "해지", "위약금"]` | 구조 기반 context packing |
| `page_no` | `12` | citation chip과 원문 이동 |
| `bbox` | `{x,y,w,h}` | PDF/이미지 하이라이트 |
| `keywords` | `["계약 해지", "위약금"]` | query expansion, keyword filtering |
| `entities` | `["ABC Corp", "2026-05-01"]` | entity filter, graph |
| `security_level` | `confidential` | 권한 필터 |
| `acl_hash` | hash | 검색 시 권한 scope 검증 |
| `ocr_confidence` | `0.93` | 낮은 품질 후보 감점 |
| `parser` | `markitdown`, `paddleocr-vl`, `hwpx-native` | 품질 분석과 디버깅 |
| `embedding_model` | `model-name` | 버전 관리 |
| `embedding_version` | `v1` | blue/green reindex |

---

## 7. RAG and Trust Pipeline

검색은 단일 vector similarity 호출로 끝나지 않는다. 질의가 들어오면 query normalization, 언어 판별, 키워드·엔터티 추출, metadata filter 생성, Vector DB 검색, keyword/BM25 검색, 구조 인덱스 참조, reranking, context packing, answer generation, citation validation, runtime eval을 순차 수행한다.

| 단계 | 설명 | 실패 시 처리 |
|---|---|---|
| Query understanding | 질의 언어, 의도, 날짜·부서·문서 유형 필터 후보 추출 | 일반 semantic search로 fallback |
| Scope resolution | 사용자가 선택한 문서, 폴더, 목차 노드, 키워드 범위를 검색 scope로 변환 | 전체 권한 문서로 제한 |
| ACL filtering | Vector DB payload filter와 Postgres ACL double-check 적용 | 권한 불일치 시 결과 제외 |
| Candidate retrieval | Vector DB top-k 후보 검색 | keyword retrieval만 사용 |
| Keyword retrieval | BM25/keyword index로 정확한 용어, 문서번호, 법령명 검색 | vector 후보만 사용 |
| Reranking | cross-encoder 또는 LLM judge로 후보 재정렬 | 원래 점수 기반 정렬 |
| Context packing | 중복 제거, 페이지 순서, 표 주변 문맥, citation anchor 보존 | context budget 초과 시 높은 신뢰도 우선 |
| Answer generation | LLM으로 답변 생성, streaming 지원 | 모델 fallback 또는 근거 부족 응답 |
| Citation validation | 주장별 source span 대응 여부 확인 | 낮은 신뢰도 경고, draft 표시 |
| Runtime eval | groundedness, faithfulness, answer relevance 측정 | eval log만 저장하고 사용자 답변 유지 가능 |

### 7.1 Trust and Guardrails

제품 원칙은 **Proof beats fluency**이다. 답변이 유창하더라도 인용과 근거가 없으면 실패로 간주한다. 모든 답변은 citation chip을 포함해야 하며, 근거가 부족한 경우 “제공된 문서에서 확인할 수 없음”을 명시해야 한다.

| 리스크 | 필수 대응 | 테스트 기준 |
|---|---|---|
| Unsupported claim | claim extraction 후 source span entailment 검사 | unsupported claim rate 5% 이하 |
| 잘못된 인용 | citation validator 적용 | citation precision 0.90 이상 |
| 표 데이터 오독 | table JSON context와 numeric QA prompt 사용 | numeric QA accuracy 측정 |
| 권한 없는 문서 노출 | Vector DB filter + Postgres ACL double-check | seeded unauthorized query 100% 차단 |
| Prompt injection 문서 | document instruction stripping, injection detector | seeded injection test 통과 |
| PII 노출 | PII tagging, redaction policy, external egress policy | seeded PII scan 통과 |

---

## 8. UI/UX Requirements

Hybrid IDP의 UI는 **3-pane document AI workspace**를 기본으로 한다. 좌측에는 문서 라이브러리, 중앙에는 채팅과 문서 미리보기, 우측에는 선택 문서의 목차·키워드·그래프·메타데이터·품질 지표를 표시한다. 외부 챗봇 UI 레퍼런스에서 공통적으로 확인되는 좋은 패턴은 명확한 메시지 포맷, typing indicator, quick reply, fallback mechanism, 버튼·메뉴·첨부·멀티미디어를 포함한 풍부한 상호작용이다.[5] [6] Claude Code 역시 자연어 기반 개발 흐름에서 프로젝트 파일을 이해하고, 변경을 제안하며, 테스트와 Git workflow를 보조하는 agentic coding 도구로 설명된다.[7] 이러한 특성을 고려해 UI 요구사항은 사용자가 문서를 탐색하고 근거를 검증하는 데 초점을 둔다.

### 8.1 Information Architecture

| 영역 | 구성 요소 | 기본 동작 |
|---|---|---|
| Left: Document Library | 문서 아이콘 카드, 리스트 전환, 필터, 정렬, 상태 뱃지 | 문서 유형별 아이콘과 처리 상태를 표시하고 다중 선택으로 질의 범위를 지정한다. |
| Center: Chat & Preview Workspace | 채팅, 추천 질문, 답변 카드, 원문 미리보기, citation highlight | 답변과 근거를 함께 표시하고 citation chip 클릭 시 원문 위치로 이동한다. |
| Right: Document Insight Panel | 목차 트리뷰, 워드 클라우드, 키워드 그래프, metadata, 품질 지표 | 문서 클릭 시 구조와 의미 정보를 시각화한다. |
| Top Bar | 전역 검색, 모델/모드 선택, 권한, 작업 큐 상태 | 현재 선택 문서 범위와 시스템 상태를 표시한다. |
| Composer | 자연어 입력, 파일 첨부, quick action, 질문 템플릿 | 요약, 비교, 표 추출, 위험 조항 찾기 등의 액션을 제공한다. |

### 8.2 Document Library Requirements

| 요구사항 ID | 요구사항 | 수용 기준 |
|---|---|---|
| UI-DOC-001 | 문서 아이콘 카드 표시 | PDF, DOCX, PPTX, XLSX, HWPX, 이미지, HTML, TXT 유형별 아이콘이 표시된다. |
| UI-DOC-002 | 처리 상태 뱃지 | `업로드됨`, `전처리 중`, `OCR 중`, `키워드 추출 중`, `색인 완료`, `오류`, `재처리 필요` 상태가 표시된다. |
| UI-DOC-003 | 품질 지표 표시 | OCR confidence, extraction coverage, table preservation, chunk count가 카드 또는 상세 패널에 표시된다. |
| UI-DOC-004 | 질의 범위 지정 | 하나 이상의 문서를 선택하면 chat scope가 해당 문서로 제한된다. |
| UI-DOC-005 | 카드/리스트 전환 | 문서 수가 많을 때 리스트형 뷰와 server-side pagination이 제공된다. |
| UI-DOC-006 | 빈 상태 디자인 | 문서가 없을 때 그라디언트 온보딩 카드, 예시 질문, drag-and-drop 안내가 표시된다. |

### 8.3 Document Insight Panel Requirements

| 탭 | 구성 요소 | 상호작용 |
|---|---|---|
| 목차 | Tree View, 페이지/섹션 번호, 표·그림 노드 | 노드 클릭 시 해당 섹션을 질의 범위로 고정한다. |
| 키워드 | Word Cloud, top keyword list, entity list | 단어 클릭 시 관련 섹션, chunk, 추천 질문을 표시한다. |
| 그래프 | Keyword Graph, Entity Graph, Section-Keyword Graph | 노드 클릭 시 연결 키워드, 문서 위치, 인용 후보를 표시한다. |
| 메타데이터 | 파일 metadata, 추출 metadata, 보안 metadata | 작성자, 생성일, 권한 등급, 색인 상태를 표시한다. |
| 품질 | OCR confidence, extraction coverage, warnings | 낮은 품질, 누락 페이지, 표 추출 실패, 재처리 버튼을 표시한다. |

워드 클라우드는 단순 빈도 기반이 아니라 TF-IDF, BM25, embedding 기반 semantic salience, 섹션 중요도, HWPX 스타일·제목 가중치를 결합한 **hybrid keyword score**를 사용한다. 그래프는 기본 노드 20~50개, 엣지 150개 이하로 제한하고, 사용자가 확장할 때만 lazy loading한다.

### 8.4 Chatbot UI Requirements

| 요구사항 ID | 요구사항 | 수용 기준 |
|---|---|---|
| UI-CHAT-001 | Suggested Prompt Cards | 선택 문서의 키워드와 목차 기반 질문 카드가 생성된다. |
| UI-CHAT-002 | Citation Chips | 답변 문장 또는 단락 옆에 문서명, 페이지, 섹션 chip이 표시된다. |
| UI-CHAT-003 | Streaming Answer | 답변 생성 중 중지, 재시도, 이어쓰기, 짧게 요약이 가능하다. |
| UI-CHAT-004 | Confidence Indicator | 검색 문서 수, citation coverage, 낮은 신뢰도 경고가 표시된다. |
| UI-CHAT-005 | Visual Mode Toggle | 일반 채팅, 문서 미리보기, 그래프 중심, 비교 분석 모드를 전환할 수 있다. |
| UI-CHAT-006 | Quick Reply & Actions | “이 섹션만 다시 검색”, “원문 보기”, “관련 문서 더 찾기”, “표로 정리” 버튼을 제공한다. |
| UI-CHAT-007 | Theming | Clean Professional, Vibrant Gradient, Dark Analytics 테마를 지원한다. |
| UI-CHAT-008 | Accessibility | 키보드 탐색, 고대비, screen reader label, 색상 외 상태 표시를 지원한다. |

### 8.5 Responsive Policy

| 화면 크기 | 레이아웃 정책 |
|---|---|
| Desktop ≥ 1440px | 좌측 280px, 중앙 flexible, 우측 360~420px 3-pane 고정 |
| Laptop 1024~1439px | 좌측 접힘 가능, 우측 overlay 또는 resizable drawer |
| Tablet 768~1023px | 문서 라이브러리는 side drawer, 인사이트는 bottom/right drawer |
| Mobile < 768px | 채팅 우선 single column, 문서·목차·키워드는 bottom sheet 탭 제공 |

---

## 9. API Contracts

API는 FastAPI 기반을 권장하며 모든 요청은 auth context와 request id를 포함한다. 문서, 키워드, 그래프, citation API는 모두 동일한 ACL middleware를 통과해야 한다.

| Endpoint | Method | 설명 | 주요 응답 |
|---|---|---|---|
| `/api/upload` | POST | 파일 업로드 및 ingestion job 생성 | `document_id`, `job_id`, `status` |
| `/api/documents` | GET | 문서 목록, 필터, 정렬, pagination | document cards |
| `/api/documents/{id}` | GET | 문서 상세 metadata | document detail |
| `/api/documents/{id}/toc` | GET | 목차 트리뷰 데이터 | `toc_tree` |
| `/api/documents/{id}/keywords` | GET | 워드 클라우드와 keyword list | `keywords`, `weights` |
| `/api/documents/{id}/graph` | GET | 키워드·엔터티 그래프 | `nodes`, `edges` |
| `/api/documents/{id}/preview` | GET | 원문 미리보기, page image, block 위치 | preview payload |
| `/api/ingest/jobs/{id}` | GET | ingestion 진행률과 로그 | job status |
| `/api/ingest/jobs/{id}/retry` | POST | 재처리 요청 | new job status |
| `/api/chat` | POST | RAG 질의와 streaming 답변 생성 | answer stream, citations |
| `/api/chat/{id}/feedback` | POST | 사용자 피드백 제출 | saved feedback |
| `/api/admin/health` | GET | 문서, 워커, DB, Vector DB, 모델 상태 | health summary |
| `/api/eval/run` | POST | golden query eval 실행 | eval run id |

### 9.1 Chat Request Contract

| 필드 | 타입 | 설명 |
|---|---|---|
| `message` | string | 사용자 질문 |
| `scope` | object | 선택 문서, 컬렉션, 섹션, 키워드 범위 |
| `mode` | enum | `answer`, `summary`, `compare`, `table_qa`, `risk_review` |
| `language` | enum nullable | `ko`, `en`, `auto` |
| `stream` | boolean | streaming 여부 |
| `model_hint` | string nullable | 관리자 또는 사용자가 지정한 모델 힌트 |

### 9.2 Chat Response Contract

| 필드 | 타입 | 설명 |
|---|---|---|
| `answer` | string | 최종 답변 |
| `citations` | object[] | 문서명, page, section, bbox, source span |
| `confidence` | object | groundedness, citation coverage, retrieval quality |
| `warnings` | string[] | 근거 부족, 낮은 OCR confidence, 충돌 문서 등 |
| `retrieval_trace_id` | string | 감사와 디버깅용 trace ID |

---

## 10. Non-Functional Requirements

### 10.1 Security and Privacy

문서 RAG는 원본 파일, OCR 텍스트, 임베딩 payload, 사용자 질문, 모델 호출 payload, 로그 모두에서 민감정보 노출 위험이 발생한다. 모든 문서·시각화·검색 API는 ACL scope를 강제해야 하며, 외부 LLM 호출은 문서 보안 등급별 egress policy를 따라야 한다.

| 요구사항 | 기준 |
|---|---|
| ACL | Vector DB payload filter와 Postgres ACL double-check를 모두 적용한다. |
| PII | 한국어 주민번호, 전화번호, 이메일, 주소, 계좌번호, 사업자번호, 조직 내부 식별자를 탐지한다. |
| 로그 | 사용자 질문과 모델 payload는 필요한 경우 마스킹하고 보존 기간을 설정한다. |
| Object store | private bucket, signed URL TTL, service account 최소 권한을 사용한다. |
| Admin override | 사유 입력, 감사 로그, 선택적 2인 승인 정책을 지원한다. |
| Prompt injection | 문서 내 지시문 제거, prompt injection detector, seeded test를 적용한다. |

### 10.2 Performance Targets

| 영역 | 지표 | 목표 |
|---|---|---|
| UI | 문서 필터·패널 전환 p95 | 300ms 이하 |
| UI | 기본 키워드 그래프 렌더링 p95 | 1.5초 이하 |
| Chat | P3 p50 first-token | 2.5초 이하 |
| Chat | P3 p95 first-token | 6.0초 이하 |
| Retrieval | golden query Recall@10 | 0.90 이상 |
| Citation | citation anchor accuracy | 0.90 이상 |
| Ingestion | MarkItDown target parse success | 97% 이상 |
| Ingestion | HWPX native parse success | 95% 이상 |
| OCR | scanned PDF OCR confidence mean | 0.90 이상 |
| Reliability | ingestion retry success | 98% 이상 |
| Backup | Vector DB snapshot restore | 월 1회 성공 |

### 10.3 Observability

운영자는 어떤 문서가 왜 실패했는지, 어떤 전처리 엔진이 어떤 warning을 만들었는지, 어떤 검색 후보가 답변에 사용되었는지, 어떤 모델 호출이 비용과 지연시간을 유발했는지 확인할 수 있어야 한다.

| 관찰 대상 | 필수 지표 |
|---|---|
| Ingestion | stage duration, failure reason, retry count, parser warnings |
| OCR | page confidence, low-confidence pages, fallback count |
| Embedding | batch size, model version, queue wait, failure rate |
| Retrieval | top-k hit, keyword hit, rerank score, ACL filtered count |
| Generation | model, token count, latency, fallback, streaming status |
| Trust | unsupported claim rate, citation precision, groundedness score |
| GB10 | CPU, memory, GPU utilization, unified memory pressure, disk I/O, temperature |

---

## 11. Risks and Mitigations

| 우선순위 | 리스크 | 영향 | 대응 |
|---|---|---|---|
| Critical | ACL/권한 필터 누락 | 권한 없는 문서 또는 키워드 노출 | Vector DB filter + Postgres double-check + seeded unauthorized test |
| Critical | citation 불일치·환각 | 제품 신뢰성 붕괴 | citation validator, groundedness eval, unsupported claim detector |
| High | 전처리 품질 편차 | 검색 품질과 답변 품질 저하 | parser quality gate, fallback chain, golden document set |
| High | GB10 리소스 경합 | OOM, latency spike, 서비스 불안정 | worker queue, concurrency limit, memory cap, telemetry |
| High | Vector DB 운영 리스크 | 장애 복구 불가 또는 재색인 실패 | snapshot, restore drill, embedding versioning, blue/green collection |
| Medium | MarkItDown 변환 손실 | 표·슬라이드·엑셀 질의 품질 저하 | Markdown 외 table JSON, sheet metadata, diff evaluation 저장 |
| Medium | HWPX edge case | 한국 문서 처리 누락 | schema variation corpus, native parser regression, render+OCR fallback |
| Medium | 시각화 오해 | 키워드·그래프가 실제 중요도와 다르게 보임 | hybrid keyword score, confidence 표시, top-N 제한 |
| Medium | 화려한 UI로 신뢰도 저하 | 기업용 도구로서 진지함 약화 | Clean Professional 기본 테마, 화려한 요소는 온보딩·그래프에 제한 |
| Medium | 모바일 3-pane 복잡도 | 사용성 저하 | bottom sheet, drawer, single-column fallback |

---

## 12. Implementation Plan for Claude

Claude Code는 터미널, IDE, GitHub 등에서 프로젝트를 이해하고 자연어 기반으로 작업을 수행하는 agentic coding 도구로 설명되며, 프로젝트 파일을 읽고 변경을 제안하고 테스트와 Git workflow를 보조할 수 있다.[7] [8] 본 PRD는 Claude가 작업을 독립적인 PR 단위로 분해할 수 있도록 monorepo 구조, 모듈 경계, 요구사항 ID, 테스트 기준을 명시한다.

### 12.1 Recommended Repository Structure

```text
hybrid-idp/
  apps/
    web/                         # Next.js UI
    api/                         # FastAPI API server
  workers/
    markitdown_worker/           # Office/target preprocessing
    ocr_worker/                  # PaddleOCR/PaddleOCR-VL
    hwpx_worker/                 # HWPX native parser
    embedding_worker/            # embedding and vector indexing
    eval_worker/                 # citation and groundedness eval
  packages/
    shared/                      # shared types, OpenAPI client, constants
    document_ir/                 # IR schema and validators
    rag_core/                    # retrieval, reranking, citation logic
  infra/
    docker/                      # Dockerfiles
    compose/                     # docker-compose files
    harness/                     # Harness pipeline YAML templates
    migrations/                  # DB migrations
  tests/
    fixtures/                    # golden documents and query sets
    unit/
    integration/
    e2e/
    performance/
  docs/
    adr/
    runbooks/
    CLAUDE.md
    PRD.md
```

### 12.2 Claude Working Instructions

`docs/CLAUDE.md` 또는 repository root `CLAUDE.md`에는 다음 지침을 둔다. 이 지침은 Claude가 기능 구현 시 PRD와 테스트를 먼저 읽고, 작은 변경 단위로 작업하도록 유도한다.

```markdown
# CLAUDE.md

## Project Rules
- Read `docs/PRD.md` and related ADR before implementation.
- Do not change public API contracts without updating OpenAPI schemas and tests.
- Every feature must include unit tests, integration tests, and acceptance notes.
- Never bypass ACL middleware in document, search, visualization, or chat APIs.
- All preprocessing outputs must validate against Document IR schema.
- New vector payload fields require migration and retrieval tests.
- UI changes must include accessibility checks and responsive behavior.
- For risky changes, create an ADR under `docs/adr/`.

## Preferred Workflow
1. Inspect the existing module and tests.
2. Implement the smallest vertical slice.
3. Run relevant tests locally.
4. Update docs and acceptance checklist.
5. Prepare a concise commit message referencing requirement IDs.
```

### 12.3 Claude Task Breakdown

| Epic | Claude 작업 단위 | 주요 요구사항 ID | 완료 기준 |
|---|---|---|---|
| E1: Foundation | monorepo scaffold, shared config, Docker base images | INFRA-001 | local compose가 API, UI, Postgres를 실행한다. |
| E2: Document IR | IR schema, validators, fixtures | IR-001 | MarkItDown/OCR/HWPX 산출물이 동일 schema를 통과한다. |
| E3: MarkItDown | adapter, table JSON, quality metric | MD-001~005 | Office 샘플 변환과 snapshot test 통과 |
| E4: OCR/PDF | PDF classifier, PaddleOCR integration, bbox storage | OCR-001~006 | scanned PDF fixture에서 page OCR 결과 생성 |
| E5: HWPX | native parser, table/style/metadata extraction | HWPX-001~006 | HWPX fixture에서 TOC와 keyword 생성 |
| E6: Indexing | chunker, embedding worker, Vector DB writer | IDX-001 | payload filter 가능한 vector index 생성 |
| E7: RAG | retrieval, reranking, context packing, chat API | RAG-001 | 인용 포함 답변 생성 |
| E8: Trust | citation validator, eval worker, guardrails | TRUST-001 | seeded hallucination과 injection test 통과 |
| E9: UI Core | document library, upload center, chat workspace | UI-DOC, UI-CHAT | 문서 선택 기반 질의 동작 |
| E10: UI Insight | TOC, word cloud, graph, quality panel | UI-VIZ | keyword click → section highlight 동작 |
| E11: Admin/Ops | health dashboard, job logs, metrics | OPS-001 | 전처리 실패 원인과 모델 latency 확인 가능 |
| E12: CI/CD | Harness pipeline, Docker image, deploy scripts | CICD-001 | dev 배포와 smoke test 자동화 |

### 12.4 Pull Request Acceptance Template

```markdown
## Requirement IDs
- 예: MD-001, IR-001

## Summary
변경 내용을 3~5문장으로 설명한다.

## Tests
- [ ] Unit tests passed
- [ ] Integration tests passed
- [ ] E2E or fixture tests passed
- [ ] ACL/security tests updated if applicable

## Observability
- [ ] Logs/metrics/traces added or not applicable

## Documentation
- [ ] PRD/ADR/OpenAPI/README updated or not applicable

## Risk
- [ ] Rollback path documented
- [ ] Migration backward compatibility checked
```

---

## 13. Harness CI/CD Plan

Harness는 YAML로 pipeline을 작성할 수 있고, stage, input set, overlays, failure handling, conditional execution, matrices, loops, parallelism, execution logs 등을 지원한다.[9] Harness CD와 GitOps는 인프라에 애플리케이션 변경을 안전하고 지속 가능한 방식으로 배포하고, 배포 검증과 모니터링을 제공하는 흐름을 지원한다.[10] 본 PRD는 Harness를 기준으로 CI, 보안 검사, 이미지 빌드, dev 배포, smoke test, prod 승인, 검증, rollback을 정의한다.

### 13.1 Pipeline Overview

| Stage | 목적 | Gate |
|---|---|---|
| `source-checkout` | Git commit checkout, PR metadata 수집 | branch policy |
| `lint-and-typecheck` | web/API/workers lint, type check | 실패 시 중단 |
| `unit-tests` | Python/TypeScript unit test | coverage threshold |
| `integration-tests` | Postgres, Vector DB, object store, workers 통합 테스트 | fixture pass |
| `security-scan` | dependency scan, secret scan, container scan | critical vulnerability 차단 |
| `build-images` | UI/API/workers Docker image build | image tag 생성 |
| `push-images` | registry push | signed/provenance optional |
| `deploy-dev` | GB10 dev 또는 staging 노드 compose 배포 | healthcheck pass |
| `smoke-tests` | upload, ingest, chat, citation, UI smoke | 실패 시 rollback |
| `eval-gate` | golden query set 최소 평가 | Recall@10, citation accuracy 기준 |
| `manual-approval-prod` | 운영 배포 승인 | admin approval |
| `deploy-prod` | prod compose pull/up 또는 GitOps sync | healthcheck pass |
| `continuous-verification` | latency, error, groundedness, hardware telemetry 검증 | threshold breach 시 rollback |
| `rollback` | 이전 image tag와 DB migration 정책 적용 | runbook 실행 |

### 13.2 Harness Pipeline YAML Skeleton

아래 YAML은 실제 Harness 계정·프로젝트·connector 이름에 맞게 수정해야 하는 skeleton이다. 목적은 개발팀이 Harness에서 pipeline stage를 어떻게 구성할지 명확히 하는 것이다.

```yaml
pipeline:
  name: hybrid-idp-ci-cd
  identifier: hybrid_idp_ci_cd
  projectIdentifier: hybrid_idp
  orgIdentifier: default
  tags:
    product: hybrid-idp
  stages:
    - stage:
        name: ci-build-test
        identifier: ci_build_test
        type: CI
        spec:
          cloneCodebase: true
          execution:
            steps:
              - step:
                  name: lint-and-typecheck
                  identifier: lint_typecheck
                  type: Run
                  spec:
                    shell: Bash
                    command: |
                      pnpm install --frozen-lockfile
                      pnpm lint
                      pnpm typecheck
                      python -m ruff check apps workers packages
              - step:
                  name: unit-tests
                  identifier: unit_tests
                  type: Run
                  spec:
                    shell: Bash
                    command: |
                      pnpm test
                      pytest tests/unit -q
              - step:
                  name: integration-tests
                  identifier: integration_tests
                  type: Run
                  spec:
                    shell: Bash
                    command: |
                      docker compose -f infra/compose/test.yml up -d
                      pytest tests/integration -q
                      docker compose -f infra/compose/test.yml down -v
    - stage:
        name: security-scan
        identifier: security_scan
        type: CI
        spec:
          execution:
            steps:
              - step:
                  name: dependency-and-secret-scan
                  identifier: dep_secret_scan
                  type: Run
                  spec:
                    shell: Bash
                    command: |
                      pnpm audit --audit-level high
                      pip-audit || true
                      gitleaks detect --no-git -v
    - stage:
        name: build-and-push-images
        identifier: build_push_images
        type: CI
        spec:
          execution:
            steps:
              - step:
                  name: build-images
                  identifier: build_images
                  type: Run
                  spec:
                    shell: Bash
                    command: |
                      docker build -t registry.example.com/hybrid-idp/api:${HARNESS_BUILD_ID} -f infra/docker/api.Dockerfile .
                      docker build -t registry.example.com/hybrid-idp/ui:${HARNESS_BUILD_ID} -f infra/docker/ui.Dockerfile .
                      docker build -t registry.example.com/hybrid-idp/worker-ocr:${HARNESS_BUILD_ID} -f infra/docker/worker-ocr.Dockerfile .
              - step:
                  name: push-images
                  identifier: push_images
                  type: Run
                  spec:
                    shell: Bash
                    command: |
                      docker push registry.example.com/hybrid-idp/api:${HARNESS_BUILD_ID}
                      docker push registry.example.com/hybrid-idp/ui:${HARNESS_BUILD_ID}
                      docker push registry.example.com/hybrid-idp/worker-ocr:${HARNESS_BUILD_ID}
    - stage:
        name: deploy-dev-and-verify
        identifier: deploy_dev_verify
        type: Deployment
        spec:
          serviceConfig:
            serviceRef: hybrid_idp
          execution:
            steps:
              - step:
                  name: deploy-compose
                  identifier: deploy_compose
                  type: ShellScript
                  spec:
                    shell: Bash
                    source:
                      type: Inline
                      spec:
                        script: |
                          export IMAGE_TAG=${HARNESS_BUILD_ID}
                          docker compose -f infra/compose/dev.yml pull
                          docker compose -f infra/compose/dev.yml up -d
              - step:
                  name: smoke-tests
                  identifier: smoke_tests
                  type: ShellScript
                  spec:
                    shell: Bash
                    source:
                      type: Inline
                      spec:
                        script: |
                          pytest tests/e2e/smoke -q
              - step:
                  name: eval-gate
                  identifier: eval_gate
                  type: ShellScript
                  spec:
                    shell: Bash
                    source:
                      type: Inline
                      spec:
                        script: |
                          pytest tests/eval -q --min-recall=0.90 --min-citation=0.90
```

### 13.3 CI Test Matrix

| 테스트 유형 | 포함 항목 | 차단 기준 |
|---|---|---|
| Unit | parser, IR validator, chunker, ACL filter, UI components | 실패 시 merge 차단 |
| Integration | upload→worker→IR→Vector DB→chat | P0 fixture 실패 시 차단 |
| E2E | 문서 업로드, 상태 뱃지, 문서 선택, 질문, citation click | 주요 user path 실패 시 차단 |
| Security | unauthorized query, PII redaction, prompt injection | Critical 실패 시 차단 |
| Performance | document card render, graph render, chat latency smoke | 기준 초과 시 경고 또는 차단 |
| Eval | golden query Recall@10, MRR, citation accuracy | 운영 배포 전 차단 |

---

## 14. Release Plan and Acceptance Criteria

### 14.1 Release Sequence

| Phase | 목표 | 포함 기능 | 완료 기준 |
|---|---|---|---|
| Phase 0 / MVP | 운영 가능한 최소 RAG | MarkItDown DOCX, PDF OCR, HWPX parser, Vector DB, chat citation, 문서 아이콘 뷰 | 샘플 문서 4종 end-to-end 성공 |
| Phase 1 / Beta | 포맷 확대와 UI insight | XLSX/PPTX/HTML/CSV/JSON/XML, 워드 클라우드, 목차 트리뷰, 품질 경고 | 문서 선택→키워드 클릭→질문 경로 성공 |
| Phase 2 | 평가와 관리자 운영 | retrieval eval, admin dashboard, model routing, ACL audit, prompt injection tests | nightly eval과 admin health dashboard 동작 |
| Phase 3 | GB10 최적화 | worker scheduling, caching, batching, telemetry, backup/restore | p95 latency와 restore drill 기준 충족 |
| Phase 4 | 확장 옵션 | OIDC/SAML, cold standby, 외부 object store, 외부 Vector DB, GitOps | 운영 조직 요구에 맞게 선택 적용 |

### 14.2 MVP Acceptance Checklist

| 영역 | 체크 항목 | 통과 기준 |
|---|---|---|
| Upload | PDF, DOCX, HWPX 업로드 | job 생성과 상태 업데이트 성공 |
| Preprocessing | MarkItDown, OCR, HWPX parser | IR schema validation 통과 |
| Indexing | Vector DB payload 저장 | ACL, citation, keyword payload 포함 |
| Chat | 문서 선택 기반 질의 | citation이 포함된 답변 생성 |
| UI | 문서 카드, 목차, keyword list | 클릭 시 scope와 추천 질문 갱신 |
| Security | 권한 없는 문서 질의 | 검색 결과와 UI 시각화 모두 차단 |
| Observability | job log, parser warning, latency | 관리자 화면 또는 log에서 확인 가능 |
| CI/CD | Harness dev 배포 | smoke test와 eval gate 통과 |

---

## 15. Decision Records to Create

개발 초기에는 다음 ADR을 반드시 작성한다. ADR은 의사결정의 이유, 대안, 결과, 되돌릴 수 있는 조건을 포함해야 한다.

| ADR | 결정 항목 | 초기 권장안 |
|---|---|---|
| ADR-0001 | Retrieval architecture | Vector DB 중심 hybrid retrieval + 구조 인덱스 보조 |
| ADR-0002 | Vector DB backend | P0에서 Qdrant와 pgvector 벤치마크 후 선택 |
| ADR-0003 | MarkItDown role | Office 및 지원 포맷 기본 preprocessing engine |
| ADR-0004 | PDF processing | layout-sensitive digital PDF는 PaddleOCR-VL, scan은 PaddleOCR/PaddleOCR-VL |
| ADR-0005 | HWPX strategy | native XML parser 우선, 실패 시 render+OCR fallback |
| ADR-0006 | Embedding model | 한국어·영어·GB10 리소스 기준으로 선정 |
| ADR-0007 | Model routing | rule-based v1, P2에서 LLM-judged routing 실험 |
| ADR-0008 | Deployment | GB10 단일 노드 Docker Compose 우선 |
| ADR-0009 | UI graph library | React Flow, Cytoscape.js, Sigma.js, ECharts Graph 중 선택 |
| ADR-0010 | Evaluation | golden query set + citation validator + LLM-as-judge 혼합 평가 |

---

## 16. References

[1]: https://github.com/microsoft/markitdown "Microsoft MarkItDown GitHub Repository"  
[2]: https://github.com/PaddlePaddle/PaddleOCR "PaddleOCR GitHub Repository"  
[3]: https://www.nvidia.com/en-us/products/workstations/dgx-spark/ "NVIDIA DGX Spark Product Page"  
[4]: https://docs.nvidia.com/dgx/dgx-spark-user-guide/latest/ "NVIDIA DGX Spark User Guide"  
[5]: https://fuselabcreative.com/chatbot-interface-design-guide/ "Fuselab Creative, Chatbot Interface Design Guide"  
[6]: https://sendbird.com/blog/chatbot-ui "Sendbird, Chatbot UI Examples"  
[7]: https://code.claude.com/docs/en/quickstart "Claude Code Quickstart"  
[8]: https://github.com/anthropics/claude-code "Anthropic Claude Code GitHub Repository"  
[9]: https://developer.harness.io/docs/category/pipelines/ "Harness Pipelines Documentation"  
[10]: https://developer.harness.io/docs/continuous-delivery "Harness Continuous Delivery and GitOps Documentation"

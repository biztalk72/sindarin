# Test fixtures

Golden documents and query sets (CLAUDE.md §5: new format → fixture + parser test + e2e).

- **`ir/` — golden Document IR** (E2/IR-001): one expected-output JSON per parser
  (`markitdown_docx`, `markitdown_xlsx`, `paddleocr_vl_pdf`, `hwpx`). These stand in for
  worker output until the parsers exist and are asserted to pass `document_ir.validate_ir`
  by `tests/unit/test_ir_validator.py`. When a worker is implemented, its real output must
  validate against the same gate. Add one IR fixture per new format/parser.
- **Documents:** sample PDF (digital + scanned), DOCX, XLSX, PPTX, HWPX, image, HTML — at
  least the MVP four (PDF, DOCX, HWPX, image) for end-to-end coverage (PRD2 §14.1 Phase 0).
- **Golden query set:** bilingual KO/EN questions with expected `{document_id, page_no}`
  citations, used by `tests/eval` against `thresholds.toml`.

Keep fixtures small and license-clean. Large binaries should be tracked out-of-band, not
committed raw, once a strategy is chosen.

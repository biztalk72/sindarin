"use client";

import { useRef, useState } from "react";

import { type DocumentCard, uploadDocument } from "@/lib/api";

const TYPE_ICON: Record<string, string> = {
  pdf: "📄",
  docx: "📝",
  xlsx: "📊",
  pptx: "📑",
  hwpx: "🇰🇷",
  image: "🖼️",
  html: "🌐",
  csv: "🔢",
  json: "🧩",
  xml: "🧬",
};

const STATUS_LABEL: Record<string, string> = {
  uploaded: "업로드됨",
  preprocessing: "전처리 중",
  ocr: "OCR 중",
  keywords: "키워드 추출 중",
  indexed: "색인 완료",
  error: "오류",
  needs_reprocess: "재처리 필요",
};

interface Props {
  documents: DocumentCard[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  onChanged: () => void; // refetch after upload
}

export function DocumentLibrary({ documents, selected, onToggle, onChanged }: Props) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of Array.from(files)) {
        await uploadDocument(file);
      }
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "upload failed");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  return (
    <div className="library">
      <h1 className="brand">Hybrid IDP</h1>

      <button
        type="button"
        className="upload-btn"
        disabled={uploading}
        onClick={() => fileInput.current?.click()}
      >
        {uploading ? "업로드 중… / Uploading…" : "+ 문서 업로드 / Upload"}
      </button>
      <input
        ref={fileInput}
        type="file"
        multiple
        hidden
        aria-label="upload documents"
        onChange={(e) => void onFiles(e.target.files)}
      />
      {error && <p className="upload-error">{error}</p>}

      {documents.length === 0 ? (
        <p className="pane-placeholder">문서가 없습니다. 업로드하세요 / No documents yet — upload one.</p>
      ) : (
        <ul className="doc-list">
          {documents.map((d) => (
            <li key={d.id}>
              <label className={`doc-card${selected.has(d.id) ? " selected" : ""}`}>
                <input
                  type="checkbox"
                  checked={selected.has(d.id)}
                  onChange={() => onToggle(d.id)}
                  aria-label={`select ${d.name}`}
                />
                <span className="doc-icon" aria-hidden>
                  {TYPE_ICON[d.type] ?? "📄"}
                </span>
                <span className="doc-body">
                  <span className="doc-name" title={d.name}>
                    {d.name}
                  </span>
                  <span className="doc-meta">
                    <span className={`status-badge status-${d.status}`}>
                      {STATUS_LABEL[d.status] ?? d.status}
                    </span>
                    <span className="doc-chunks">{d.chunk_count} chunks</span>
                  </span>
                </span>
              </label>
            </li>
          ))}
        </ul>
      )}

      {selected.size > 0 && (
        <p className="scope-note">{selected.size}개 문서로 질의 범위 지정 / scoped to {selected.size}</p>
      )}
    </div>
  );
}

"use client";

import { type FormEvent, useRef, useState } from "react";

import { ApiError, type ChatResponse, type PreviewTarget, postChat } from "@/lib/api";
import { CitationChip } from "@/components/CitationChip";

interface Message {
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse;
  error?: boolean;
}

const SUGGESTED = [
  "이 문서의 핵심 내용을 요약해줘",
  "위약금 조건을 알려줘",
  "What are the key dates mentioned?",
];

function groundednessPct(r?: ChatResponse): number | null {
  const g = r?.confidence?.groundedness;
  return typeof g === "number" ? Math.round(g * 100) : null;
}

export default function ChatWorkspace({
  scopeDocumentIds = [],
  onOpenPreview,
}: {
  scopeDocumentIds?: string[];
  onOpenPreview?: (target: PreviewTarget) => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const listEnd = useRef<HTMLDivElement>(null);

  async function send(text: string) {
    const message = text.trim();
    if (!message || loading) return;
    setMessages((m) => [...m, { role: "user", content: message }]);
    setInput("");
    setLoading(true);
    try {
      const response = await postChat(message, "answer", scopeDocumentIds);
      setMessages((m) => [...m, { role: "assistant", content: response.answer, response }]);
    } catch (err) {
      const detail = err instanceof ApiError ? err.message : "요청에 실패했습니다 / request failed";
      setMessages((m) => [...m, { role: "assistant", content: detail, error: true }]);
    } finally {
      setLoading(false);
      requestAnimationFrame(() => listEnd.current?.scrollIntoView({ behavior: "smooth" }));
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void send(input);
  }

  return (
    <div className="chat">
      <div className="chat-messages" role="log" aria-live="polite">
        {messages.length === 0 && (
          <div className="empty-state">
            <h2>문서에 대해 질문하세요 / Ask about your documents</h2>
            <p>근거가 검증된 답변만 표시됩니다. Answers are shown only with verified citations.</p>
            <div className="suggested">
              {SUGGESTED.map((s) => (
                <button key={s} type="button" className="suggested-prompt" onClick={() => void send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}${m.error ? " error" : ""}`}>
            <div className="bubble-content">{m.content}</div>

            {m.response && (
              <div className="answer-meta">
                {m.response.citations.length > 0 ? (
                  <div className="citations">
                    {m.response.citations.map((c, idx) => (
                      <CitationChip
                        key={c.chunk_id + idx}
                        citation={c}
                        index={idx}
                        onClick={
                          onOpenPreview
                            ? (cit) =>
                                onOpenPreview({
                                  documentId: cit.document_id,
                                  span: cit.source_span,
                                  page_no: cit.page_no,
                                })
                            : undefined
                        }
                      />
                    ))}
                  </div>
                ) : (
                  <div className="no-citations">근거 없음 / no citations</div>
                )}

                <div className="confidence">
                  {groundednessPct(m.response) != null && (
                    <span className="conf-badge">groundedness {groundednessPct(m.response)}%</span>
                  )}
                  {m.response.warnings.map((w) => (
                    <span key={w} className="warning-badge" title={w}>
                      ⚠ {w}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}

        {loading && <div className="bubble assistant loading">생각 중… / thinking…</div>}
        <div ref={listEnd} />
      </div>

      <form className="composer" onSubmit={onSubmit}>
        <input
          type="text"
          aria-label="질문 입력 / message"
          placeholder="질문을 입력하세요 / Type your question"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          보내기 / Send
        </button>
      </form>
    </div>
  );
}

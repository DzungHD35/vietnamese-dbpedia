import type { AskSteps, Attempt, Check, LinkResult, TermUse } from "../api/types";
import { formatMs, formatNumber } from "../utils/format";
import { EntityLink } from "./EntityLink";
import { SparqlBlock } from "./SparqlBlock";

const VIO = "http://vi.dbpedia.org/ontology/";

export type StepState = "wait" | "run" | "done" | "warn" | "fail" | "skip";

export interface PipelineStep {
  n: number;
  title: string;
  state: StepState;
  note?: string;
}

const STATE_ICON: Record<StepState, string> = { wait: "○", run: "…", done: "✓", warn: "!", fail: "✗", skip: "–" };

/** Thanh tiến trình ①–⑥ ở đầu kết quả: mỗi bước một ô, bấm để cuộn tới thẻ của bước đó. */
export function Pipeline({ steps }: { steps: PipelineStep[] }) {
  return (
    <ol className="ask-pipeline" aria-label="Các bước của luồng hỏi đáp">
      {steps.map((s) => (
        <li key={s.n} className={`ask-pipe ask-pipe-${s.state}`}>
          <a href={`#ask-step-${s.n}`}>
            <span className="ask-pipe-icon" aria-hidden="true">
              {STATE_ICON[s.state]}
            </span>
            <span className="ask-pipe-title">
              {s.n}. {s.title}
            </span>
            {s.note && <span className="ask-pipe-note">{s.note}</span>}
          </a>
        </li>
      ))}
    </ol>
  );
}

/** Bước ①: các tên tìm thấy trong câu hỏi và thực thể ứng với từng tên. */
export function LinkStep({ link, llm }: { link: LinkResult; llm: boolean }) {
  if (link.mentions.length === 0) {
    return (
      <p className="muted">
        Không thấy tên thực thể nào trong câu hỏi
        {llm
          ? ": LLM tự tìm thực thể theo nhãn trong SPARQL. Lần 1 tìm nhãn chứa nguyên cụm tên; nếu ra 0 dòng, lần 2 tách cụm theo khoảng trắng và tìm nhãn chứa đủ từng từ."
          : "."}
      </p>
    );
  }
  return (
    <>
      <ul className="mentions">
        {link.mentions.map((m) => (
          <li key={m.text}>
            <span className="mention-text">“{m.text}”</span>
            <span className="muted small">{m.match === "exact" ? "khớp tên" : "khớp phần cuối tên"} →</span>
            <span className="mention-cands">
              {m.candidates.map((c) => (
                <span key={c.id} className="mention-cand">
                  <EntityLink node={c} />
                  {c.cls && <span className="muted small"> · {c.cls}</span>}
                </span>
              ))}
            </span>
            {m.candidates.length > 1 && (
              <span className="mention-warn small">
                trùng tên: {m.candidates.length} thực thể{llm ? ", LLM được dặn giữ tất cả" : ""}
              </span>
            )}
          </li>
        ))}
      </ul>
      <p className="muted small">
        Tìm bằng chỉ mục nhãn và tên khác (redirect), không phân biệt dấu.{" "}
        {llm ? "Các IRI này được gửi kèm prompt ở bước 2, để LLM không phải đoán chuỗi tìm theo tên." : "SPARQL viết sẵn tự tìm thực thể theo nhãn, không dùng bước này."}
      </p>
    </>
  );
}

const ATTEMPT_LABEL: Record<Attempt["status"], string> = {
  ok: "chạy được",
  empty: "chạy được nhưng 0 dòng",
  error: "lỗi",
};

const ATTEMPT_BY: Record<Attempt["by"], (a: Attempt) => string> = {
  llm: (a) => `LLM ${formatMs(a.llmMs)}`,
  cache: () => "viết sẵn",
  system: () => "hệ thống tự sửa, không gọi LLM",
};

function AttemptRow({ a, last }: { a: Attempt; last: boolean }) {
  const head = (
    <>
      <span className={`attempt-badge attempt-${a.status}`}>
        {a.status === "ok" ? "✓" : a.status === "empty" ? "∅" : "✗"} Lần {a.n}: {ATTEMPT_LABEL[a.status]}
        {a.status === "ok" && `, ${formatNumber(a.rows)} dòng`}
      </span>
      <span className="muted small">
        {ATTEMPT_BY[a.by](a)} · chạy {formatMs(a.runMs)}
      </span>
    </>
  );
  return (
    <li className="attempt">
      {a.feedback && a.by === "system" && <p className="muted small attempt-system">{a.feedback}</p>}
      {a.feedback && a.by !== "system" && (
        <details className="attempt-feedback">
          <summary>Phản hồi gửi lại LLM trước lần {a.n}</summary>
          <pre>{a.feedback}</pre>
        </details>
      )}
      {last ? (
        <div className="attempt-head">{head}</div>
      ) : (
        <details>
          <summary className="attempt-head">{head}</summary>
          <SparqlBlock sparql={a.sparql} openable={false} />
        </details>
      )}
      {a.error && <p className="attempt-message">{a.error}</p>}
    </li>
  );
}

/** Bước ②: nguồn SPARQL, các lần thử (kể cả lần LLM tự sửa) và prompt đã gửi. */
export function GenerateStep({ gen, sparql, onFresh }: { gen: AskSteps["generate"]; sparql: string; onFresh: () => void }) {
  const cached = gen.source === "cache";
  const attempts = gen.attempts;
  return (
    <>
      {gen.fallback && <p className="demo-note small">{gen.fallback}</p>}
      {gen.reused && (
        <div className="ask-skip">
          <p className="muted small">
            Kết quả LLM của lần hỏi trước trong phiên này: không gọi lại LLM, không tốn thêm request (thời gian bên dưới là của lần
            gọi đó).
          </p>
          <button type="button" className="btn" onClick={onFresh}>
            Gọi lại LLM
          </button>
        </div>
      )}
      {cached && !gen.fallback && (
        <p className="muted small">SPARQL viết sẵn cho câu hỏi mẫu này, không gọi LLM (vì chưa có API key).</p>
      )}
      {!cached && (attempts.length > 1 || attempts[0]?.status !== "ok") && (
        <p className="muted small">Truy vấn lỗi hoặc ra 0 dòng thì lỗi được gửi lại để LLM tự sửa.</p>
      )}
      <ol className="attempts">
        {attempts.map((a, i) => (
          <AttemptRow key={a.n} a={a} last={i === attempts.length - 1} />
        ))}
      </ol>
      {sparql && <SparqlBlock sparql={sparql} />}
      {gen.prompt && (
        <details className="prompt">
          <summary>
            Prompt gửi LLM ({formatNumber(gen.prompt.length)} ký tự): schema của graph, quy tắc, 6 ví dụ, thực thể ở bước 1
          </summary>
          <pre>{gen.prompt}</pre>
        </details>
      )}
    </>
  );
}

const CHECK_ICON: Record<Check["status"], string> = { ok: "✓", warn: "!", fail: "✗", info: "i" };

function TermRow({ t }: { t: TermUse }) {
  const share = t.total ? Math.round((t.inferred / t.total) * 100) : 0;
  const name = t.iri.startsWith(VIO) ? (
    <a href={`/ontology/${encodeURIComponent(t.iri.slice(VIO.length))}`} target="_blank" rel="noopener noreferrer" title={t.iri}>
      <code>{t.term}</code> ↗
    </a>
  ) : (
    <code title={t.iri}>{t.term}</code>
  );
  return (
    <li>
      {name}
      <span className="muted small">
        {t.kind === "class" ? "lớp" : "thuộc tính"} · {formatNumber(t.total)} triple
      </span>
      {t.inferred > 0 && (
        <span className="term-inferred small">
          {share === 100 ? "toàn bộ" : `${share}%`} do suy luận OWL 2 RL
        </span>
      )}
    </li>
  );
}

/** Bước ③: kiểm tra truy vấn trước khi tin kết quả, và thuật ngữ ontology mà truy vấn dựa vào. */
export function CheckStep({ checks, terms }: { checks: Check[]; terms: TermUse[] }) {
  return (
    <>
      <ul className="checks">
        {checks.map((c) => (
          <li key={c.label} className={`check check-${c.status}`}>
            <span className="check-icon" aria-hidden="true">
              {CHECK_ICON[c.status]}
            </span>
            <b>{c.label}</b>
            <span className="muted small">{c.detail}</span>
          </li>
        ))}
      </ul>
      {terms.length > 0 && (
        <>
          <h3 className="sub-title">Thuật ngữ ontology trong truy vấn</h3>
          <ul className="terms">
            {terms.map((t) => (
              <TermRow key={t.iri} t={t} />
            ))}
          </ul>
        </>
      )}
    </>
  );
}

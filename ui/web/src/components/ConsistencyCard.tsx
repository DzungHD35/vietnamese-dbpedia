import { useRef, useState } from "react";
import { postJson } from "../api/client";
import type { ConsistencyPreset, ConsistencyResult, Node, SchemaTerm } from "../api/types";
import { formatNumber } from "../utils/format";
import { EntityLink } from "./EntityLink";
import { ErrorState, Loading } from "./States";

type Triple = { subject: string; predicate: string; object: string };

function Term({ t }: { t: Node | SchemaTerm }) {
  return "qname" in t ? <code title={t.qname}>{t.label}</code> : <EntityLink node={t} />;
}

/** Thử thêm một triple sai rồi chạy reasoner: ontology có bắt được dữ liệu vô lý không? Graph thật không đổi. */
export function ConsistencyCard({ entityId, presets }: { entityId: string; presets: ConsistencyPreset[] }) {
  const [state, setState] = useState<{ data: ConsistencyResult | null; error: string | null; loading: boolean }>({
    data: null,
    error: null,
    loading: false,
  });
  const [active, setActive] = useState<string | null>(null);
  const [form, setForm] = useState<Triple>({ subject: entityId, predicate: "vio:ground", object: "" });
  const controller = useRef<AbortController | null>(null);

  const check = (t: Triple, key: string) => {
    controller.current?.abort();
    const ctl = new AbortController();
    controller.current = ctl;
    setActive(key);
    setState({ data: null, error: null, loading: true });
    postJson<ConsistencyResult>("/api/consistency", t, ctl.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((e: unknown) => {
        if (!ctl.signal.aborted) setState({ data: null, error: e instanceof Error ? e.message : String(e), loading: false });
      });
  };

  return (
    <section className="card consistency">
      <h2>Thử thêm dữ liệu sai: ontology có bắt được không?</h2>
      <p className="muted small">
        Chọn một triple. Reasoner OWL 2 RL chạy lại trên phần graph quanh thực thể; graph thật không thay đổi.
      </p>
      <div className="cons-presets">
        {presets.map((p) => {
          const key = `${p.subject}|${p.predicate}|${p.object}`;
          return (
            <button
              key={key}
              type="button"
              className={`cons-preset${active === key ? " active" : ""}`}
              onClick={() => check(p, key)}
            >
              <span className="cons-triple">
                {p.p.label} → {p.o.label}
              </span>
              <span className="muted small">{p.note}</span>
            </button>
          );
        })}
      </div>
      <details className="cons-free">
        <summary className="small">Tự nhập triple</summary>
        <form
          className="cons-form"
          onSubmit={(e) => {
            e.preventDefault();
            check(form, "free");
          }}
        >
          {(["subject", "predicate", "object"] as const).map((f) => (
            <input
              key={f}
              aria-label={f}
              placeholder={{ subject: "chủ ngữ (local name)", predicate: "thuộc tính (vio:…, rdf:type)", object: "tân ngữ (local name hoặc vio:Lớp)" }[f]}
              value={form[f]}
              onChange={(e) => setForm({ ...form, [f]: e.target.value })}
            />
          ))}
          <button type="submit" className="btn" disabled={state.loading}>
            Kiểm tra
          </button>
        </form>
      </details>

      {state.loading && <Loading text="Đang chạy reasoner…" />}
      {state.error && <ErrorState message={state.error} />}
      {state.data && <Verdict r={state.data} />}
    </section>
  );
}

function Verdict({ r }: { r: ConsistencyResult }) {
  const { domain, range } = r.axioms;
  return (
    <div className={`cons-result ${r.consistent ? "ok" : "bad"}`}>
      <div className="cons-head">
        <b>{r.consistent ? "✓ Không mâu thuẫn" : "✗ Mâu thuẫn"}</b>
        <span className="muted small">
          reasoner chạy trên {formatNumber(r.triples)} triple · {formatNumber(r.ms)} ms
        </span>
      </div>
      <ol className="cons-steps">
        <li>
          Thêm: <Term t={r.triple.s} /> <code>{r.triple.p.qname}</code> <Term t={r.triple.o} />
        </li>
        {(domain || range) && (
          <li>
            Ontology: <code>{r.triple.p.qname}</code>
            {domain && (
              <>
                {" "}
                có <code>rdfs:domain</code> <code>{domain.label}</code>
              </>
            )}
            {domain && range && ","}
            {range && (
              <>
                {" "}
                <code>rdfs:range</code> <code>{range.label}</code>
              </>
            )}
          </li>
        )}
        {r.gained.length > 0 && (
          <li>
            Máy suy ra:{" "}
            {r.gained.map((g, i) => (
              <span key={i}>
                {i > 0 && "; "}
                <EntityLink node={g.node} /> là <b className="inferred-text">{g.cls.label}</b>
              </span>
            ))}
          </li>
        )}
        {r.conflicts.map((c, i) => (
          <li key={i}>
            Nhưng <code>{c.classes[0].label}</code> và <code>{c.classes[1].label}</code> được khai báo tách rời (
            <code>owl:AllDisjointClasses</code>) → <EntityLink node={c.individual} /> không thể vừa là cái này vừa là
            cái kia.
          </li>
        ))}
        {r.errors.map((m, i) => (
          <li key={`e${i}`}>
            <code>{m}</code>
          </li>
        ))}
      </ol>
      {r.consistent && (
        <p className="small muted">
          Triple đúng loại nên không mâu thuẫn, dù có thể sai sự thật: ontology kiểm tra <i>loại</i> của thực thể,
          không kiểm tra sự thật (giả định thế giới mở).
        </p>
      )}
    </div>
  );
}

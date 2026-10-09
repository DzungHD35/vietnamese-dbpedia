import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { postJson } from "../api/client";
import type { ConsistencyPreset, ConsistencyResult, Node, SchemaTerm } from "../api/types";
import { formatNumber } from "../utils/format";
import { kindColorVar } from "../utils/kinds";
import { ErrorState, Loading } from "./States";

type Triple = { subject: string; predicate: string; object: string };

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
      <h2>Nếu crawler đọc nhầm infobox? Ontology có bắt được không</h2>
      <p className="muted small">
        Chọn một lỗi giả lập: thêm thử một triple sai rồi chạy lại reasoner OWL 2 RL trên phần graph quanh thực thể.
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

function short(text: string, max = 26): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

/** Nút tròn có nhãn bên dưới; bấm mở trang thực thể. */
function Dot({ n, x, y, r, danger }: { n: Node | SchemaTerm; x: number; y: number; r: number; danger?: boolean }) {
  const label = n.label;
  const fill = "kind" in n ? kindColorVar(n.kind) : "var(--k-other)";
  const body = (
    <g>
      <title>{label}</title>
      <circle cx={x} cy={y} r={r} fill={fill} stroke={danger ? DANGER : "#fff"} strokeWidth={danger ? 4 : 2} />
      <text x={x} y={y + r + 18} textAnchor="middle" className="cg-node">
        {short(label)}
      </text>
    </g>
  );
  return "id" in n && !n.external ? <Link to={`/entity/${encodeURIComponent(n.id)}`}>{body}</Link> : body;
}

const DANGER = "#d92d20";
const OK = "#079455";
const W = 720;
const H = 250;

/** Đồ thị giải thích một vi phạm disjoint: triple thử → máy suy ra lớp mới → hai lớp tách rời. */
function ConflictGraph({ r, c }: { r: ConsistencyResult; c: ConsistencyResult["conflicts"][number] }) {
  const other = c.isSubject ? r.triple.o : r.triple.s;
  const ix = 400, iy = 125, ox = 630; // cá thể vi phạm ở giữa, đầu kia của triple thử bên phải
  const box = { x: 20, w: 250, h: 44, top: 30, bottom: 176 };
  const [from, to] = c.isSubject ? [ix + 28, ox - 24] : [ox - 24, ix + 28];
  return (
    <svg className="cg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Đồ thị giải thích mâu thuẫn">
      <defs>
        {[["gray", "var(--asserted)"], ["inf", "var(--inferred)"], ["bad", DANGER]].map(([id, color]) => (
          <marker key={id} id={`cg-${id}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0,0 L10,5 L0,10 z" fill={color} />
          </marker>
        ))}
      </defs>

      {/* hai lớp tách rời */}
      <rect x={box.x} y={box.top} width={box.w} height={box.h} rx="6" className="cg-class" />
      <text x={box.x + box.w / 2} y={box.top + 27} textAnchor="middle" className="cg-class-text">
        {short(c.known.label, 30)}
      </text>
      <rect x={box.x} y={box.bottom} width={box.w} height={box.h} rx="6" className="cg-class cg-class-inf" />
      <text x={box.x + box.w / 2} y={box.bottom + 27} textAnchor="middle" className="cg-class-text cg-inf">
        {short(c.inferred.label, 30)}
      </text>
      <line x1={box.x + 60} y1={box.top + box.h} x2={box.x + 60} y2={box.bottom} stroke={DANGER} strokeWidth="3" />
      <text x={box.x + 72} y={(box.top + box.h + box.bottom) / 2 + 2} className="cg-bad cg-strong">
        ⊥ tách rời
      </text>
      <text x={box.x + 72} y={(box.top + box.h + box.bottom) / 2 + 18} className="cg-bad cg-small">
        owl:AllDisjointClasses
      </text>

      {/* cá thể → hai lớp */}
      <line x1={ix - 26} y1={iy - 10} x2={box.x + box.w + 4} y2={box.top + box.h / 2} stroke="var(--asserted)" strokeWidth="2" markerEnd="url(#cg-gray)" />
      <text x={ix - 40} y={iy - 48} textAnchor="middle" className="cg-edge">
        đã có trong graph
      </text>
      <line x1={ix - 26} y1={iy + 10} x2={box.x + box.w + 4} y2={box.bottom + box.h / 2} stroke="var(--inferred)" strokeWidth="2" strokeDasharray="6 4" markerEnd="url(#cg-inf)" />
      <text x={box.x + box.w + 14} y={box.bottom + 30} className="cg-edge cg-inf">
        <tspan className="cg-strong">máy suy ra</tspan>
        <tspan x={box.x + box.w + 14} dy="16">
          {c.reason}
        </tspan>
      </text>

      {/* triple thử */}
      <line x1={from} y1={iy} x2={to} y2={iy} stroke={DANGER} strokeWidth="2.5" strokeDasharray="6 4" markerEnd="url(#cg-bad)" />
      <text x={(ix + ox) / 2} y={iy - 12} textAnchor="middle" className="cg-edge cg-bad cg-strong">
        {short(r.triple.p.label, 22)}
      </text>
      <text x={(ix + ox) / 2} y={iy + 22} textAnchor="middle" className="cg-edge cg-bad">
        triple thử
      </text>

      <Dot n={c.individual} x={ix} y={iy} r={26} danger />
      <Dot n={other} x={ox} y={iy} r={22} />
    </svg>
  );
}

/** Không mâu thuẫn: triple thử khớp domain/range của thuộc tính. */
function ConsistentGraph({ r }: { r: ConsistencyResult }) {
  const { domain, range } = r.axioms;
  const sx = 170, ox = 550, y = 70;
  return (
    <svg className="cg cg-ok" viewBox={`0 0 ${W} 150`} role="img" aria-label="Triple thử không mâu thuẫn">
      <defs>
        <marker id="cg-ok" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" fill={OK} />
        </marker>
      </defs>
      <line x1={sx + 26} y1={y} x2={ox - 24} y2={y} stroke={OK} strokeWidth="2.5" strokeDasharray="6 4" markerEnd="url(#cg-ok)" />
      <text x={(sx + ox) / 2} y={y - 12} textAnchor="middle" className="cg-edge cg-good cg-strong">
        {short(r.triple.p.label, 22)}
      </text>
      <text x={(sx + ox) / 2} y={y + 22} textAnchor="middle" className="cg-edge cg-good">
        {[domain && `domain ${domain.label} ✓`, range && `range ${range.label} ✓`].filter(Boolean).join(" · ") || "triple thử"}
      </text>
      <Dot n={r.triple.s} x={sx} y={y} r={26} />
      <Dot n={r.triple.o} x={ox} y={y} r={22} />
    </svg>
  );
}

function Verdict({ r }: { r: ConsistencyResult }) {
  const c = r.conflicts[0];
  return (
    <div className={`cons-result ${r.consistent ? "ok" : "bad"}`}>
      <div className="cons-head">
        <b>{r.consistent ? "✓ Không mâu thuẫn" : "✗ Mâu thuẫn"}</b>
        <span className="muted small">
          reasoner OWL 2 RL · {formatNumber(r.triples)} triple · {formatNumber(r.ms)} ms · graph thật không đổi
        </span>
      </div>
      {c ? <ConflictGraph r={r} c={c} /> : r.consistent && <ConsistentGraph r={r} />}
      {c && (
        <p className="cons-caption">
          <b>{c.individual.label}</b> không thể vừa là <b>{c.known.label}</b> vừa là{" "}
          <b className="inferred-text">{c.inferred.label}</b>.
        </p>
      )}
      {r.consistent && (
        <p className="cons-caption small muted">
          Đúng loại nên không mâu thuẫn, dù có thể sai sự thật: ontology kiểm tra <i>loại</i> của thực thể, không kiểm tra
          sự thật (giả định thế giới mở).
        </p>
      )}
      {r.errors.map((m, i) => (
        <p key={i} className="small">
          <code>{m}</code>
        </p>
      ))}
    </div>
  );
}

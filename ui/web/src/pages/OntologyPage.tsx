import { useEffect, useMemo } from "react";
import { useLocation } from "react-router-dom";
import type { Ontology, OntologyClass, OntologyProperty } from "../api/types";
import { useApi } from "../api/useApi";
import { ErrorState, Loading } from "../components/States";
import { StatTile } from "../components/StatTile";
import { formatNumber } from "../utils/format";

/** "vio:playedFor" → "playedFor" (dùng trong công thức tiên đề cho gọn). */
const local = (id: string) => id.replace(/^vio:/, "");

function Inferred({ n, title = "số triple do bộ suy luận OWL 2 RL thêm vào nhờ định nghĩa này" }: { n: number; title?: string }) {
  if (n <= 0) return null;
  return (
    <span className="onto-badge inf" title={title}>
      +{formatNumber(n)} suy luận
    </span>
  );
}

function TermLink({ id, term, title }: { id: string; term: string; title: string }) {
  // mở định nghĩa Linked Data của team (/ontology/{term}) trong tab mới
  return (
    <a href={`/ontology/${encodeURIComponent(term)}`} target="_blank" rel="noopener noreferrer" title={title}>
      <code>{id}</code>
    </a>
  );
}

function PropertyRow({ p }: { p: OntologyProperty }) {
  return (
    <li className="onto-prop">
      <TermLink id={p.id} term={p.term} title={`${p.label} (${p.labelEn}) — mở định nghĩa trong tab mới`} />
      <span className="onto-arrow">→</span>
      <code className="muted">{p.range ?? "?"}</code>
      <span className="onto-plabel">{p.label}</span>
      {p.subPropertyOf.map((s) => (
        <span key={s} className="onto-badge" title="rdfs:subPropertyOf">
          ⊑ {s}
        </span>
      ))}
      {p.functional && (
        <span className="onto-badge" title="owl:FunctionalProperty: mỗi chủ thể chỉ có một giá trị">
          functional
        </span>
      )}
      {p.inverseOf && (
        <span className="onto-badge" title="owl:inverseOf">
          nghịch đảo của {p.inverseOf}
        </span>
      )}
      <Inferred n={p.inferred} />
    </li>
  );
}

function ClassRow({ c, highlighted }: { c: OntologyClass; highlighted: boolean }) {
  const inferred = c.total - c.asserted;
  return (
    <li id={`cls-${c.term}`} className={`onto-class${highlighted ? " highlight" : ""}`} style={{ marginLeft: c.depth * 18 }}>
      <div className="onto-class-head">
        <strong>{c.label}</strong>
        <TermLink id={c.id} term={c.term} title={`${c.labelEn} — mở định nghĩa lớp trong tab mới`} />
        {c.dbo.length > 0 && <span className="onto-sub">⊑ {c.dbo.join(", ")}</span>}
        <span className="onto-count" title={`${formatNumber(c.asserted)} thực thể khai báo · ${formatNumber(c.total)} sau suy luận`}>
          {formatNumber(c.asserted)} / {inferred > 0 ? <span className="onto-inferred">{formatNumber(c.total)}</span> : formatNumber(c.total)}
        </span>
      </div>
      {c.properties.length > 0 && (
        <ul className="onto-props">
          {c.properties.map((p) => (
            <PropertyRow key={p.id} p={p} />
          ))}
        </ul>
      )}
    </li>
  );
}

/** Ontology vio: cây lớp, thuộc tính theo lớp và các tiên đề tạo ra suy luận (dữ liệu từ /api/ontology). */
export function OntologyPage() {
  const { data, error, loading } = useApi<Ontology>("/api/ontology");
  const { hash } = useLocation();
  const target = hash ? decodeURIComponent(hash.slice(1)) : "";
  const noDomain = useMemo(() => (data?.properties ?? []).filter((p) => !p.domain), [data]);

  // deep link /ontology#Person: cuộn tới và tô sáng dòng lớp
  useEffect(() => {
    if (!data || !target) return;
    document.getElementById(`cls-${target}`)?.scrollIntoView({ block: "center" });
  }, [data, target]);

  if (loading) return <Loading text="Đang tải ontology…" />;
  if (error || !data) {
    const hint = error?.includes("404") ? " Máy chủ này chưa có endpoint /api/ontology." : "";
    return <ErrorState message={`${error ?? "Không có dữ liệu ontology."}${hint}`} />;
  }

  const { stats, classes, axioms } = data;
  const curl = `curl -H "Accept: text/turtle" ${window.location.origin}/ontology/playedFor`;

  return (
    <div className="ontology">
      <h1 className="page-title">
        Ontology <code>vio:</code>
      </h1>
      <p className="muted lead">
        Lớp nào, thuộc tính nào, tiên đề nào tạo ra suy luận? Namespace <code className="mono">{stats.namespace}</code> ·{" "}
        <a href={stats.download} target="_blank" rel="noopener noreferrer">
          Tải vi-ontology.ttl
        </a>
      </p>

      <section className="tiles">
        <StatTile value={formatNumber(stats.classes)} label="lớp" note="owl:Class, cây rdfs:subClassOf" />
        <StatTile value={formatNumber(stats.objectProperties)} label="thuộc tính đối tượng" note="owl:ObjectProperty" />
        <StatTile value={formatNumber(stats.datatypeProperties)} label="thuộc tính dữ liệu" note="owl:DatatypeProperty" />
        <StatTile value={formatNumber(stats.triples)} label="triple" note="trong vi-ontology.ttl" />
      </section>

      <p className="muted small onto-hint">Mỗi thuật ngữ dereference được (303 + content negotiation), ví dụ:</p>
      <pre className="curl">{curl}</pre>

      <div className="onto-cols">
        <section className="card">
          <h2>Cây lớp ({classes.length})</h2>
          <p className="muted small">
            Số bên phải: thực thể khai báo / sau suy luận (phần tím là do <code>rdfs:subClassOf</code> và các ràng buộc). Bấm mã lớp để mở định nghĩa.
          </p>
          <ul className="onto-tree">
            {classes.map((c) => (
              <ClassRow key={c.id} c={c} highlighted={c.term === target} />
            ))}
          </ul>
        </section>

        <section className="card onto-axioms">
          <h2>Tiên đề</h2>
          <p className="muted small">Các định nghĩa OWL khiến bộ suy luận thêm triple; số tím là triple suy ra được từ từng tiên đề.</p>

          <h3>Chuỗi thuộc tính</h3>
          {axioms.chains.length === 0 && <p className="muted small">Không có.</p>}
          <ul>
            {axioms.chains.map((ch) => (
              <li key={ch.property}>
                <span className="onto-formula">
                  {ch.chain.map(local).join(" ∘ ")} ⊑ {local(ch.property)}
                </span>
                <Inferred n={ch.inferred} />
              </li>
            ))}
          </ul>

          <h3>Nghịch đảo</h3>
          {axioms.inverses.length === 0 && <p className="muted small">Không có.</p>}
          <ul>
            {axioms.inverses.map((inv) => (
              <li key={`${inv.a}|${inv.b}`}>
                <span className="onto-formula">
                  {local(inv.a)} ≡ {local(inv.b)}⁻
                </span>
                <Inferred n={inv.inferredA} title={`triple ${inv.a} suy ra từ ${inv.b}`} />
                <Inferred n={inv.inferredB} title={`triple ${inv.b} suy ra từ ${inv.a}`} />
              </li>
            ))}
          </ul>

          <h3>Ràng buộc</h3>
          {axioms.restrictions.length === 0 && <p className="muted small">Không có.</p>}
          <ul>
            {axioms.restrictions.map((r) => (
              <li key={`${r.onClass}|${r.property}|${r.filler}`}>
                <span className="onto-formula" title={`${r.kind} · ${r.onClass} · ${r.property} · ${r.filler}`}>
                  {r.text}
                </span>
                <Inferred n={r.inferred} />
              </li>
            ))}
          </ul>

          <h3>Rời nhau</h3>
          {axioms.disjoint.length === 0 && <p className="muted small">Không có.</p>}
          <ul>
            {axioms.disjoint.map((group) => (
              <li key={group.join("|")} className="onto-disjoint">
                <span className="muted small">owl:AllDisjointClasses</span>
                {group.map((cls) => (
                  <span key={cls} className="chip">
                    {cls}
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </section>
      </div>

      <details className="card onto-nodomain">
        <summary>Thuộc tính không có domain ({noDomain.length})</summary>
        <p className="muted small">Dùng chung cho nhiều lớp nên không gắn rdfs:domain; bộ suy luận không suy ra lớp của chủ thể từ chúng.</p>
        {noDomain.length === 0 ? (
          <p className="muted small">Mọi thuộc tính đều có domain.</p>
        ) : (
          <ul className="onto-props">
            {noDomain.map((p) => (
              <PropertyRow key={p.id} p={p} />
            ))}
          </ul>
        )}
      </details>
    </div>
  );
}

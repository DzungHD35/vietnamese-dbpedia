import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useApi } from "../api/useApi";
import type { Entity, Fact, Neighbors, Value } from "../api/types";
import { CareerTimeline } from "../components/CareerTimeline";
import { EntityLink } from "../components/EntityLink";
import { GraphView } from "../components/GraphView";
import { InferredBadge } from "../components/InferredBadge";
import { LinkedDataCard } from "../components/LinkedDataCard";
import { ErrorState, Loading } from "../components/States";
import { useInference } from "../context/InferenceContext";
import { formatLiteral, formatNumber } from "../utils/format";
import { kindColorVar } from "../utils/kinds";

type TabId = "facts" | "incoming" | "classes" | "query";
const TABS: { id: TabId; label: string }[] = [
  { id: "facts", label: "Thuộc tính" },
  { id: "incoming", label: "Được tham chiếu bởi" },
  { id: "classes", label: "Cây phân lớp" },
  { id: "query", label: "Truy vấn" },
];
const NS_TITLES: Record<Fact["ns"], string> = {
  vio: "Ontology vio: (khai báo của dự án)",
  dbo: "Ontology dbo: (tương đương DBpedia, phần lớn do suy luận)",
  other: "Chung (rdf, rdfs, owl, foaf, dct, prov…)",
  vip: "Thuộc tính thô từ infobox (vip:)",
};
const KEY_FACTS = 8;

export function EntityPage() {
  const { id } = useParams();
  return <EntityView key={id} id={id ?? ""} />;
}

function ValueView({ v, raw = false }: { v: Value; raw?: boolean }) {
  if (v.type === "iri") {
    return (
      <>
        <EntityLink node={v.node} />
        {v.inferred && <InferredBadge />}
      </>
    );
  }
  return (
    <>
      {raw ? v.value : formatLiteral(v.value, v.datatype)}
      {(v.lang || v.datatype) && <span className="dt">{v.lang ? `@${v.lang}` : v.datatype}</span>}
      {v.inferred && <InferredBadge />}
    </>
  );
}

function EntityView({ id }: { id: string }) {
  const navigate = useNavigate();
  const { showInferred } = useInference();
  const enc = encodeURIComponent(id);
  const entity = useApi<Entity>(`/api/entity/${enc}`);
  const neighbors = useApi<Neighbors>(`/api/neighbors/${enc}`);
  const [tab, setTab] = useState<TabId>("facts");
  const [fullAbstract, setFullAbstract] = useState(false);

  if (entity.loading) return <Loading text="Đang tải thực thể…" />;
  if (entity.error || !entity.data) return <ErrorState message={entity.error ?? "Không có dữ liệu."} />;
  const e = entity.data;
  const { node, lod } = e;
  const ttl = `${lod.linkedData.replace("/resource/", "/data/")}.ttl`;
  const key = e.facts
    .filter((f) => f.ns === "vio" && f.values.length <= 3 && f.values.every((v) => !v.inferred))
    .slice(0, KEY_FACTS);

  return (
    <div className="entity">
      <header className="ent-head">
        {e.thumbnail && (
          <img className="ent-thumb" src={e.thumbnail} alt="" referrerPolicy="no-referrer" onError={(ev) => (ev.currentTarget.style.display = "none")} />
        )}
        <div className="ent-main">
          <div className="ent-title">
            <h1>{node.label}</h1>
            {node.cls && (
              <span className="chip chip-kind" style={{ background: kindColorVar(node.kind) }}>
                {node.cls}
              </span>
            )}
          </div>
          <div className="chips">
            {lod.wikipedia && <ExtChip href={lod.wikipedia} text="Wikipedia" />}
            {lod.dbpedia.map((u) => (
              <ExtChip key={u} href={u} text="DBpedia EN" />
            ))}
            {lod.wikidata.map((u) => (
              <ExtChip key={u} href={u} text={`Wikidata ${u.split("/").pop()}`} />
            ))}
            <ExtChip href={ttl} text="Linked Data (Turtle)" />
            {lod.lat !== null && lod.lon !== null && (
              <ExtChip href={`https://www.openstreetmap.org/?mlat=${lod.lat}&mlon=${lod.lon}#map=12/${lod.lat}/${lod.lon}`} text="Bản đồ" />
            )}
          </div>
          {e.abstract && (
            <p className={`ent-abstract${fullAbstract ? "" : " clamp"}`} onClick={() => setFullAbstract((x) => !x)} title="Bấm để thu/phóng">
              {e.abstract}
            </p>
          )}
          <p className="ent-counts">
            {formatNumber(e.counts.asserted)} triple khai báo
            {showInferred && (
              <>
                {" · "}
                <b>{formatNumber(e.counts.inferred)} triple suy luận</b>
              </>
            )}
          </p>
        </div>
      </header>

      <div className="ent-cols">
        {e.career.length > 0 ? (
          <section className="card">
            <h2>Sự nghiệp</h2>
            <CareerTimeline career={e.career} />
          </section>
        ) : (
          <section className="card">
            <h2>Thông tin chính</h2>
            {key.length === 0 ? (
              <p className="muted">Chưa có thuộc tính vio: nổi bật.</p>
            ) : (
              <dl className="keyfacts">
                {key.map((f) => (
                  <div key={f.prop} style={{ display: "contents" }}>
                    <dt>{f.label}</dt>
                    <dd>
                      {f.values.map((v, i) => (
                        <span key={i}>
                          {i > 0 && ", "}
                          <ValueView v={v} />
                        </span>
                      ))}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </section>
        )}
        {neighbors.loading ? (
          <section className="card">
            <Loading text="Đang dựng đồ thị…" />
          </section>
        ) : neighbors.error || !neighbors.data ? (
          <section className="card">
            <ErrorState message={neighbors.error ?? "Không có dữ liệu."} />
          </section>
        ) : (
          <GraphView
            title="Đồ thị lân cận"
            data={neighbors.data}
            centerId={node.id}
            expandable
            showInferred={showInferred}
            onOpen={(nid) => navigate(`/entity/${encodeURIComponent(nid)}`)}
          />
        )}
      </div>

      <LinkedDataCard id={id} iri={node.iri} lod={lod} />

      <div className="tabs">
        <div className="tab-list" role="tablist">
          {TABS.map((t) => (
            <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
        <div className="tab-body">
          {tab === "facts" && <FactsTab facts={e.facts} showInferred={showInferred} />}
          {tab === "incoming" && <IncomingTab entity={e} showInferred={showInferred} />}
          {tab === "classes" && <ClassesTab entity={e} showInferred={showInferred} />}
          {tab === "query" && <QueryTab iri={node.iri} />}
        </div>
      </div>
    </div>
  );
}

function ExtChip({ href, text }: { href: string; text: string }) {
  return (
    <a className="chip" href={href} target="_blank" rel="noopener noreferrer">
      {text} ↗
    </a>
  );
}

function FactsTab({ facts, showInferred }: { facts: Fact[]; showInferred: boolean }) {
  const groups = (["vio", "dbo", "other", "vip"] as const)
    .map((ns) => ({
      ns,
      rows: facts
        .filter((f) => f.ns === ns)
        .map((f) => ({ ...f, values: f.values.filter((v) => showInferred || !v.inferred) }))
        .filter((f) => f.values.length > 0),
    }))
    .filter((g) => g.rows.length > 0);

  return (
    <>
      {groups.map((g) => (
        <section key={g.ns} className="facts-group">
          <h3>{NS_TITLES[g.ns]}</h3>
          <table className="facts">
            <tbody>
              {g.rows.map((f) => (
                <tr key={f.prop}>
                  <th>
                    <code>{f.prop}</code>
                    {f.label !== f.prop && <div className="small">{f.label}</div>}
                  </th>
                  <td>
                    <ul>
                      {f.values.map((v, i) => (
                        <li key={i}>
                          <ValueView v={v} raw />
                        </li>
                      ))}
                    </ul>
                    {f.more > 0 && showInferred && <span className="more">… và {formatNumber(f.more)} giá trị khác</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </>
  );
}

function IncomingTab({ entity, showInferred }: { entity: Entity; showInferred: boolean }) {
  const groups = entity.incoming
    .map((g) => ({ ...g, items: g.items.filter((i) => showInferred || !i.inferred) }))
    .filter((g) => g.items.length > 0);
  if (groups.length === 0) return <p className="muted">Không có tài nguyên nào trỏ tới thực thể này.</p>;
  return (
    <table className="facts">
      <tbody>
        {groups.map((g) => (
          <tr key={g.prop}>
            <th>
              là <code>{g.prop}</code> của
              <div className="small">{g.label !== g.prop ? g.label : ""} ({formatNumber(g.count)})</div>
            </th>
            <td>
              <ul>
                {g.items.map((i) => (
                  <li key={i.id}>
                    <EntityLink node={i} />
                    {i.inferred && <InferredBadge />}
                  </li>
                ))}
              </ul>
              {g.count > g.items.length && showInferred && <span className="more">… và {formatNumber(g.count - g.items.length)} tài nguyên khác</span>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ClassesTab({ entity, showInferred }: { entity: Entity; showInferred: boolean }) {
  const visible = entity.classes.filter((c) => showInferred || !c.inferred);
  const depth = new Map<string, number>();
  // danh sách đã theo thứ tự cha trước con; độ sâu chỉ đếm các lớp đang hiện
  const resolveDepth = (parent: string | null): number => {
    let p = parent;
    while (p) {
      const d = depth.get(p);
      if (d !== undefined) return d + 1;
      p = entity.classes.find((c) => c.id === p)?.parent ?? null;
    }
    return 0;
  };
  visible.forEach((c) => depth.set(c.id, resolveDepth(c.parent)));
  if (visible.length === 0) return <p className="muted">Không có lớp vio:/dbo: khai báo.</p>;
  return (
    <ul className="class-tree">
      {visible.map((c) => (
        <li key={c.id} style={{ paddingLeft: (depth.get(c.id) ?? 0) * 20 }}>
          <code>{c.id}</code> <span className="muted">{c.label !== c.id ? c.label : ""}</span>
          {c.inferred ? <InferredBadge /> : <span className="chip" style={{ marginLeft: 6 }}>khai báo</span>}
          {c.also.length > 0 && <span className="also">⊑ {c.also.join(", ")}</span>}
        </li>
      ))}
    </ul>
  );
}

function QueryTab({ iri }: { iri: string }) {
  const select = `SELECT ?p ?o WHERE { <${iri}> ?p ?o }`;
  const describe = `DESCRIBE <${iri}>`;
  return (
    <div className="query-links">
      <Link className="btn" to={`/sparql?query=${encodeURIComponent(select)}`}>
        Mở SELECT ?p ?o trong SPARQL
      </Link>
      <Link className="btn" to={`/sparql?query=${encodeURIComponent(describe)}`}>
        Mở DESCRIBE trong SPARQL
      </Link>
      <pre>{select}</pre>
    </div>
  );
}

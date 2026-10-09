import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useApi, type ApiState } from "../api/useApi";
import type { Entity, EntityClass, Fact, Node, RelationGroup, RelationNode, RelationTree, Value } from "../api/types";
import { CareerTimeline } from "../components/CareerTimeline";
import { EntityLink } from "../components/EntityLink";
import { InferredBadge } from "../components/InferredBadge";
import { IriTip } from "../components/IriTip";
import { LinkedDataCard } from "../components/LinkedDataCard";
import { DraggableGraph } from "../components/DraggableGraph";
import { ErrorState, Loading } from "../components/States";
import { Chevron, LeafMark, rowToggle } from "../components/TreeChevron";
import { useInference } from "../context/InferenceContext";
import { formatLiteral, formatNumber, shortIri } from "../utils/format";

type TabId = "facts" | "incoming" | "tree" | "query";
const TABS: { id: TabId; label: string }[] = [
  { id: "facts", label: "Thuộc tính" },
  { id: "incoming", label: "Được tham chiếu bởi" },
  { id: "tree", label: "Cây quan hệ" },
  { id: "query", label: "Truy vấn" },
];
const VIO_NS = "http://vi.dbpedia.org/ontology/";
const VIP_NS = "http://vi.dbpedia.org/property/";
const DBO_NS = "http://dbpedia.org/ontology/";
const CLASS_NS: Record<string, string> = { vio: VIO_NS, dbo: DBO_NS }; // lớp trong cây phân lớp chỉ có vio:/dbo:
const RDF_TYPE = "rdf:type";
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
  const { showInferred } = useInference();
  const enc = encodeURIComponent(id);
  const entity = useApi<Entity>(`/api/entity/${enc}`);
  const [tab, setTab] = useState<TabId>("facts");
  const [treeOpened, setTreeOpened] = useState(false); // cây quan hệ chỉ nạp khi mở tab lần đầu, rồi giữ lại
  const tree = useApi<RelationTree>(treeOpened ? `/api/entity/${enc}/tree` : null);
  const [fullAbstract, setFullAbstract] = useState(false);

  if (entity.loading) return <Loading text="Đang tải thực thể…" />;
  if (entity.error || !entity.data) return <ErrorState message={entity.error ?? "Không có dữ liệu."} />;
  const e = entity.data;
  const { node, lod } = e;
  const ttl = `${lod.linkedData.replace("/resource/", "/data/")}.ttl`;
  const hasCareer = e.career.length > 0;
  const key = e.facts
    .filter((f) => f.ns === "vio" && f.values.length <= 3 && f.values.every((v) => !v.inferred))
    .slice(0, KEY_FACTS);

  return (
    <div className="entity">
      <header className="ent-head">
        {e.thumbnail && (
          <figure className="ent-thumbfig" title={e.thumbnail}>
            <img
              className="ent-thumb"
              src={e.thumbnail}
              alt={node.label}
              referrerPolicy="no-referrer"
              onError={(ev) => ((ev.currentTarget.parentElement as HTMLElement).style.display = "none")}
            />
            <figcaption>dbo:thumbnail</figcaption>
          </figure>
        )}
        <div className="ent-main">
          <div className="ent-title">
            <h1>{node.label}</h1>
          </div>
          <p className="ent-type">
            Thực thể thuộc lớp{" "}
            {e.types.length === 0
              ? "—"
              : e.types.map((t, i) => (
                  <span key={t.id}>
                    {i > 0 && ", "}
                    <IriTip iri={t.iri}>
                      <Link to={`/ontology#${encodeURIComponent(t.term)}`} title={t.iri}>
                        {t.label}
                      </Link>
                    </IriTip>
                  </span>
                ))}
            {" · đồ thị "}
            <code>{e.graph}</code>
          </p>
          <p className="ent-iri">
            <code>{node.iri}</code>
          </p>
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

      <div className="ent-cols ent-onto">
        <section className="card ent-classes">
          <h2>Cây phân lớp</h2>
          <p className="muted small ent-note">Lớp khai báo và các lớp DBpedia suy ra bằng OWL 2 RL (rdfs:subClassOf).</p>
          <ClassTree classes={e.classes} showInferred={showInferred} />
        </section>
        <LinkedDataCard id={id} iri={node.iri} lod={lod} />
      </div>


      {/* trái: thông tin chính + sự nghiệp; phải: đồ thị lân cận (hình tĩnh như Gradio) */}
      <div className="ent-cols ent-main-row">
        <div className="ent-stack">
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
          {hasCareer && (
            <section className="card">
              <h2>Sự nghiệp</h2>
              <CareerTimeline career={e.career} />
            </section>
          )}
        </div>
        <section className="card ent-graph">
          <h2>Đồ thị lân cận</h2>
          <p className="muted small ent-note">
            Mũi tên trỏ theo hướng của triple, tên quan hệ ghi giữa mũi tên; nét đứt là quan hệ có được nhờ suy luận.
            Nút viền đứt là liên kết LOD ra ngoài.
          </p>
          <DraggableGraph id={id} showInferred={showInferred} />
        </section>
      </div>

      <div className="tabs">
        <div className="tab-list" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={tab === t.id}
              className={tab === t.id ? "active" : ""}
              onClick={() => {
                setTab(t.id);
                if (t.id === "tree") setTreeOpened(true);
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="tab-body">
          {tab === "facts" && <FactsTab facts={e.facts} showInferred={showInferred} />}
          {tab === "incoming" && <IncomingTab entity={e} showInferred={showInferred} />}
          {tab === "tree" && <TreeTab tree={tree} />}
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

/**
 * qname của thuộc tính / lớp thành link, như `self.link(p, self.qname(p))` của trang Gradio: vio: mở định nghĩa trên trang
 * Ontology (#term), vip: chưa có trang riêng nên chỉ có bong bóng IRI, IRI khác (dbo:, rdfs:, owl:…) mở tab mới.
 */
function TermRef({ iri, qname }: { iri: string; qname: string }) {
  if (!iri) return <code>{qname}</code>; // máy chủ cũ chưa trả IRI
  if (iri.startsWith(VIO_NS)) {
    return (
      <IriTip iri={iri}>
        <Link className="term-ref" to={`/ontology#${encodeURIComponent(iri.slice(VIO_NS.length))}`} title={iri}>
          <code>{qname}</code>
        </Link>
      </IriTip>
    );
  }
  if (iri.startsWith(VIP_NS)) {
    return (
      <IriTip iri={iri}>
        <code className="term-ref" title={iri}>
          {qname}
        </code>
      </IriTip>
    );
  }
  return (
    <IriTip iri={iri}>
      <a className="term-ref" href={iri} target="_blank" rel="noopener noreferrer" title={iri}>
        <code>{qname}</code> ↗
      </a>
    </IriTip>
  );
}

/** "vio:Club" → IRI đầy đủ; tiền tố khác trả "" (TermRef hiện mã không link). */
function classIri(qname: string): string {
  const i = qname.indexOf(":");
  const ns = CLASS_NS[qname.slice(0, i)];
  return ns ? ns + qname.slice(i + 1) : "";
}

const nodeQname = (n: Node) => n.qname ?? shortIri(n.iri);
const nsRank = (iri: string) => (iri.startsWith(VIO_NS) ? 0 : iri.startsWith(DBO_NS) ? 1 : 2);

/** Giá trị rdf:type: khai báo trước suy luận, vio: trước dbo: trước lớp khác, rồi theo qname. */
function sortTypes(values: Value[]): Value[] {
  const rank = (v: Value) => (v.type === "iri" ? nsRank(v.node.iri) : 3);
  const name = (v: Value) => (v.type === "iri" ? nodeQname(v.node) : v.value);
  return [...values].sort((a, b) => Number(a.inferred) - Number(b.inferred) || rank(a) - rank(b) || name(a).localeCompare(name(b)));
}

function ClassValue({ node, inferred }: { node: Node; inferred: boolean }) {
  const qname = nodeQname(node);
  return (
    <>
      <TermRef iri={node.iri} qname={qname} />
      {node.label !== qname && <span className="muted"> {node.label}</span>}
      {inferred && <InferredBadge />}
    </>
  );
}

function FactRow({ f, showInferred }: { f: Fact; showInferred: boolean }) {
  const isType = f.prop === RDF_TYPE;
  const values = isType ? sortTypes(f.values) : f.values;
  return (
    <tr>
      <th>
        <TermRef iri={f.iri} qname={f.prop} />
        {f.label !== f.prop && <div className="small">{f.label}</div>}
      </th>
      <td>
        <ul>
          {values.map((v, i) => (
            <li key={i}>{isType && v.type === "iri" ? <ClassValue node={v.node} inferred={v.inferred} /> : <ValueView v={v} raw />}</li>
          ))}
        </ul>
        {f.more > 0 && showInferred && <span className="more">… và {formatNumber(f.more)} giá trị khác</span>}
      </td>
    </tr>
  );
}

function FactsTab({ facts, showInferred }: { facts: Fact[]; showInferred: boolean }) {
  const visible = facts
    .map((f) => ({ ...f, values: f.values.filter((v) => showInferred || !v.inferred) }))
    .filter((f) => f.values.length > 0);
  // rdf:type tách khỏi nhóm "Chung" thành nhóm đầu tiên; các thuộc tính khác (rdfs:label, dbo:abstract…) giữ chỗ cũ
  const type = visible.find((f) => f.prop === RDF_TYPE);
  const groups = [
    ...(type ? [{ key: "type", title: "Lớp của thực thể (rdf:type)", rows: [type] }] : []),
    ...(["vio", "dbo", "other", "vip"] as const).map((ns) => ({
      key: ns,
      title: NS_TITLES[ns],
      rows: visible.filter((f) => f.ns === ns && f !== type),
    })),
  ].filter((g) => g.rows.length > 0);

  return (
    <>
      {groups.map((g) => (
        <section key={g.key} className="facts-group">
          <h3>{g.title}</h3>
          <table className="facts">
            <tbody>
              {g.rows.map((f) => (
                <FactRow key={f.prop} f={f} showInferred={showInferred} />
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
            {/* như _reverse_table của Gradio: "là vio:playedFor của · có cầu thủ (39)" */}
            <th>
              là <TermRef iri={g.iri} qname={g.prop} /> của{" "}
              <span className="small">
                · {g.label !== g.prop && `${g.label} `}({formatNumber(g.count)})
              </span>
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

// ---- Cây quan hệ (giống mục "Cây quan hệ" ở tab Tài nguyên của Gradio; dữ liệu /api/entity/{id}/tree) ----

function TreeTab({ tree }: { tree: ApiState<RelationTree> }) {
  return (
    <>
      <p className="muted small rt-hint">Chỉ gồm quan hệ khai báo (trừ vio:playedFor), tối đa 3 bước: gốc → đội → sân → tỉnh.</p>
      {tree.loading && <Loading text="Đang dựng cây quan hệ…" />}
      {tree.error && <ErrorState message={`${tree.error}${tree.error.includes("404") ? " Máy chủ này chưa có endpoint /api/entity/{id}/tree." : ""}`} />}
      {tree.data &&
        (tree.data.groups.length === 0 ? (
          <p className="muted">Không có quan hệ tới thực thể khác.</p>
        ) : (
          <div className="rt">
            <p className="rt-root">
              <b>{tree.data.root.label}</b>
            </p>
            <RelationGroups groups={tree.data.groups} depth={1} />
          </div>
        ))}
    </>
  );
}

function RelationGroups({ groups, depth }: { groups: RelationGroup[]; depth: number }) {
  return (
    <ul className="ct-tree" role={depth === 1 ? "tree" : "group"} aria-label={depth === 1 ? "Cây quan hệ" : undefined}>
      {groups.map((g) => {
        const out = g.direction === "out";
        return (
          <li key={`${g.direction}:${g.prop}`} className="ct-node rt-group">
            <div className="ct-row">
              <span className="rt-arrow" aria-label={out ? "quan hệ đi ra" : "quan hệ đi vào"}>
                {out ? "→" : "←"}
              </span>
              <span className="ct-text">
                <code>{g.prop}</code>{" "}
                <span className="ct-muted">
                  {g.label}
                  {out ? "" : " của"} ({formatNumber(g.total)})
                </span>
              </span>
            </div>
            <div className="ct-children">
              <ul className="ct-tree" role="group">
                {g.children.map((c, i) => (
                  <RelationChild key={`${c.node.id}#${c.station ?? i}`} c={c} depth={depth} />
                ))}
                {g.more > 0 && <li className="rt-more">… và {formatNumber(g.more)} khác</li>}
              </ul>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function RelationChild({ c, depth }: { c: RelationNode; depth: number }) {
  // con trực tiếp của gốc mở sẵn, sâu hơn thu lại (như <details> của Gradio)
  const [open, setOpen] = useState(depth === 1);
  const expandable = c.groups.length > 0;
  const onToggle = () => setOpen((o) => !o);
  return (
    <li className="ct-node" role="treeitem" aria-expanded={expandable ? open : undefined}>
      <div className={`ct-row${expandable ? " ct-clickable" : ""}`} onClick={expandable ? rowToggle(onToggle) : undefined}>
        {expandable ? <Chevron open={open} onToggle={onToggle} /> : <LeafMark />}
        <span className="ct-text">
          <EntityLink node={c.node} />
          {c.node.cls && <span className="chip rt-cls">{c.node.cls}</span>}
          {c.note && <span className="ct-muted rt-note">{c.note}</span>}
        </span>
      </div>
      {expandable && open && (
        <div className="ct-children">
          <RelationGroups groups={c.groups} depth={depth + 1} />
        </div>
      )}
    </li>
  );
}

// ---- Cây phân lớp (giống _class_tree của trang tài nguyên Gradio; dữ liệu entity.classes) ----

function ClassTree({ classes, showInferred }: { classes: EntityClass[]; showInferred: boolean }) {
  const visible = classes.filter((c) => showInferred || !c.inferred);
  if (visible.length === 0) return <p className="muted">Không có lớp vio:/dbo: khai báo.</p>;
  const shown = new Set(visible.map((c) => c.id));
  const byId = new Map(classes.map((c) => [c.id, c]));
  // danh sách đã theo thứ tự cha trước con; lớp cha đang ẩn (tắt suy luận) thì treo vào tổ tiên gần nhất đang hiện
  const kids = new Map<string | null, EntityClass[]>();
  for (const c of visible) {
    let p = c.parent;
    for (let hop = 0; p !== null && !shown.has(p) && hop < classes.length; hop++) p = byId.get(p)?.parent ?? null;
    const key = p !== null && shown.has(p) ? p : null;
    kids.set(key, [...(kids.get(key) ?? []), c]);
  }
  return <ClassBranch items={kids.get(null) ?? []} kids={kids} root />;
}

function ClassBranch({ items, kids, root = false }: { items: EntityClass[]; kids: Map<string | null, EntityClass[]>; root?: boolean }) {
  return (
    <ul className={root ? "class-tree" : undefined}>
      {items.map((c) => {
        const sub = kids.get(c.id);
        return (
          <li key={c.id}>
            <TermRef iri={classIri(c.id)} qname={c.id} />
            {c.label !== c.id && <span className="muted"> {c.label}</span>}
            {c.inferred ? <InferredBadge /> : <span className="badge-asserted">khai báo</span>}
            {c.also.length > 0 && (
              <span className="also">
                ⊑{" "}
                {c.also.map((a, i) => (
                  <span key={a}>
                    {i > 0 && ", "}
                    <TermRef iri={classIri(a)} qname={a} />
                  </span>
                ))}
              </span>
            )}
            {sub && <ClassBranch items={sub} kids={kids} />}
          </li>
        );
      })}
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

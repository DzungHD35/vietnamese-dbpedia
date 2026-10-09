import { useRef, useState, type RefObject } from "react";
import type { Lod } from "../api/types";
import { copyText } from "../utils/clipboard";
import { shortIri } from "../utils/format";

const DBR = "http://dbpedia.org/resource/";
const WD = "http://www.wikidata.org/entity/";
const FORMATS = [
  { label: "Turtle", ext: "ttl" },
  { label: "N-Triples", ext: "nt" },
  { label: "JSON-LD", ext: "jsonld" },
  { label: "RDF/XML", ext: "rdf" },
];

/** IRI DBpedia/Wikidata → tên có tiền tố (dbr:X, wd:Q123); IRI khác rút gọn. */
function prefixed(iri: string): string {
  if (iri.startsWith(DBR)) {
    let local = iri.slice(DBR.length);
    try {
      local = decodeURIComponent(local);
    } catch {
      /* giữ nguyên nếu % không hợp lệ */
    }
    return `dbr:${local}`;
  }
  if (iri.startsWith(WD)) return `wd:${iri.slice(WD.length)}`;
  return shortIri(iri);
}

/** URL bản sửa đổi Wikipedia → số oldid (…?oldid=123 hoặc …/123); không có thì trả cả URL. */
function revisionId(url: string): string {
  const m = /[?&]oldid=(\d+)/.exec(url) ?? /\/(\d+)\/?$/.exec(url);
  return m ? m[1] : url;
}

function CopyButton({ text, target }: { text: string; target: RefObject<HTMLElement> }) {
  const [state, setState] = useState<"idle" | "done" | "selected">("idle");
  const copy = async () => {
    const ok = await copyText(text, target.current);
    setState(ok ? "done" : "selected");
    window.setTimeout(() => setState("idle"), 1800);
  };
  return (
    <button type="button" className="btn" onClick={copy}>
      {state === "done" ? "Đã sao chép" : state === "selected" ? "Đã chọn, nhấn Ctrl+C" : "Sao chép"}
    </button>
  );
}

function Ext({ href, text }: { href: string; text: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" title={href}>
      {text} ↗
    </a>
  );
}

/** Khối "Liên kết dữ liệu mở": IRI, sameAs, nguồn gốc, các dạng RDF tải được và lệnh dereference. */
export function LinkedDataCard({ id, iri, lod }: { id: string; iri: string; lod: Lod }) {
  const enc = encodeURIComponent(id);
  const curl = `curl -L -H "Accept: text/turtle" ${window.location.origin}/resource/${enc}`;
  const iriRef = useRef<HTMLElement>(null);
  const curlRef = useRef<HTMLPreElement>(null);
  const sameAs = [...lod.dbpedia, ...lod.wikidata];

  return (
    <section className="card lod-card">
      <h2>Liên kết dữ liệu mở</h2>
      <dl className="lod">
        <dt>IRI</dt>
        <dd className="lod-iri">
          <code ref={iriRef}>{iri}</code>
          <CopyButton text={iri} target={iriRef} />
        </dd>

        <dt>
          <code>owl:sameAs</code>
        </dt>
        <dd>
          {sameAs.length === 0 ? (
            <span className="muted">chưa nối với DBpedia / Wikidata</span>
          ) : (
            sameAs.map((u, i) => (
              <span key={u}>
                {i > 0 && " · "}
                <Ext href={u} text={prefixed(u)} />
              </span>
            ))
          )}
        </dd>

        <dt>
          <code>foaf:isPrimaryTopicOf</code>
        </dt>
        <dd>{lod.wikipedia ? <Ext href={lod.wikipedia} text={shortIri(lod.wikipedia)} /> : <span className="muted">—</span>}</dd>

        <dt>
          <code>prov:wasDerivedFrom</code>
        </dt>
        <dd>
          {lod.derivedFrom ? (
            <Ext href={lod.derivedFrom} text={`bản sửa đổi ${revisionId(lod.derivedFrom)}`} />
          ) : (
            <span className="muted">—</span>
          )}
        </dd>

        <dt>Tải RDF:</dt>
        <dd>
          {FORMATS.map((f, i) => (
            <span key={f.ext}>
              {i > 0 && " · "}
              <a href={`/data/${enc}.${f.ext}`} target="_blank" rel="noopener noreferrer">
                {f.label}
              </a>
            </span>
          ))}
        </dd>
      </dl>
      <p className="small muted lod-deref">URI dereference được (303 + content negotiation):</p>
      <div className="lod-curl">
        <pre className="curl" ref={curlRef}>
          {curl}
        </pre>
        <CopyButton text={curl} target={curlRef} />
      </div>
    </section>
  );
}

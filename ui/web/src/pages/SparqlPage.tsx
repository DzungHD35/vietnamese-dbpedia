import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { postJson } from "../api/client";
import type { SparqlExample, SparqlResult } from "../api/types";
import { useApi } from "../api/useApi";
import { ResultTable } from "../components/ResultTable";
import { Empty, ErrorState, Loading } from "../components/States";
import { formatNumber } from "../utils/format";

const DEFAULT_QUERY = "SELECT ?p ?o WHERE {\n  vres:Đặng_Quang_Huy ?p ?o .\n} LIMIT 20";
const DOWNLOADS = [
  { label: "JSON", accept: "application/sparql-results+json", ext: "json" },
  { label: "CSV", accept: "text/csv", ext: "csv" },
];

/** Gọi endpoint chuẩn /sparql với Accept tương ứng rồi lưu thành file. */
async function download(query: string, inference: boolean, accept: string, ext: string) {
  const res = await fetch(`/sparql?inference=${inference}`, {
    method: "POST",
    headers: { Accept: accept, "Content-Type": "application/sparql-query" },
    body: query,
  });
  if (!res.ok) throw new Error(await res.text());
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `ket-qua-sparql.${ext}`;
  a.click();
  URL.revokeObjectURL(url);
}

/** SPARQL: ô soạn truy vấn + bảng kết quả; endpoint chuẩn nằm ở /sparql. */
export function SparqlPage() {
  const [params, setParams] = useSearchParams();
  const urlQuery = params.get("query");
  const [text, setText] = useState(urlQuery ?? DEFAULT_QUERY);
  const [inference, setInference] = useState(true);
  const [result, setResult] = useState<{ data: SparqlResult | null; error: string | null; loading: boolean }>({
    data: null,
    error: null,
    loading: false,
  });
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const examples = useApi<SparqlExample[]>("/api/sparql/examples");
  const controller = useRef<AbortController | null>(null);

  const run = useCallback((query: string, withInference: boolean) => {
    controller.current?.abort();
    const ctl = new AbortController();
    controller.current = ctl;
    setResult({ data: null, error: null, loading: true });
    setDownloadError(null);
    postJson<SparqlResult>("/api/sparql", { query, inference: withInference }, ctl.signal)
      .then((data) => setResult({ data, error: null, loading: false }))
      .catch((e: unknown) => {
        if (!ctl.signal.aborted) setResult({ data: null, error: e instanceof Error ? e.message : String(e), loading: false });
      });
  }, []);

  // mở từ link có ?query= (trang Thực thể, khối SPARQL của Hỏi đáp) thì chạy luôn
  useEffect(() => {
    if (urlQuery) {
      setText(urlQuery);
      run(urlQuery, true);
      setInference(true);
    }
    return () => controller.current?.abort();
  }, [urlQuery, run]);

  const data = result.data;
  const endpoint = `${window.location.origin}/sparql`;
  const curl = `curl -G ${endpoint} -H 'Accept: application/sparql-results+json' --data-urlencode 'query=ASK { ?s ?p ?o }'`;
  return (
    <div className="sparql-page">
      <h1 className="page-title">SPARQL</h1>
      <p className="muted lead">
        Endpoint chuẩn SPARQL 1.1 Protocol: <code className="mono">{endpoint}</code> (JSON, XML, CSV theo header{" "}
        <code>Accept</code>; CONSTRUCT trả Turtle). Gọi từ dòng lệnh:
      </p>
      <pre className="curl">{curl}</pre>
      <div className="card">
        <div className="sparql-bar">
          <select
            aria-label="Truy vấn mẫu"
            value=""
            onChange={(e) => {
              const ex = examples.data?.find((x) => x.name === e.target.value);
              if (ex) {
                setText(ex.query);
                setParams({}, { replace: true });
              }
            }}
          >
            <option value="">Chọn truy vấn mẫu…</option>
            {(examples.data ?? []).map((x) => (
              <option key={x.name} value={x.name}>
                {x.name}
              </option>
            ))}
          </select>
          <label className="toggle" title="Tắt để chạy chỉ trên triple khai báo (không có triple do suy luận thêm)">
            <input type="checkbox" checked={inference} onChange={(e) => setInference(e.target.checked)} />
            <span className="toggle-track" />
            Có suy luận
          </label>
          <span className="nav-spacer" />
          <button type="button" className="btn btn-primary" disabled={result.loading} onClick={() => run(text, inference)}>
            Chạy (Ctrl+Enter)
          </button>
        </div>
        <textarea
          className="sparql-input"
          value={text}
          spellCheck={false}
          aria-label="Truy vấn SPARQL"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              run(text, inference);
            }
          }}
        />
        <p className="muted small">Các prefix vio:, vres:, dbo:, rdfs:, owl:… đã khai báo sẵn. Truy vấn nặng không có LIMIT có thể chạy lâu.</p>
      </div>

      {result.loading && <Loading text="Đang chạy truy vấn…" />}
      {result.error && <ErrorState message={result.error} />}
      {data?.error && <ErrorState message={data.error} />}
      {data && !data.error && (
        <section className="card">
          <div className="result-bar">
            <strong>
              {data.type} · {formatNumber(data.total)} dòng · {formatNumber(data.ms)} ms
            </strong>
            <span className="muted small">{inference ? "có suy luận" : "chỉ khai báo"}</span>
            <span className="nav-spacer" />
            {DOWNLOADS.map((d) => (
              <button
                key={d.ext}
                type="button"
                className="btn"
                onClick={() => download(text, inference, d.accept, d.ext).catch((e: unknown) => setDownloadError(e instanceof Error ? e.message : String(e)))}
              >
                Tải {d.label}
              </button>
            ))}
          </div>
          {downloadError && <ErrorState message={downloadError} />}
          {data.rows.length === 0 ? (
            <Empty text="Truy vấn chạy được nhưng không có dòng nào." />
          ) : (
            <ResultTable columns={data.columns} rows={data.rows} links={data.links} total={data.total} />
          )}
        </section>
      )}
    </div>
  );
}

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, postJson } from "../api/client";
import type { AnswerResult, AskResult, AssertedInfo, GraphData, Health, Overview } from "../api/types";
import { useApi } from "../api/useApi";
import { GraphView } from "../components/GraphView";
import { InferenceContrast } from "../components/InferenceContrast";
import { ResultTable } from "../components/ResultTable";
import { SparqlBlock } from "../components/SparqlBlock";
import { Empty, ErrorState, Loading } from "../components/States";
import { useInference } from "../context/InferenceContext";

const HISTORY_SIZE = 5;
const POLL_MS = 3000;
const POLL_MAX = 40;

type Remote<T> = { data: T | null; error: string | null; loading: boolean };

function Step({ n, title, hint, children }: { n: number; title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="card step">
      <h2>
        <span className="step-n">{n}</span>
        {title}
        {hint && <span className="step-hint">{hint}</span>}
      </h2>
      {children}
    </section>
  );
}

function AnswerBlock({ state }: { state: Remote<AnswerResult> }) {
  if (state.loading) {
    return (
      <div className="skeleton" aria-label="Đang viết câu trả lời">
        <i />
        <i />
        <i />
      </div>
    );
  }
  if (state.error) return <ErrorState message={state.error} />;
  const d = state.data;
  if (!d || d.answer === null) {
    return (
      <p className="muted">
        Chưa có câu trả lời bằng chữ: {d?.note ?? "LLM không phản hồi."} Bảng ② và đồ thị ④ vẫn là bằng chứng đầy đủ.
      </p>
    );
  }
  return (
    <>
      <p className="answer">{d.answer}</p>
      <p className="muted small">{d.source === "cache" ? "Lấy từ bộ nhớ đệm của demo." : "Do LLM viết, chỉ dựa trên bảng kết quả ở trên."}</p>
      {d.reasoning && (
        <details>
          <summary>Các bước suy luận của LLM</summary>
          <pre className="reasoning">{d.reasoning}</pre>
        </details>
      )}
    </>
  );
}

function Evidence({ ids }: { ids: string[] }) {
  const { showInferred } = useInference();
  const navigate = useNavigate();
  const url = ids.length >= 2 ? `/api/subgraph?${ids.map((i) => `ids=${encodeURIComponent(i)}`).join("&")}` : null;
  const graph = useApi<GraphData>(url);
  if (ids.length < 2) return <Empty text="Kết quả có ít hơn hai thực thể nên chưa có quan hệ để vẽ." />;
  if (graph.loading) return <Loading text="Đang dựng đồ thị bằng chứng…" />;
  if (graph.error) return <ErrorState message={graph.error} />;
  if (!graph.data || graph.data.edges.length === 0) {
    return <Empty text="Các thực thể trong kết quả không nối trực tiếp với nhau (ví dụ câu hỏi tổng hợp), nên không có đồ thị để vẽ." />;
  }
  return (
    <GraphView
      title={`${graph.data.nodes.length} thực thể, ${graph.data.edges.length} quan hệ`}
      data={graph.data}
      expandable={false}
      showInferred={showInferred}
      onOpen={(id) => navigate(`/entity/${encodeURIComponent(id)}`)}
    />
  );
}

/** Màn Hỏi đáp có bằng chứng: câu hỏi → ① SPARQL → ② kết quả (có/không suy luận) → ③ câu trả lời → ④ đồ thị. */
export function AskPage() {
  const [params, setParams] = useSearchParams();
  const urlQuestion = params.get("q") ?? "";
  const urlSparqlMode = params.get("mode") === "sparql"; // giữ trong URL để chip / lịch sử / nút Back không mất
  const [input, setInput] = useState(urlQuestion);
  const [result, setResult] = useState<Remote<AskResult>>({ data: null, error: null, loading: false });
  const [answer, setAnswer] = useState<Remote<AnswerResult>>({ data: null, error: null, loading: false });
  const [skipped, setSkipped] = useState(false); // SPARQL mode: đã có kết quả nhưng chưa gọi LLM viết câu trả lời
  const [asserted, setAsserted] = useState<AssertedInfo | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const controller = useRef<AbortController | null>(null);
  const answerController = useRef<AbortController | null>(null);
  const health = useApi<Health>("/api/health");
  const overview = useApi<Overview>("/api/overview");
  const demoMode = health.data !== null && !health.data.llm;
  // demo mode không có LLM (câu trả lời lấy từ cache) nên SPARQL mode vô nghĩa: ẩn ô chọn và bỏ qua
  const sparqlMode = urlSparqlMode && !demoMode;
  const sparqlModeRef = useRef(sparqlMode);
  sparqlModeRef.current = sparqlMode;

  // gọi LLM viết câu trả lời từ bảng kết quả (tự động, hoặc theo yêu cầu khi đang ở SPARQL mode)
  const requestAnswer = useCallback((res: AskResult) => {
    answerController.current?.abort();
    const ctl = new AbortController();
    answerController.current = ctl;
    setSkipped(false);
    setAnswer({ data: null, error: null, loading: true });
    postJson<AnswerResult>("/api/ask/answer", { question: res.question, sparql: res.sparql, rows: res.rows }, ctl.signal)
      .then((data) => setAnswer({ data, error: null, loading: false }))
      .catch((e: unknown) => {
        if (!ctl.signal.aborted) setAnswer({ data: null, error: e instanceof Error ? e.message : String(e), loading: false });
      });
  }, []);

  const run = useCallback(
    (question: string) => {
      controller.current?.abort();
      answerController.current?.abort();
      const ctl = new AbortController();
      controller.current = ctl;
      setResult({ data: null, error: null, loading: true });
      setAnswer({ data: null, error: null, loading: false });
      setSkipped(false);
      setAsserted(null);
      setHistory((h) => [question, ...h.filter((q) => q !== question)].slice(0, HISTORY_SIZE));
      postJson<AskResult>("/api/ask", { question }, ctl.signal)
        .then((res) => {
          setResult({ data: res, error: null, loading: false });
          setAsserted(res.asserted);
          if (res.error) return;
          // SPARQL mode: dừng ở bảng kết quả, tiết kiệm một request LLM; người dùng bấm "Viết câu trả lời" khi cần
          if (sparqlModeRef.current) {
            setSkipped(true);
            return;
          }
          // câu trả lời đến sau: hiện SPARQL và bảng ngay, không chờ LLM
          requestAnswer(res);
        })
        .catch((e: unknown) => {
          if (ctl.signal.aborted) return;
          const message = e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e);
          setResult({ data: null, error: message, loading: false });
        });
    },
    [requestAnswer],
  );

  // có ?q= thì tự chạy; đổi ?q= (chip, nút Back) thì chạy lại
  useEffect(() => {
    setInput(urlQuestion);
    if (urlQuestion.trim()) run(urlQuestion.trim());
    return () => {
      controller.current?.abort();
      answerController.current?.abort();
    };
  }, [urlQuestion, run]);

  // tắt SPARQL mode khi đang có kết quả chưa trả lời: gọi LLM luôn, không bắt hỏi lại
  const pending = skipped && !sparqlMode ? result.data : null;
  useEffect(() => {
    if (pending && !pending.error) requestAnswer(pending);
  }, [pending, requestAnswer]);

  const setSparqlMode = (on: boolean) => {
    const next = new URLSearchParams(params);
    if (on) next.set("mode", "sparql");
    else next.delete("mode");
    setParams(next, { replace: true });
  };

  // graph "chỉ khai báo" nạp sau graph chính: hỏi lại cho tới khi có
  const sparql = result.data?.sparql;
  const waiting = asserted?.status === "loading";
  useEffect(() => {
    if (!waiting || !sparql) return;
    let cancelled = false;
    let tries = 0;
    let timer: number | undefined;
    const controller = new AbortController();
    const tick = async () => {
      tries += 1;
      try {
        const a = await postJson<AssertedInfo>("/api/ask/asserted", { sparql }, controller.signal);
        if (cancelled) return; // câu hỏi đã đổi hoặc rời trang: bỏ phản hồi cũ
        if (a.status !== "loading") {
          setAsserted(a);
          return;
        }
      } catch {
        if (cancelled) return;
      }
      if (tries >= POLL_MAX) {
        setAsserted({ rows: null, status: "error", error: "Quá thời gian chờ graph chỉ khai báo." });
        return;
      }
      timer = window.setTimeout(tick, POLL_MS);
    };
    timer = window.setTimeout(tick, POLL_MS);
    return () => {
      cancelled = true;
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [waiting, sparql]);

  const submit = (question: string) => {
    const q = question.trim();
    if (!q) return;
    if (q === urlQuestion) run(q);
    else setParams(urlSparqlMode ? { q, mode: "sparql" } : { q });
  };

  const data = result.data;
  return (
    <div className="ask">
      <h1 className="page-title">Hỏi đáp có bằng chứng</h1>
      <p className="muted lead">Hỏi bằng tiếng Việt; hệ thống sinh SPARQL, chạy trên graph và chỉ ra câu trả lời đến từ đâu.</p>
      <form
        className="ask-form"
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ví dụ: Cầu thủ nào từng chơi cho Than Quảng Ninh?"
          aria-label="Câu hỏi"
          autoFocus
        />
        <button type="submit" className="btn btn-primary" disabled={result.loading || !input.trim()}>
          {result.loading ? "Đang chạy…" : "Hỏi"}
        </button>
      </form>
      {demoMode ? (
        <p className="demo-note small">Chế độ demo: chưa có OPENAI_API_KEY nên chỉ trả lời được các câu hỏi mẫu bên dưới.</p>
      ) : (
        <label className="ask-mode">
          <input type="checkbox" checked={urlSparqlMode} onChange={(e) => setSparqlMode(e.target.checked)} />
          <span>SPARQL mode</span>
          <span className="muted small">Hiện truy vấn và kết quả thô, không gọi LLM viết câu trả lời (tiết kiệm 1 request)</span>
        </label>
      )}
      <div className="chips">
        {(overview.data?.questions ?? []).map((q) => (
          <button key={q} type="button" className="chip chip-btn" onClick={() => submit(q)}>
            {q}
          </button>
        ))}
      </div>
      {history.length > 1 && (
        <p className="small muted">
          Gần đây:{" "}
          {history.slice(1).map((q) => (
            <button key={q} type="button" className="link-btn" onClick={() => submit(q)}>
              {q}
            </button>
          ))}
        </p>
      )}

      {result.loading && <Loading text="Đang sinh và chạy SPARQL…" />}
      {result.error && <ErrorState message={result.error} />}
      {data && (
        <div className="ask-steps">
          <Step n={1} title="SPARQL sinh ra" hint={`${data.source === "cache" ? "từ bộ nhớ đệm demo" : "do LLM sinh"} · ${data.attempts} lần thử`}>
            <SparqlBlock sparql={data.sparql} />
            {data.error && <ErrorState message={data.error} />}
          </Step>
          {!data.error && (
            <>
              <Step n={2} title="Kết quả trên graph">
                <InferenceContrast withInference={data.rowsTotal} asserted={asserted ?? data.asserted} />
                {data.rowsTotal === 0 ? (
                  <Empty text="Truy vấn chạy được nhưng không có dòng nào: dữ liệu hiện chưa có thông tin này." />
                ) : (
                  <ResultTable columns={data.columns} rows={data.rows} links={data.links} total={data.rowsTotal} />
                )}
              </Step>
              <Step n={3} title="Câu trả lời" hint={skipped ? "SPARQL mode" : undefined}>
                {skipped ? (
                  <div className="ask-skip">
                    <p className="muted">Đã tắt bước viết câu trả lời (SPARQL mode). Bật lại để LLM trả lời từ bảng ②.</p>
                    <button type="button" className="btn" onClick={() => requestAnswer(data)}>
                      Viết câu trả lời
                    </button>
                  </div>
                ) : (
                  <AnswerBlock state={answer} />
                )}
              </Step>
              <Step n={4} title="Bằng chứng trên graph" hint="cạnh nét đứt tím là quan hệ do suy luận">
                <Evidence ids={data.evidence.map((n) => n.id)} />
              </Step>
            </>
          )}
        </div>
      )}
    </div>
  );
}


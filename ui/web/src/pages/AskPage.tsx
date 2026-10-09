import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, postJson } from "../api/client";
import type { AnswerResult, AskResult, AssertedInfo, GraphData, Health, LinkResult, Overview } from "../api/types";
import { useApi } from "../api/useApi";
import { CheckStep, GenerateStep, LinkStep, Pipeline, type PipelineStep, type StepState } from "../components/AskSteps";
import { GraphView } from "../components/GraphView";
import { InferenceContrast } from "../components/InferenceContrast";
import { ResultTable } from "../components/ResultTable";
import { Empty, ErrorState, Loading } from "../components/States";
import { useInference } from "../context/InferenceContext";
import { formatMs, formatNumber } from "../utils/format";

const HISTORY_SIZE = 5;
const POLL_MS = 3000;
const POLL_MAX = 40;

type Remote<T> = { data: T | null; error: string | null; loading: boolean };
const IDLE = { data: null, error: null, loading: false };
const LOADING = { data: null, error: null, loading: true };

function message(e: unknown): string {
  return e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e);
}

function Step({ n, title, hint, children }: { n: number; title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="card step" id={`ask-step-${n}`}>
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
        Chưa có câu trả lời bằng chữ: {d?.note ?? "LLM không phản hồi."} Bảng ở bước 4 và đồ thị ở bước 6 vẫn là bằng chứng đầy đủ.
      </p>
    );
  }
  return (
    <>
      <p className="answer">{d.answer}</p>
      <p className="muted small">
        {d.source === "cache" ? "Câu trả lời viết sẵn cho câu hỏi mẫu." : "Do LLM viết, chỉ dựa trên bảng kết quả ở bước 4 (tối đa 30 dòng)."}
        {d.reused && " Lấy lại câu trả lời đã viết trong phiên này, không gọi lại LLM."}
      </p>
      {d.reasoning && (
        <details>
          <summary>Các bước lập luận của LLM (không phải suy luận OWL)</summary>
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

/** Trạng thái sáu bước cho thanh tiến trình, suy ra từ các request đang chạy hoặc đã xong. */
function pipeline(
  link: Remote<LinkResult>,
  result: Remote<AskResult>,
  answer: Remote<AnswerResult>,
  skipped: boolean,
): PipelineStep[] {
  const d = result.data;
  const ok = d !== null && !d.error;
  const gen = d?.steps.generate;
  const checks = d?.steps.checks ?? [];
  const pending = (fallback: StepState): StepState => (result.loading ? "wait" : result.error ? "skip" : fallback);
  const answerState: StepState = !ok
    ? pending("skip")
    : skipped
      ? "skip"
      : answer.loading
        ? "run"
        : answer.error
          ? "fail"
          : answer.data?.answer
            ? "done"
            : answer.data
              ? "skip"
              : "wait";
  return [
    {
      n: 1,
      title: "Nhận diện thực thể",
      state: link.loading ? "run" : link.error ? "fail" : link.data ? "done" : "wait",
      note: link.data ? `${link.data.mentions.length} tên · ${formatMs(link.data.ms)}` : undefined,
    },
    {
      n: 2,
      title: "Sinh SPARQL",
      state: result.loading ? "run" : result.error || d?.error ? "fail" : d ? "done" : "wait",
      note: gen
        ? gen.source === "cache"
          ? "viết sẵn"
          : `LLM · ${gen.attempts.length} lần · ${formatMs(gen.attempts.reduce((s, a) => s + (a.llmMs ?? 0), 0))}`
        : undefined,
    },
    {
      n: 3,
      title: "Kiểm tra truy vấn",
      state: d
        ? checks.some((c) => c.status === "fail")
          ? "fail"
          : checks.some((c) => c.status === "warn")
            ? "warn"
            : "done"
        : pending("wait"),
      note: d ? `${checks.filter((c) => c.status === "ok").length}/${checks.length} đạt` : undefined,
    },
    {
      n: 4,
      title: "Chạy trên graph",
      state: ok ? "done" : d ? "skip" : pending("wait"),
      note: ok && d ? `${formatNumber(d.rowsTotal)} dòng · ${formatMs(d.steps.run.ms)}` : undefined,
    },
    {
      n: 5,
      title: "Trả lời",
      state: answerState,
      note: skipped ? "SPARQL mode" : answer.data?.answer && answer.data.source === "llm" ? formatMs(answer.data.ms) : undefined,
    },
    {
      n: 6,
      title: "Bằng chứng",
      state: ok ? "done" : d ? "skip" : pending("wait"),
      note: ok && d ? `${d.evidence.length} thực thể` : undefined,
    },
  ];
}

/** Màn Hỏi đáp có bằng chứng, chia sáu bước: nhận diện thực thể → sinh SPARQL → kiểm tra → chạy → trả lời → bằng chứng. */
export function AskPage() {
  const [params, setParams] = useSearchParams();
  const urlQuestion = params.get("q") ?? "";
  // giữ trong URL để chip / lịch sử / nút Back không mất
  const urlSparqlMode = params.get("mode") === "sparql";
  const [input, setInput] = useState(urlQuestion);
  const [link, setLink] = useState<Remote<LinkResult>>(IDLE);
  const [result, setResult] = useState<Remote<AskResult>>(IDLE);
  const [answer, setAnswer] = useState<Remote<AnswerResult>>(IDLE);
  const [skipped, setSkipped] = useState(false); // SPARQL mode: đã có kết quả nhưng chưa gọi LLM viết câu trả lời
  const [asserted, setAsserted] = useState<AssertedInfo | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const controller = useRef<AbortController | null>(null);
  const answerController = useRef<AbortController | null>(null);
  const health = useApi<Health>("/api/health");
  const overview = useApi<Overview>("/api/overview");
  const demoMode = health.data !== null && !health.data.llm;
  // không có LLM thì câu trả lời là bản viết sẵn: ẩn công tắc SPARQL mode
  const sparqlMode = urlSparqlMode && !demoMode;
  const sparqlModeRef = useRef(sparqlMode);
  sparqlModeRef.current = sparqlMode;

  // bước 5: LLM viết câu trả lời từ bảng kết quả (tự động, hoặc theo yêu cầu khi đang ở SPARQL mode)
  const requestAnswer = useCallback((res: AskResult) => {
    answerController.current?.abort();
    const ctl = new AbortController();
    answerController.current = ctl;
    setSkipped(false);
    setAnswer(LOADING);
    postJson<AnswerResult>("/api/ask/answer", { question: res.question, sparql: res.sparql, rows: res.rows }, ctl.signal)
      .then((data) => setAnswer({ data, error: null, loading: false }))
      .catch((e: unknown) => {
        if (!ctl.signal.aborted) setAnswer({ data: null, error: message(e), loading: false });
      });
  }, []);

  const run = useCallback(
    (question: string, fresh = false) => {
      controller.current?.abort();
      answerController.current?.abort();
      const ctl = new AbortController();
      controller.current = ctl;
      setLink(LOADING);
      setResult(LOADING);
      setAnswer(IDLE);
      setSkipped(false);
      setAsserted(null);
      setHistory((h) => [question, ...h.filter((q) => q !== question)].slice(0, HISTORY_SIZE));
      // bước 1 chỉ mất vài ms: hiện ngay trong lúc LLM còn đang viết SPARQL
      postJson<LinkResult>("/api/ask/link", { question }, ctl.signal)
        .then((data) => setLink({ data, error: null, loading: false }))
        .catch((e: unknown) => {
          if (!ctl.signal.aborted) setLink({ data: null, error: message(e), loading: false });
        });
      // có key thì server gọi LLM; LLM lỗi hoặc không có key thì câu mẫu tự dùng SPARQL viết sẵn
      postJson<AskResult>("/api/ask", { question, fresh }, ctl.signal)
        .then((res) => {
          setResult({ data: res, error: null, loading: false });
          setLink({ data: res.steps.link, error: null, loading: false });
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
          setResult({ data: null, error: message(e), loading: false });
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
  const pendingAnswer = skipped && !sparqlMode ? result.data : null;
  useEffect(() => {
    if (pendingAnswer && !pendingAnswer.error) requestAnswer(pendingAnswer);
  }, [pendingAnswer, requestAnswer]);

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
    const ctl = new AbortController();
    const tick = async () => {
      tries += 1;
      try {
        const a = await postJson<AssertedInfo>("/api/ask/asserted", { sparql }, ctl.signal);
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
      ctl.abort();
      window.clearTimeout(timer);
    };
  }, [waiting, sparql]);

  const submit = (question: string) => {
    const q = question.trim();
    if (!q) return;
    if (q === urlQuestion) {
      run(q);
      return;
    }
    const next = new URLSearchParams(params);
    next.set("q", q);
    setParams(next);
  };

  const data = result.data;
  const ok = data !== null && !data.error;
  const started = link.loading || link.data !== null || result.loading || data !== null || result.error !== null;
  const llmSource = data ? data.source === "llm" : !demoMode;
  return (
    <div className="ask">
      <h1 className="page-title">Hỏi đáp có bằng chứng</h1>
      <p className="muted lead">
        Đặt câu hỏi bằng tiếng Việt, LLM viết SPARQL và hệ thống chạy truy vấn trên đồ thị tri thức. Câu trả lời luôn kèm truy vấn đã
        chạy và các triple làm bằng chứng, tách phần khai báo với phần suy luận OWL 2 RL.
      </p>
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
        <p className="demo-note small">
          Chế độ demo: chưa có OPENAI_API_KEY nên chỉ trả lời được các câu hỏi mẫu bên dưới, bằng SPARQL viết sẵn.
        </p>
      ) : (
        <label className="ask-mode">
          <input type="checkbox" checked={urlSparqlMode} onChange={(e) => setSparqlMode(e.target.checked)} />
          <span>SPARQL mode</span>
          <span className="muted small">Dừng ở bảng kết quả, không gọi LLM viết câu trả lời (tiết kiệm 1 request)</span>
        </label>
      )}
      <div className="chips">
        {(overview.data?.questions ?? []).map((q) => (
          <button key={q} type="button" className="chip chip-btn" onClick={() => submit(q)}>
            {q}
          </button>
        ))}
      </div>
      {overview.data?.questionHint && (
        <p className="small muted">
          Không cần gõ dấu, thử:{" "}
          <button type="button" className="link-btn" onClick={() => submit(overview.data?.questionHint ?? "")}>
            {overview.data.questionHint}
          </button>
        </p>
      )}
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

      {started && (
        <div className="ask-steps">
          <Pipeline steps={pipeline(link, result, answer, skipped)} />
          <Step n={1} title="Nhận diện thực thể" hint={link.data ? formatMs(link.data.ms) : undefined}>
            {link.loading && <Loading text="Đang tìm tên thực thể trong câu hỏi…" />}
            {link.error && <ErrorState message={link.error} />}
            {link.data && <LinkStep link={link.data} llm={llmSource} />}
          </Step>
          <Step
            n={2}
            title="Sinh SPARQL"
            hint={data ? (data.source === "cache" ? "SPARQL viết sẵn" : `do LLM sinh · ${data.attempts} lần thử`) : undefined}
          >
            {result.loading && (
              <Loading text={demoMode ? "Đang chạy SPARQL viết sẵn…" : "LLM đang đọc schema và viết SPARQL…"} />
            )}
            {result.error && <ErrorState message={result.error} />}
            {data && <GenerateStep gen={data.steps.generate} sparql={data.sparql} onFresh={() => run(data.question, true)} />}
            {data?.error && <ErrorState message={`Không tạo được truy vấn chạy được sau ${data.attempts} lần: ${data.error}`} />}
          </Step>
          {data && data.steps.checks.length > 0 && (
            <Step n={3} title="Kiểm tra truy vấn" hint="trước khi tin kết quả">
              <CheckStep checks={data.steps.checks} terms={data.steps.terms} />
            </Step>
          )}
          {ok && data && (
            <>
              <Step n={4} title="Chạy trên graph" hint={`${formatNumber(data.rowsTotal)} dòng · ${formatMs(data.steps.run.ms)}`}>
                <InferenceContrast withInference={data.rowsTotal} asserted={asserted ?? data.asserted} />
                {data.rowsTotal === 0 ? (
                  <Empty text="Truy vấn chạy được nhưng không có dòng nào: dữ liệu hiện chưa có thông tin này." />
                ) : (
                  <ResultTable columns={data.columns} rows={data.rows} links={data.links} total={data.rowsTotal} />
                )}
              </Step>
              <Step
                n={5}
                title="Câu trả lời"
                hint={skipped ? "SPARQL mode" : answer.data?.answer && answer.data.source === "llm" ? `LLM · ${formatMs(answer.data.ms)}` : undefined}
              >
                {skipped ? (
                  <div className="ask-skip">
                    <p className="muted">Đã tắt bước viết câu trả lời (SPARQL mode). Bật lại để LLM trả lời từ bảng ở bước 4.</p>
                    <button type="button" className="btn" onClick={() => requestAnswer(data)}>
                      Viết câu trả lời
                    </button>
                  </div>
                ) : (
                  <AnswerBlock state={answer} />
                )}
              </Step>
              <Step n={6} title="Bằng chứng trên graph" hint="cạnh nét đứt tím là quan hệ do suy luận">
                <Evidence ids={data.evidence.map((n) => n.id)} />
              </Step>
            </>
          )}
        </div>
      )}
    </div>
  );
}

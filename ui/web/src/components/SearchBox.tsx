import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, getJson } from "../api/client";
import type { SearchHit } from "../api/types";
import { kindColorVar } from "../utils/kinds";

const DEBOUNCE_MS = 200;

/** Kết quả luôn đi kèm chuỗi đã tìm, để Enter không mở nhầm kết quả của chuỗi cũ. */
interface Results {
  q: string;
  hits: SearchHit[];
  status: "ok" | "error";
  error?: string;
}

function describe(e: unknown): string {
  if (e instanceof ApiError && e.status === 503) return "Graph đang nạp…";
  if (e instanceof ApiError) return e.message;
  return "Không kết nối được máy chủ API.";
}

/** Ô tìm thực thể (không cần dấu): debounce 200ms, điều khiển bằng ↑ ↓ Enter Esc. */
export function SearchBox() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Results | null>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const box = useRef<HTMLDivElement>(null);

  const text = q.trim();
  const current = results && results.q === text ? results : null; // null = chưa có kết quả cho chuỗi đang gõ
  const hits = current?.hits ?? [];

  useEffect(() => {
    if (!text) {
      setResults(null);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      getJson<SearchHit[]>(`/api/search?q=${encodeURIComponent(text)}&limit=10`, controller.signal)
        .then((r) => {
          setResults({ q: text, hits: r, status: "ok" });
          setActive(-1);
          setOpen(true);
        })
        .catch((e: unknown) => {
          if (controller.signal.aborted) return;
          setResults({ q: text, hits: [], status: "error", error: describe(e) });
          setOpen(true);
        });
    }, DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [text]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as globalThis.Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const go = (hit: SearchHit) => {
    setOpen(false);
    setQ("");
    navigate(`/entity/${encodeURIComponent(hit.id)}`);
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((a) => Math.min(a + 1, hits.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      // chỉ mở khi kết quả đúng là của chuỗi đang gõ (đang chờ API thì bỏ qua)
      const hit = current ? hits[active >= 0 ? active : 0] : undefined;
      if (hit) go(hit);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="search" ref={box}>
      <input
        type="search"
        value={q}
        placeholder="Tìm thực thể (Công Phượng, Hà Nội…)"
        aria-label="Tìm thực thể"
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => current && setOpen(true)}
        onKeyDown={onKey}
      />
      {open && current && (
        <ul className="search-list" role="listbox">
          {current.status === "error" && <li className="search-none search-error">{current.error}</li>}
          {current.status === "ok" && hits.length === 0 && <li className="search-none">Không tìm thấy thực thể nào.</li>}
          {hits.map((h, i) => (
            <li
              key={h.id}
              role="option"
              aria-selected={i === active}
              className={i === active ? "active" : ""}
              onMouseDown={(e) => {
                e.preventDefault();
                go(h);
              }}
              onMouseEnter={() => setActive(i)}
            >
              <i className="dot" style={{ background: kindColorVar(h.kind) }} />
              <span className="search-label">{h.label}</span>
              {h.cls && <span className="search-cls">{h.cls}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

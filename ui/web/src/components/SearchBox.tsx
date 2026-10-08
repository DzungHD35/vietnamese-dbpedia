import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { getJson } from "../api/client";
import type { SearchHit } from "../api/types";
import { kindColorVar } from "../utils/kinds";

const DEBOUNCE_MS = 200;

/** Ô tìm thực thể (không cần dấu): debounce 200ms, điều khiển bằng ↑ ↓ Enter Esc. */
export function SearchBox() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [searched, setSearched] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const text = q.trim();
    if (!text) {
      setHits([]);
      setSearched(false);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      getJson<SearchHit[]>(`/api/search?q=${encodeURIComponent(text)}&limit=10`, controller.signal)
        .then((r) => {
          setHits(r);
          setActive(-1);
          setSearched(true);
          setOpen(true);
        })
        .catch(() => {});
    }, DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [q]);

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
      const hit = hits[active >= 0 ? active : 0];
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
        onFocus={() => hits.length > 0 && setOpen(true)}
        onKeyDown={onKey}
      />
      {open && searched && (
        <ul className="search-list" role="listbox">
          {hits.length === 0 && <li className="search-none">Không tìm thấy thực thể nào.</li>}
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

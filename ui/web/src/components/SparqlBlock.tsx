import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { copyText } from "../utils/clipboard";

// một lượt quét: chú thích | chuỗi | biến | từ khoá | tên có tiền tố (prefix:tên)
const TOKEN =
  /(#[^\n]*)|("(?:[^"\\\n]|\\.)*"(?:@[\w-]+|\^\^\S+)?)|(\?\w+)|\b(SELECT|DISTINCT|WHERE|OPTIONAL|FILTER|NOT|EXISTS|GROUP|BY|ORDER|ASC|DESC|LIMIT|OFFSET|COUNT|AS|VALUES|ASK|CONSTRUCT|DESCRIBE|UNION|PREFIX|LCASE|STR|CONTAINS|STRSTARTS|LANG|BIND|HAVING|MIN|MAX|SUM|AVG)\b|(\b[a-z][\w-]*:[\w\-.]*[\w-])/gi;
const CLASSES = ["tok-comment", "tok-string", "tok-var", "tok-keyword", "tok-name"];

function highlight(text: string) {
  const parts: (string | JSX.Element)[] = [];
  let last = 0;
  for (const m of text.matchAll(TOKEN)) {
    const at = m.index ?? 0;
    if (at > last) parts.push(text.slice(last, at));
    const group = m.slice(1).findIndex((g) => g !== undefined);
    parts.push(
      <span key={at} className={CLASSES[group]}>
        {m[0]}
      </span>,
    );
    last = at + m[0].length;
  }
  parts.push(text.slice(last));
  return parts;
}

/** Khối SPARQL chỉ đọc, tô màu đơn giản; có nút Sao chép và mở trong trang SPARQL. */
export function SparqlBlock({ sparql, openable = true }: { sparql: string; openable?: boolean }) {
  const [copied, setCopied] = useState<"idle" | "done" | "selected">("idle");
  const pre = useRef<HTMLPreElement>(null);
  const copy = async () => {
    // không có navigator.clipboard (HTTP không phải localhost) thì chọn sẵn văn bản để Ctrl+C
    const ok = await copyText(sparql, pre.current);
    setCopied(ok ? "done" : "selected");
    window.setTimeout(() => setCopied("idle"), 1800);
  };
  return (
    <div className="sparql-block">
      <div className="sparql-tools">
        <button type="button" className="btn" onClick={copy}>
          {copied === "done" ? "Đã sao chép" : copied === "selected" ? "Đã chọn, nhấn Ctrl+C" : "Sao chép"}
        </button>
        {openable && (
          <Link className="btn" to={`/sparql?query=${encodeURIComponent(sparql)}`}>
            Mở trong SPARQL
          </Link>
        )}
      </div>
      <pre ref={pre}>{highlight(sparql)}</pre>
    </div>
  );
}

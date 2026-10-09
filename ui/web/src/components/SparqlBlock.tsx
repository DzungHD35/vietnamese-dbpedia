import { useState } from "react";
import { Link } from "react-router-dom";

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
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard
      .writeText(sparql)
      .then(() => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => setCopied(false));
  };
  return (
    <div className="sparql-block">
      <div className="sparql-tools">
        <button type="button" className="btn" onClick={copy}>
          {copied ? "Đã sao chép" : "Sao chép"}
        </button>
        {openable && (
          <Link className="btn" to={`/sparql?query=${encodeURIComponent(sparql)}`}>
            Mở trong SPARQL
          </Link>
        )}
      </div>
      <pre>{highlight(sparql)}</pre>
    </div>
  );
}

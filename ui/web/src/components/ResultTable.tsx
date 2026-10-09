import type { Cells, Node } from "../api/types";
import { formatNumber, shortIri } from "../utils/format";
import { EntityLink } from "./EntityLink";

const MAX_CELL = 160;

interface Props {
  columns: string[];
  rows: Cells[];
  links: Record<string, Node>;
  total?: number;
}

function Cell({ value, node }: { value: string; node?: Node }) {
  if (node) return <EntityLink node={node} />;
  if (/^https?:\/\/\S+$/.test(value)) {
    return (
      <a href={value} target="_blank" rel="noopener noreferrer" title={value}>
        {shortIri(value)} ↗
      </a>
    );
  }
  return <span title={value.length > MAX_CELL ? value : undefined}>{value.length > MAX_CELL ? `${value.slice(0, MAX_CELL - 1)}…` : value}</span>;
}

/** Bảng kết quả SPARQL: ô nhận ra là thực thể (có trong `links`) thành link sang màn Thực thể. */
export function ResultTable({ columns, rows, links, total }: Props) {
  const all = total ?? rows.length;
  return (
    <div className="result">
      <div className="result-scroll">
        <table className="result-table">
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {columns.map((c) => (
                  <td key={c}>
                    <Cell value={r[c] ?? ""} node={links[r[c] ?? ""]} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {all > rows.length && (
        <p className="muted small">
          Hiện {formatNumber(rows.length)} / {formatNumber(all)} dòng.
        </p>
      )}
    </div>
  );
}

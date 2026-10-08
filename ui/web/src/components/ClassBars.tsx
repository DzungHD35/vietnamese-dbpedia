import type { ClassRow } from "../api/types";
import { formatNumber } from "../utils/format";

const MIN_BAR_PCT = 0.6; // lớp rất nhỏ (1 thực thể) vẫn nhìn thấy được

/** Cây lớp vio: dạng thanh ngang thụt lề; độ dài ∝ số thực thể, chia đoạn khai báo / suy luận. */
export function ClassBars({ rows, showInferred }: { rows: ClassRow[]; showInferred: boolean }) {
  const depth = new Map<string, number>();
  for (const r of rows) depth.set(r.id, r.parent ? (depth.get(r.parent) ?? 0) + 1 : 0);
  const max = Math.max(...rows.map((r) => r.total), 1);
  const pct = (n: number) => (n === 0 ? 0 : Math.max((n / max) * 100, MIN_BAR_PCT));

  return (
    <ul className="classbars">
      {rows.map((r) => {
        const inferredOnly = r.asserted === 0;
        const faded = !showInferred && inferredOnly;
        return (
          <li key={r.id} className={faded ? "faded" : ""} style={{ paddingLeft: (depth.get(r.id) ?? 0) * 18 }}>
            <div className="cb-name">
              <strong>{r.label.replace(/ \(.*\)$/, "")}</strong> <code>{r.id}</code>
              {r.dbo.length > 0 && <span className="cb-sub">⊑ {r.dbo.join(", ")}</span>}
            </div>
            <div className="cb-track" title={`${formatNumber(r.asserted)} khai báo · ${formatNumber(r.total - r.asserted)} suy luận`}>
              <span className="cb-asserted" style={{ width: `${pct(r.asserted)}%` }} />
              {showInferred && r.total > r.asserted && (
                <span className="cb-inferred" style={{ width: `${pct(r.total) - pct(r.asserted)}%` }} />
              )}
            </div>
            <div className="cb-num">
              {formatNumber(showInferred ? r.total : r.asserted)}
              {faded && <span className="cb-hint">chỉ nhờ suy luận</span>}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

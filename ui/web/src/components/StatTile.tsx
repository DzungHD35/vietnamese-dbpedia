interface Props {
  value: string;
  label: string;
  note?: string;
  tone?: "inferred" | "ok";
  onClick?: () => void;
}

/** Số lớn + nhãn + chú thích nhỏ; bấm được nếu có `onClick`. */
export function StatTile({ value, label, note, tone, onClick }: Props) {
  const cls = `tile${tone ? ` tile-${tone}` : ""}${onClick ? " tile-click" : ""}`;
  const body = (
    <>
      <span className="tile-value">{value}</span>
      <span className="tile-label">{label}</span>
      {note && <span className="tile-note">{note}</span>}
    </>
  );
  return onClick ? (
    <button type="button" className={cls} onClick={onClick}>
      {body}
    </button>
  ) : (
    <div className={cls}>{body}</div>
  );
}

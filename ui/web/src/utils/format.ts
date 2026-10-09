const vn = new Intl.NumberFormat("vi-VN");

/** 131233 → "131.233" */
export function formatNumber(n: number | null | undefined): string {
  return n == null ? "—" : vn.format(n);
}

const seconds = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 });

/** 12.3 → "12 ms", 1834 → "1,8 s" */
export function formatMs(ms: number | null | undefined): string {
  if (ms == null) return "—";
  return ms < 1000 ? `${Math.round(ms)} ms` : `${seconds.format(ms / 1000)} s`;
}

const INTEGER_TYPES = new Set(["xsd:integer", "xsd:int", "xsd:nonNegativeInteger", "xsd:positiveInteger", "xsd:long"]);
const DECIMAL_TYPES = new Set(["xsd:double", "xsd:decimal", "xsd:float"]);
const decimal = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 });

/** Literal số → dạng Việt (1.234 / 1,78); kiểu khác giữ nguyên chuỗi. */
export function formatLiteral(value: string, datatype?: string): string {
  const n = Number(value);
  if (datatype && Number.isFinite(n)) {
    if (INTEGER_TYPES.has(datatype)) return vn.format(n);
    if (DECIMAL_TYPES.has(datatype)) return decimal.format(n);
  }
  return value;
}

/** "Câu lạc bộ bóng đá Hải Phòng" → "Hải Phòng": nhãn ngắn để vừa thanh timeline. */
export function shortTeamName(label: string): string {
  return label
    .replace(/^Câu lạc bộ bóng đá /, "")
    .replace(/^Đội tuyển bóng đá quốc gia /, "ĐTQG ")
    .replace(/^Đội tuyển bóng đá /, "ĐT ");
}

/** IRI/URL dài → dạng ngắn để hiển thị (bỏ giao thức, giải mã %, cắt gọn). */
export function shortIri(iri: string, max = 56): string {
  let text = iri.replace(/^https?:\/\//, "");
  try {
    text = decodeURIComponent(text);
  } catch {
    /* giữ nguyên nếu % không hợp lệ */
  }
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

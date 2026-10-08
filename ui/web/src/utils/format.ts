const vn = new Intl.NumberFormat("vi-VN");

/** 131233 → "131.233" */
export function formatNumber(n: number | null | undefined): string {
  return n == null ? "—" : vn.format(n);
}

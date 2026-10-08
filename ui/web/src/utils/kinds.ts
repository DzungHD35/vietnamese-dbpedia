import type { Kind } from "../api/types";

export const KIND_LABEL: Record<Kind, string> = {
  player: "Cầu thủ",
  club: "CLB / đội tuyển",
  stadium: "Sân vận động",
  uni: "Đại học",
  prov: "Tỉnh / quốc gia",
  station: "Chặng sự nghiệp",
  lod: "LOD bên ngoài",
  other: "Khác",
};

/** Tên biến CSS (tokens.css) của màu theo loại thực thể. */
export function kindColorVar(kind: Kind): string {
  return `var(--k-${kind})`;
}

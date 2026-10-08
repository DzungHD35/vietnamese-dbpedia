// Kiểu dữ liệu JSON của ui/api (xem .agents/PLAN.md §2). Cập nhật khi thêm endpoint.

export type Kind = "player" | "club" | "stadium" | "uni" | "prov" | "station" | "other" | "lod";

export interface Health {
  ready: boolean;
  asserted_ready: boolean;
  llm: boolean;
  message: string;
  error: string | null;
}

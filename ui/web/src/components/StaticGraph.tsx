import type { MouseEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useApi } from "../api/useApi";
import { ErrorState, Loading } from "./States";

/**
 * Đồ thị lân cận dạng hình tĩnh, đúng hình của trang tài nguyên Gradio: máy chủ gọi lại
 * `ResourceView._graph_svg` của team (bố cục hai phía, tên thuộc tính dưới từng nút, cạnh suy luận nét đứt,
 * nút LOD viền đứt, chú giải). Tắt "Hiện suy luận" thì máy chủ vẽ lại chỉ với quan hệ khai báo.
 * Nút trỏ tới /resource/… (Linked Data) được mở thẳng trang thực thể của giao diện này.
 */
export function StaticGraph({ id, showInferred }: { id: string; showInferred: boolean }) {
  const navigate = useNavigate();
  const url = `/api/entity/${encodeURIComponent(id)}/graph${showInferred ? "" : "?inferred=false"}`;
  const graph = useApi<{ html: string }>(url);

  if (graph.loading && !graph.data) return <Loading text="Đang vẽ đồ thị lân cận…" />;
  if (graph.error) return <ErrorState message={graph.error} />;
  if (!graph.data) return null;

  const onClick = (ev: MouseEvent<HTMLDivElement>) => {
    const a = (ev.target as Element).closest("a");
    const href = a?.getAttribute("href") ?? "";
    if (href.startsWith("/resource/") && !ev.ctrlKey && !ev.metaKey && !ev.shiftKey) {
      ev.preventDefault();
      navigate(`/entity/${href.slice("/resource/".length)}`);
    }
  };

  // HTML do máy chủ sinh từ dữ liệu của chính dataset, mọi chuỗi đã được escape phía máy chủ (esc của team)
  return <div className="static-graph" onClick={onClick} dangerouslySetInnerHTML={{ __html: graph.data.html }} />;
}

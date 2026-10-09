import type { ReactNode } from "react";
import type { Health } from "../api/types";
import { ErrorState } from "./States";

const START_CMD = ".venv/bin/python -m ui.api           # Linux / macOS\n.venv\\Scripts\\python -m ui.api        # Windows";

/** Chỉ cho vào trang khi graph đã nạp xong; lần nạp đầu có thể mất vài chục giây nên báo rõ đang làm gì. */
export function GraphGate({ health, offline, children }: { health: Health | null; offline: boolean; children: ReactNode }) {
  if (offline) {
    return (
      <div className="gate">
        <ErrorState message="Không kết nối được máy chủ API (hoặc kiểm tra cổng đang dùng). Hãy chạy từ thư mục gốc dự án:" />
        <pre className="curl gate-cmd">{START_CMD}</pre>
      </div>
    );
  }
  if (health?.error) {
    return (
      <div className="gate">
        <ErrorState message={`Nạp graph thất bại: ${health.error}`} />
      </div>
    );
  }
  if (!health?.ready) {
    return (
      <div className="gate" role="status">
        <div className="spinner" />
        <h2>{health?.message ?? "Đang kết nối tới máy chủ…"}</h2>
        <p className="muted">Máy chủ đang nạp toàn bộ graph vào bộ nhớ (thường mất vài giây tới vài chục giây). Trang sẽ tự mở khi xong.</p>
      </div>
    );
  }
  return <>{children}</>;
}

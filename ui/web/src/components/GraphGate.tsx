import type { ReactNode } from "react";
import type { Health } from "../api/types";
import { ErrorState } from "./States";

/** Chỉ cho vào trang khi graph đã nạp xong; lần nạp đầu có thể mất vài chục giây nên báo rõ đang làm gì. */
export function GraphGate({ health, offline, children }: { health: Health | null; offline: boolean; children: ReactNode }) {
  if (offline) {
    return (
      <div className="gate">
        <ErrorState message="Không kết nối được máy chủ API. Hãy chạy: .venv/bin/python -m ui.api (hoặc kiểm tra cổng đang dùng)." />
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
        <p className="muted">Lần khởi động đầu cần nạp khoảng 131 nghìn triple vào bộ nhớ. Trang sẽ tự mở khi xong.</p>
      </div>
    );
  }
  return <>{children}</>;
}

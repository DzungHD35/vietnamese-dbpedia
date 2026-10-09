import type { Health } from "../api/types";

/** Trạng thái graph ở góc thanh điều hướng. */
export function HealthBadge({ health, offline }: { health: Health | null; offline: boolean }) {
  if (offline) return <span className="health error"><i className="health-dot" />Không kết nối được API</span>;
  if (!health) return <span className="health"><i className="health-dot" />Đang kết nối…</span>;
  if (health.error) return <span className="health error" title={health.error}><i className="health-dot" />Lỗi nạp graph</span>;
  return (
    <span className={`health${health.ready ? " ready" : ""}`}>
      <i className="health-dot" />
      {health.ready ? "Graph sẵn sàng" : health.message}
    </span>
  );
}

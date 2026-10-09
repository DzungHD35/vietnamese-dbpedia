import type { Health } from "../api/types";

/** Góc phải thanh điều hướng: tên nhóm khi graph sẵn sàng, trạng thái graph khi đang nạp hoặc lỗi. */
export function HealthBadge({ health, offline }: { health: Health | null; offline: boolean }) {
  if (offline) return <span className="health error"><i className="health-dot" />Không kết nối được API</span>;
  if (!health) return <span className="health"><i className="health-dot" />Đang kết nối…</span>;
  if (health.error) return <span className="health error" title={health.error}><i className="health-dot" />Lỗi nạp graph</span>;
  // bình thường hiện tên nhóm; chỉ khi đang nạp, lỗi hoặc mất kết nối mới hiện trạng thái graph
  if (health.ready) {
    return (
      <span className="health team" title="Graph sẵn sàng">
        Group 23
      </span>
    );
  }
  return (
    <span className="health">
      <i className="health-dot" />
      {health.message}
    </span>
  );
}

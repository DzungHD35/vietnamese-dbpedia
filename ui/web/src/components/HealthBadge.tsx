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
        <svg
          className="team-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="9" cy="7" r="4" />
          <path d="M2 21v-2a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v2" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
        </svg>
        <span className="team-name">Group 23</span>
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

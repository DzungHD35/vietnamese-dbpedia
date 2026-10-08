import { useEffect, useState } from "react";
import { getJson } from "../api/client";
import type { Health } from "../api/types";

const POLL_MS = 2000;

/** Trạng thái graph ở góc thanh điều hướng; hỏi lại mỗi 2 giây cho tới khi graph sẵn sàng. */
export function HealthBadge() {
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let timer: number | undefined;
    const controller = new AbortController();
    const poll = async () => {
      try {
        const h = await getJson<Health>("/api/health", controller.signal);
        setHealth(h);
        setOffline(false);
        if (h.ready || h.error) return;
      } catch {
        if (controller.signal.aborted) return;
        setOffline(true);
      }
      timer = window.setTimeout(poll, POLL_MS);
    };
    poll();
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, []);

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

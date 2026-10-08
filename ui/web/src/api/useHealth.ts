import { useEffect, useState } from "react";
import { getJson } from "./client";
import type { Health } from "./types";

const POLL_MS = 2000;

/** Trạng thái graph; hỏi lại mỗi 2 giây cho tới khi sẵn sàng (hoặc lỗi), mất kết nối thì hỏi tiếp. */
export function useHealth(): { health: Health | null; offline: boolean } {
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

  return { health, offline };
}

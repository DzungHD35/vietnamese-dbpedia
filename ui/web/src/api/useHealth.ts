import { useEffect, useState } from "react";
import { getJson, UNREADY_EVENT } from "./client";
import type { Health } from "./types";

const POLL_MS = 2000;

/**
 * Trạng thái graph; hỏi lại mỗi 2 giây cho tới khi sẵn sàng (hoặc lỗi), mất kết nối thì hỏi tiếp.
 * Sau khi sẵn sàng, nếu một API khác trả 503 (server khởi động lại, graph nạp lại) thì hỏi lại từ đầu
 * để GraphGate hiện màn "Đang nạp graph…" thay vì để từng trang báo lỗi.
 */
export function useHealth(): { health: Health | null; offline: boolean } {
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let timer: number | undefined;
    let polling = false;

    const poll = async () => {
      polling = true;
      try {
        const h = await getJson<Health>("/api/health", controller.signal);
        setHealth(h);
        setOffline(false);
        if (h.ready || h.error) {
          polling = false;
          return;
        }
      } catch {
        if (controller.signal.aborted) return;
        setOffline(true);
      }
      timer = window.setTimeout(poll, POLL_MS);
    };

    const onUnready = () => {
      if (polling || controller.signal.aborted) return;
      setHealth((h) => (h ? { ...h, ready: false, message: "Graph đang nạp lại…" } : h));
      poll();
    };

    window.addEventListener(UNREADY_EVENT, onUnready);
    poll();
    return () => {
      controller.abort();
      window.clearTimeout(timer);
      window.removeEventListener(UNREADY_EVENT, onUnready);
    };
  }, []);

  return { health, offline };
}

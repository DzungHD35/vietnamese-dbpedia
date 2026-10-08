import { useEffect, useState } from "react";
import { getJson } from "./client";

export interface ApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/** GET `url` và huỷ request khi `url` đổi hoặc component bị gỡ; `url = null` thì không gọi. */
export function useApi<T>(url: string | null): ApiState<T> {
  const [state, setState] = useState<ApiState<T>>({ data: null, error: null, loading: url !== null });

  useEffect(() => {
    if (url === null) {
      setState({ data: null, error: null, loading: false });
      return;
    }
    const controller = new AbortController();
    setState((s) => ({ data: s.data, error: null, loading: true }));
    getJson<T>(url, controller.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setState({ data: null, error: e instanceof Error ? e.message : String(e), loading: false });
      });
    return () => controller.abort();
  }, [url]);

  return state;
}

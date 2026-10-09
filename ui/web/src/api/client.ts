/** Lỗi từ API, kèm mã HTTP và thông báo tiếng Việt do server trả về. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function parse<T>(res: Response): Promise<T> {
  if (res.ok) return (await res.json()) as T;
  let message = `Lỗi ${res.status}`;
  try {
    const body = await res.json();
    message = body.detail ?? body.error ?? message;
  } catch {
    /* thân phản hồi không phải JSON: giữ thông báo mặc định */
  }
  throw new ApiError(res.status, typeof message === "string" ? message : JSON.stringify(message));
}

export async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  return parse<T>(await fetch(url, { signal }));
}

export async function postJson<T>(url: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  return parse<T>(res);
}

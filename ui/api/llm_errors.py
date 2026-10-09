"""Đổi lỗi của nhà cung cấp LLM (OpenAI, Gemini, Groq… qua API tương thích OpenAI) thành hướng dẫn tiếng Việt.

Thông báo gốc của nhà cung cấp là một khối JSON dài; màn Hỏi đáp chỉ cần biết lỗi gì và phải sửa ở đâu trong .env.
"""

import re

import openai
from fastapi import HTTPException

RESTART = "rồi khởi động lại server (.env chỉ được đọc lúc khởi động)"
RETRY_IN = re.compile(r"retry in (?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", re.I)
RETRY_DELAY = re.compile(r"retryDelay'?\"?:\s*'?\"?(\d+)s")


def _wait(text: str) -> str | None:
    """'Please retry in 9h15m29.02s' hoặc retryDelay '33329s' → '9 giờ 15 phút'."""
    m = RETRY_IN.search(text)
    if m and any(m.groups()):
        seconds = int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + float(m.group(3) or 0)
    else:
        m = RETRY_DELAY.search(text)
        if not m:
            return None
        seconds = int(m.group(1))
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours} giờ {minutes} phút"
    return f"{minutes} phút" if minutes else f"{secs} giây"


def explain(e: Exception, model: str) -> HTTPException:
    """Lỗi khi gọi LLM → HTTPException có thông báo dễ hiểu (429 khi hết hạn mức, còn lại 502)."""
    status = getattr(e, "status_code", None)
    text = str(e)
    if status == 429 or "RESOURCE_EXHAUSTED" in text or "insufficient_quota" in text:
        wait = _wait(text)
        return HTTPException(
            status_code=429,
            detail=(
                f"LLM “{model}” đã hết hạn mức (HTTP 429)"
                + (f", nhà cung cấp báo thử lại sau {wait}" if wait else "")
                + ". Mỗi câu hỏi tốn 2 request (thêm 1 khi phải sửa SPARQL). Đổi OPENAI_MODEL hoặc key trong .env "
                + RESTART
                + "; trong lúc chờ, câu hỏi mẫu vẫn chạy bằng SPARQL viết sẵn và trang SPARQL không cần LLM."
            ),
        )
    if status == 404 or "model_not_found" in text:
        return HTTPException(
            status_code=502,
            detail=(
                f"Model “{model}” không có ở nhà cung cấp đang cấu hình (HTTP 404). Kiểm tra OPENAI_MODEL "
                f"(ví dụ gpt-4o, gpt-4o-mini) và OPENAI_BASE_URL (bỏ trống khi dùng OpenAI) trong .env {RESTART}."
            ),
        )
    if status in (401, 403):
        return HTTPException(
            status_code=502,
            detail=(
                f"API key bị từ chối (HTTP {status}). OPENAI_API_KEY phải là key của đúng nhà cung cấp ở "
                f"OPENAI_BASE_URL (key OpenAI cho OpenAI, key Gemini cho Google) {RESTART}."
            ),
        )
    if isinstance(e, openai.APIConnectionError):
        return HTTPException(
            status_code=502,
            detail=f"Không kết nối được tới LLM: kiểm tra mạng và OPENAI_BASE_URL trong .env {RESTART}.",
        )
    return HTTPException(status_code=502, detail=f"Không gọi được LLM: {text[:300]}")

/**
 * Sao chép `text` vào clipboard. `navigator.clipboard` chỉ có trên HTTPS/localhost; thiếu thì chọn sẵn
 * nội dung của `el` (người dùng nhấn Ctrl+C) và thử lệnh copy cũ. Trả về true nếu đã sao chép được.
 */
export async function copyText(text: string, el?: HTMLElement | null): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* bị từ chối quyền hoặc không có clipboard: rơi xuống phương án chọn văn bản */
  }
  if (!el) return false;
  const range = document.createRange();
  range.selectNodeContents(el);
  const sel = window.getSelection();
  sel?.removeAllRanges();
  sel?.addRange(range);
  try {
    return document.execCommand("copy");
  } catch {
    return false;
  }
}

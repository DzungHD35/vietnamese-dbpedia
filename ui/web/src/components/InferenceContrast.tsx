import type { AssertedInfo } from "../api/types";
import { formatNumber } from "../utils/format";

/** "Có suy luận: 39 dòng · Chỉ khai báo: 0 dòng" kèm một câu giải thích: bằng chứng suy luận có ích. */
export function InferenceContrast({ withInference, asserted }: { withInference: number; asserted: AssertedInfo }) {
  const only = asserted.rows;
  let note: string;
  if (asserted.status === "loading") note = "Đang nạp graph chỉ khai báo để so sánh…";
  else if (only === null) note = asserted.error ? `Không so sánh được: ${asserted.error}` : "Không so sánh được.";
  else if (only === 0 && withInference > 0)
    note = "Không triple khai báo nào trả lời được câu hỏi này: toàn bộ kết quả đến từ bộ suy luận OWL 2 RL.";
  else if (only < withInference)
    note = `Bộ suy luận OWL 2 RL bổ sung thêm ${formatNumber(withInference - only)} dòng so với dữ liệu khai báo.`;
  else note = "Câu hỏi này chỉ cần triple khai báo: suy luận không thay đổi kết quả.";
  return (
    <div className="contrast">
      <div className="contrast-num contrast-inferred">
        <b>{formatNumber(withInference)}</b>
        <span>dòng · có suy luận</span>
      </div>
      <div className="contrast-num">
        <b>{only === null ? "…" : formatNumber(only)}</b>
        <span>dòng · chỉ khai báo</span>
      </div>
      <p className="contrast-note small">{note}</p>
    </div>
  );
}

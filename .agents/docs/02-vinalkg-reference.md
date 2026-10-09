# VinaLKG Explorer — reference (chỉ để lấy cảm hứng)

Vị trí: `~/projects/personal/vn-legal-graph/web` (React 19 + zustand; vis-network, Cytoscape+ELK, Sigma+FA2).
Do agent pipeline dựng, chưa review chặt → học ý tưởng, KHÔNG port code.

## Bố cục
Top bar (search, Ngày T, chọn view, undo/share/clear/theme) + 3 cột: Chat 330px | Canvas | Inspector 340px.
5 view: Mạng lưới (vis), Thứ bậc (vis hierarchical), Cấu trúc (Cytoscape+ELK), Dòng thời gian (SVG), Tổng quan (Sigma WebGL).

## Ý tưởng đáng học
- Canvas do người dùng tự dựng: menu mở rộng liệt kê quan hệ + số lượng; quá nhiều → checklist chọn.
- Chat stream SSE; bằng chứng được merge lên canvas (glow), chip `[E1]` bấm để focus node + trích dẫn.
- Panel minh bạch SPARQL (log mọi truy vấn UI đã chạy).
- Mã hóa thị giác: viền node = trạng thái, màu cạnh = loại quan hệ, nét đứt = suy luận; legend.
- Điều khiển thời gian "Ngày T" có vạch mốc + chip "Về hôm nay".
- Tìm đường giữa 2 node (≤4 bước), highlight đường đi.
- URL share mã hóa canvas.

## Không mang sang
- 3 thư viện graph + ELK + FA2 cho canvas vài trăm nút; khái niệm "tier" làm 2 lần.
- Overview tích hợp nửa vời; path mode hỏng ở timeline/overview.
- Undo một phần (glow bằng chứng sót lại); markdown hiện thô `**`.
- 2 cột cố định 670px → laptop chật; chat mặc định mở.
- Thiết kế cho khám phá tự do, không cho trình bày theo kịch bản.

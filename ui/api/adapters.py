"""Nơi DUY NHẤT gọi hàm/thuộc tính private của vidbpedia (chỉ đọc).

Team đổi `ResourceView`, `SparqlBasedKGRAG`… thì chỉ phải sửa file này. Mọi hàm trả dữ liệu thuần
(list, dict, set), không trả HTML.
"""

from vidbpedia.web.resource_page import ResourceView


def neighbors(view, iri):
    """→ (đi ra, đi vào); mỗi phần tử là (IRI, [thuộc tính]) theo thứ tự LINK_PROPS."""
    return view._neighbors(iri)


def round_robin(items, n):
    """Lấy n phần tử của `neighbors`, xoay vòng giữa các thuộc tính để quan hệ nào cũng có mặt."""
    return ResourceView._round_robin(items, n)


def prop_key(view, prop):
    """Khoá sắp xếp thuộc tính như trang tài nguyên của team: rdf:type, nhãn… trước, rồi vio:, dbo:, khác, vip:."""
    return view._prop_key(prop)

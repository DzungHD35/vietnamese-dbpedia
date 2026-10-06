"""Unit test cho bộ parse infobox và hàm tạo IRI (không gọi mạng)."""

from vidbpedia.crawl.infobox import (
    external_links_section,
    find_infobox,
    float_vi,
    height_m,
    int_vi,
    is_loan,
    links,
    parse_date,
    raw_property_name,
    render,
    year_range,
)
from vidbpedia.crawl.iri import category_iri, dbr_iri, resource_iri, wd_iri

PLAYER = """{{Thông tin tiểu sử bóng đá
| name = Nguyễn Văn A
| birth_date = {{Ngày sinh và tuổi|1997|4|12}}
| birth_place = [[Đông Anh]], [[Hà Nội]], [[Việt Nam]]
| height = {{height|m=1,68}}
| position = [[Tiền vệ (bóng đá)#Tiền vệ tấn công|Tiền vệ tấn công]]
| currentclub = [[Câu lạc bộ bóng đá Hà Nội|Hà Nội]]
| years1 = 2015–2019 | clubs1 = [[Câu lạc bộ bóng đá Hà Nội|Hà Nội]] | caps1 = 102 | goals1 = 21
| years2 = 2022– | clubs2 = → [[Pau FC]] (mượn) | caps2 = 7 | goals2 = 0
| nationalyears1 = 2016– | nationalteam1 = [[Đội tuyển bóng đá quốc gia Việt Nam|Việt Nam]]<ref>VFF</ref>
}}
'''Nguyễn Văn A''' là cầu thủ.
== Liên kết ngoài ==
* {{Official website|https://example.vn}}
* [https://vff.org.vn/a Hồ sơ trên VFF]
"""


def test_find_infobox_nested_templates():
    name, params = find_infobox(PLAYER, ["Thông tin tiểu sử bóng đá"])
    assert name == "Thông tin tiểu sử bóng đá"
    assert parse_date(render(params["birth_date"])) == ("1997-04-12", "date")
    assert height_m(render(params["height"])) == 1.68
    assert links(params["birth_place"]) == ["Đông Anh", "Hà Nội", "Việt Nam"]
    assert links(params["position"]) == ["Tiền vệ (bóng đá)"]  # bỏ #anchor
    assert render(params["nationalteam1"]) == "Việt Nam"  # bỏ <ref>


def test_fallback_to_any_infobox():
    name, params = find_infobox("{{Hộp thông tin địa điểm|capacity=22.500}}", aliases=[])
    assert name == "Hộp thông tin địa điểm" and int_vi(params["capacity"]) == 22500


def test_loans_and_year_ranges():
    _, p = find_infobox(PLAYER, [])
    assert is_loan(p["clubs2"]) and not is_loan(p["clubs1"])
    assert year_range(p["years1"]) == ("2015", "2019")
    assert year_range(p["years2"]) == ("2022", None)
    assert year_range("2018") == ("2018", "2018")


def test_vietnamese_numbers_and_dates():
    assert int_vi("39.220 sinh viên") == 39220
    assert int_vi("khoảng 40,192 chỗ") == 40192
    assert float_vi("16.361,2 km²") == 16361.2
    assert float_vi("3,358.6") == 3358.6
    assert parse_date("ngày 6 tháng 3 năm 1956") == ("1956-03-06", "date")
    assert parse_date("21/1/1995") == ("1995-01-21", "date")
    assert parse_date("tháng 9 năm 1966") == ("1966-09", "gYearMonth")
    assert parse_date("Thành lập năm 1966") == ("1966", "gYear")
    assert parse_date(render("{{ngày thành lập và tuổi|1966|10|28}}")) == ("1966-10-28", "date")
    assert parse_date(render("{{ngày thành lập và tuổi|2002|07|}}")) == ("2002-07", "gYearMonth")
    assert parse_date(render("{{Năm bắt đầu và tuổi|1949}}")) == ("1949", "gYear")


def test_lists_and_external_links():
    assert render("{{ubl|Hà Nội|[[Đà Nẵng]]}}") == "Hà Nội; Đà Nẵng"
    assert render("Đội bóng Đất Mỏ (<ref>VFF</ref>)") == "Đội bóng Đất Mỏ"  # ngoặc rỗng
    assert set(external_links_section(PLAYER)) == {"https://vff.org.vn/a", "https://example.vn"}


def test_iri_rules():
    assert str(resource_iri("Hà Nội")) == "http://vi.dbpedia.org/resource/Hà_Nội"
    assert str(resource_iri("hoàng Anh Gia Lai")) == "http://vi.dbpedia.org/resource/Hoàng_Anh_Gia_Lai"
    assert str(resource_iri("A?B")) == "http://vi.dbpedia.org/resource/A%3FB"
    assert (
        str(dbr_iri("Đặng Văn Lâm")) == "http://dbpedia.org/resource/Đặng_Văn_Lâm"
    )  # Unicode, không percent-encode
    assert str(category_iri("Thể loại:Cầu thủ bóng đá Việt Nam")).endswith(
        "Thể_loại:Cầu_thủ_bóng_đá_Việt_Nam"
    )
    assert wd_iri("http://www.wikidata.org/entity/Q881") == wd_iri("Q881")
    assert raw_property_name("ngày thành lập") == "ngàyThànhLập"
    assert raw_property_name("2nd name") == "_2ndName"

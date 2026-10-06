"""Trích infobox từ wikitext và chuyển giá trị sang kiểu dữ liệu (số kiểu Việt, ngày tháng, năm…)."""

import re
import unicodedata

import mwparserfromhell as mwp
from mwparserfromhell.nodes import Comment, ExternalLink, HTMLEntity, Tag, Template, Text, Wikilink

INFOBOX_RE = re.compile(r"^(infobox|thông tin|hộp thông tin)\b", re.I)
NON_ARTICLE_NS = re.compile(
    r"^(tập tin|file|hình|image|thể loại|category|bản mẫu|template|wikipedia|wp|wikt|commons|d|en|:?[a-z]{2,3}):",
    re.I,
)


def norm_name(name):
    """Tên template/trang để so khớp: bỏ tiền tố, '_' → ' ', gộp khoảng trắng, chữ thường."""
    s = unicodedata.normalize("NFC", str(name)).strip()
    s = re.sub(r"^(bản mẫu|template)\s*:\s*", "", s, flags=re.I)
    s = " ".join(s.replace("_", " ").split())
    return s.casefold()


def find_infobox(wikitext, aliases=()):
    """(tên template, {khoá: wikitext}) của infobox cấp ngoài cùng, hoặc None.

    Ưu tiên template có tên trong `aliases`; nếu không có thì lấy template đầu tiên tên
    "Infobox …", "Thông tin …" hoặc "Hộp thông tin …".
    """
    if not wikitext:
        return None
    code = mwp.parse(wikitext)
    aliases = {norm_name(a) for a in aliases}
    fallback = None
    for t in code.filter_templates(recursive=False):
        name = norm_name(t.name)
        if name in aliases:
            return str(t.name).strip(), _params(t)
        if fallback is None and INFOBOX_RE.match(name):
            fallback = (str(t.name).strip(), _params(t))
    return fallback


def _params(template):
    out = {}
    for p in template.params:
        key = " ".join(str(p.name).split())
        val = str(p.value).strip()
        if key and val:
            out[key] = val
    return out


DATE_TEMPLATES = {
    "birth date and age",
    "birth date",
    "ngày sinh và tuổi",
    "ngày sinh",
    "start date",
    "start date and age",
    "ngày bắt đầu",
    "ngày bắt đầu và tuổi",
    "end date",
    "death date",
    "death date and age",
    "ngày mất",
    "ngày mất và tuổi",
    "date",
    "ngày",
    "bda",
    "dob",
}
WRAP_FIRST = {
    "nowrap",
    "nobr",
    "small",
    "big",
    "nowrap begin",
    "abbr",
    "lang-vi",
    "nobold",
    "ill",
    "sortname",
    "vn",
}
WRAP_SECOND = {"lang", "sort", "ngôn ngữ"}
LIST_TEMPLATES = {
    "ubl",
    "unbulleted list",
    "plainlist",
    "plain list",
    "hlist",
    "flatlist",
    "bulleted list",
    "danh sách",
}
DROP_TEMPLATES = {
    "flagicon",
    "flag icon",
    "flagicon image",
    "flag",
    "efn",
    "refn",
    "sfn",
    "cn",
    "citation needed",
    "cần dẫn nguồn",
    "fact",
    "update",
    "updated",
    "as of",
    "medaltemplates",
    "!",
    "-",
    "clear",
    "break",
}


def render(value):
    """wikitext → văn bản; các template thông dụng (ngày, chiều cao, danh sách…) được diễn giải thay vì bỏ."""
    code = value if isinstance(value, mwp.wikicode.Wikicode) else mwp.parse(str(value))
    text = _render_nodes(code.nodes)
    text = re.sub(r"\(\s*[,;]?\s*\)", "", text)  # ngoặc rỗng còn lại sau khi bỏ template/ref
    return re.sub(r"[ \t ]+", " ", text).replace(" ;", ";").strip(" ;,\n")


def _render_nodes(nodes):
    return "".join(_render_node(n) for n in nodes)


def _render_node(n):
    if isinstance(n, Text):
        return str(n.value)
    if isinstance(n, Comment):
        return ""
    if isinstance(n, HTMLEntity):
        return n.normalize()
    if isinstance(n, Wikilink):
        if NON_ARTICLE_NS.match(str(n.title).strip()):
            return ""
        return _render_nodes((n.text or n.title).nodes)
    if isinstance(n, ExternalLink):
        return _render_nodes(n.title.nodes) if n.title else str(n.url)
    if isinstance(n, Tag):
        tag = str(n.tag).lower()
        if tag in ("ref", "references", "gallery"):
            return ""
        if tag == "br":
            return "; "
        return _render_nodes(n.contents.nodes) if n.contents else ""
    if isinstance(n, Template):
        return _render_template(n)
    return str(n)


def _pos(t, i):
    """Tham số vị trí thứ i (từ 1), đã diễn giải."""
    for p in t.params:
        if not p.showkey and str(p.name).strip() == str(i):
            return render(p.value)
    return ""


def _named(t, *keys):
    for k in keys:
        if t.has(k):
            return render(t.get(k).value)
    return ""


def _render_template(t):
    name = norm_name(t.name)
    if name in DROP_TEMPLATES or name.startswith(("cite", "chú thích", "citation")):
        return ""
    # viwiki có nhiều biến thể: "ngày thành lập và tuổi", "Năm bắt đầu và tuổi"…
    if name in DATE_TEMPLATES or re.match(r"^(ngày|năm)\b", name) or "date" in name:
        y, m, d = _pos(t, 1), _pos(t, 2), _pos(t, 3)
        if y.isdigit() and m.isdigit() and d.isdigit():
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
        if y.isdigit() and m.isdigit():
            return f"{int(y):04d}-{int(m):02d}"
        return y or render(t.params[0].value) if t.params else ""
    if name in ("height", "chiều cao"):
        m = _named(t, "m", "meters")
        if m:
            return f"{m} m"
        cm = _named(t, "cm")
        if cm:
            return f"{cm} cm"
        return ""
    if name in ("convert", "cvt", "đổi"):
        return f"{_pos(t, 1)} {_pos(t, 2)}".strip()
    if name in ("url", "official website", "trang web chính thức", "official url", "website"):
        return _pos(t, 1) or _named(t, "url")
    if name in LIST_TEMPLATES:
        items = [render(p.value) for p in t.params if not p.showkey]
        return "; ".join(i for i in items if i)
    if name in WRAP_FIRST:
        return _pos(t, 1)
    if name in WRAP_SECOND:
        return _pos(t, 2) or _pos(t, 1)
    return ""


def links(value):
    """Tiêu đề bài viết được link trong giá trị (bỏ File, Thể loại, liên wiki và #anchor)."""
    out = []
    for wl in mwp.parse(str(value)).filter_wikilinks(recursive=True):
        title = str(wl.title).strip()
        if not title or NON_ARTICLE_NS.match(title) or title.startswith("#"):
            continue
        title = title.split("#", 1)[0].strip()
        if title:
            out.append(title[:1].upper() + title[1:])
    return list(dict.fromkeys(out))


NUM_RE = re.compile(r"\d[\d.,  ]*")
YEAR_RE = re.compile(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)")
VI_DATE_RE = re.compile(r"(?:ngày\s*)?(\d{1,2})\s*tháng\s*(\d{1,2})\s*(?:năm|,)?\s*(\d{3,4})", re.I)
VI_MONTH_RE = re.compile(r"tháng\s*(\d{1,2})\s*(?:năm|,)?\s*(\d{3,4})", re.I)
DMY_RE = re.compile(r"(?<!\d)(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?!\d)")
ISO_RE = re.compile(r"(?<!\d)(\d{4})-(\d{2})(?:-(\d{2}))?(?!\d)")
EN_MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ],
        1,
    )
}


def _number_token(text):
    m = NUM_RE.search(text.replace(" ", " "))
    return m.group(0).strip().replace(" ", " ").rstrip(".,") if m else None


def int_vi(text):
    """'39.220' / '40,192' / '39 220' / 'khoảng 5.000 người' → int; . , hoặc khoảng trắng trước nhóm 3 chữ số là phân cách nghìn."""
    tok = _number_token(str(text))
    if not tok:
        return None
    first = re.match(r"\d{1,3}(?:[., ]\d{3})+(?![\d])|\d+", tok)
    if not first:
        return None
    return int(re.sub(r"[., ]", "", first.group(0)))


def float_vi(text):
    """'16.361,2 km²' (kiểu Việt) / '3,358.6' (kiểu Anh) / '1,72' → float."""
    tok = _number_token(str(text))
    if not tok:
        return None
    tok = tok.replace(" ", "")
    seps = [c for c in tok if c in ".,"]
    if not seps:
        return float(tok)
    last = max(tok.rfind("."), tok.rfind(","))
    decimals = len(tok) - last - 1
    if len(seps) == 1 and decimals == 3:  # "40,192" hoặc "5.000": phân cách nghìn
        return float(tok.replace(".", "").replace(",", ""))
    integer, frac = tok[:last], tok[last + 1 :]
    return float(re.sub(r"[.,]", "", integer) + "." + frac)


def parse_date(text):
    """→ (giá trị, 'date' | 'gYearMonth' | 'gYear') hoặc None."""
    s = str(text)
    m = ISO_RE.search(s)
    if m and m.group(3):
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", "date"
    m = VI_DATE_RE.search(s)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}", "date"
    m = DMY_RE.search(s)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}", "date"
    for name, num in EN_MONTHS.items():
        em = re.search(rf"(\d{{1,2}})?\s*{name}\s*(\d{{1,2}})?,?\s*(\d{{4}})", s, re.I)
        if em:
            day = em.group(1) or em.group(2)
            y = int(em.group(3))
            return (
                (f"{y:04d}-{num:02d}-{int(day):02d}", "date") if day else (f"{y:04d}-{num:02d}", "gYearMonth")
            )
    if m := ISO_RE.search(s):
        return f"{m.group(1)}-{m.group(2)}", "gYearMonth"
    m = VI_MONTH_RE.search(s)
    if m:
        mo, y = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}", "gYearMonth"
    y = parse_year(s)
    return (y, "gYear") if y else None


def parse_year(text):
    m = YEAR_RE.search(str(text))
    return m.group(1) if m else None


def year_range(text):
    """'2015–2019' → ('2015','2019'); '2015–' / '2015 – nay' → ('2015', None); '2015' → ('2015','2015')."""
    s = str(text)
    years = YEAR_RE.findall(s)
    if not years:
        return None, None
    if len(years) >= 2:
        return years[0], years[1]
    open_ended = re.search(r"\d{4}\s*[–—\-−]\s*($|nay|hiện tại|present)", s.strip(), re.I)
    return years[0], (None if open_ended else years[0])


def height_m(text):
    """'1,72 m' / '1.72 m' / '172 cm' → mét."""
    s = str(text)
    v = float_vi(s)
    if v is None:
        return None
    if "cm" in s or v > 3:
        v = v / 100
    return round(v, 2) if 1.4 <= v <= 2.2 else None


def first_url(text):
    m = re.search(r"https?://[^\s\]|<>\"]+", str(text))
    if m:
        return m.group(0).rstrip(".,;)")
    m = re.search(
        r"(?<![\w@])((?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:vn|com|org|edu|net|gov)(?:\.vn)?(?:/[^\s]*)?)",
        str(text),
        re.I,
    )
    return f"http://{m.group(1)}" if m else None


LOAN_RE = re.compile(r"→|\((?:cho\s*)?mượn\)|\(loan\)|\bmượn\b", re.I)


def is_loan(raw):
    return bool(LOAN_RE.search(str(raw)))


def raw_property_name(key):
    """Khoá infobox → local name hợp lệ (NCName) cho vip:, ví dụ 'ngày thành lập' → 'ngàyThànhLập'."""
    parts = re.split(r"[\s_\-/]+", unicodedata.normalize("NFC", key.strip()))
    name = parts[0][:1].lower() + parts[0][1:] + "".join(p[:1].upper() + p[1:] for p in parts[1:] if p)
    name = re.sub(r"[^\w]", "", name)
    return name if name and not name[0].isdigit() else f"_{name}"


def external_links_section(wikitext):
    """URL trong mục 'Liên kết ngoài' / 'External links'."""
    m = re.search(r"==\s*(liên kết ngoài|external links)\s*==(.*?)(\n==[^=]|\Z)", wikitext or "", re.I | re.S)
    if not m:
        return []
    code = mwp.parse(m.group(2))
    urls = [str(e.url) for e in code.filter_external_links(recursive=True)]
    for t in code.filter_templates(recursive=True):
        if norm_name(t.name) in ("official website", "trang web chính thức", "url", "website") and t.params:
            u = first_url(render(t.params[0].value))
            if u:
                urls.append(u)
    return [u for u in dict.fromkeys(urls) if u.startswith("http")]

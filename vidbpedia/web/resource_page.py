"""Trang tài nguyên kiểu dbpedia.org/page/… cho tab Tài nguyên.

ResourceView.search tìm thực thể theo nhãn hoặc tên khác (không cần dấu). ResourceView.render dựng HTML gồm
thông tin chung, liên kết LOD, cây phân lớp, đồ thị lân cận (SVG), cây quan hệ, bảng thuộc tính và bảng
"được tham chiếu bởi".
"""

import html
import os
import unicodedata
from collections import defaultdict
from urllib.parse import quote

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import FOAF, OWL, RDF, RDFS, SKOS

from vidbpedia.crawl.iri import UNSAFE, URL_SAFE
from vidbpedia.vocab import DBO, DBR, PREFIXES, PROV, VIO, VIP, VRES, WD, WGS84

MAIN_CLASSES = [
    VIO.FootballPlayer,
    VIO.FootballClub,
    VIO.NationalFootballTeam,
    VIO.Stadium,
    VIO.University,
    VIO.Province,
    VIO.Country,
]
CLASS_NAMES = {
    "FootballPlayer": "Cầu thủ",
    "FootballClub": "CLB",
    "NationalFootballTeam": "Đội tuyển",
    "Stadium": "Sân vận động",
    "University": "Đại học",
    "Province": "Tỉnh",
    "FormerProvince": "Tỉnh cũ",
    "Country": "Quốc gia",
}
# lớp → màu nút trong đồ thị lân cận
NODE_KIND = {
    VIO.FootballPlayer: "player",
    VIO.FootballClub: "club",
    VIO.NationalFootballTeam: "club",
    VIO.Stadium: "stadium",
    VIO.University: "uni",
    VIO.Province: "prov",
    VIO.Country: "prov",
    VIO.CareerStation: "station",
}

# thuộc tính đối tượng vẽ trong đồ thị lân cận, theo thứ tự ưu tiên
LINK_PROPS = [
    VIO.birthProvince,
    VIO.birthPlace,
    VIO.currentClub,
    VIO.position,
    VIO.team,
    VIO.ground,
    VIO.tenant,
    VIO.league,
    VIO.manager,
    VIO.chairman,
    VIO.rector,
    VIO.affiliation,
    VIO.owner,
    VIO.operator,
    VIO.province,
    VIO.locatedIn,
    VIO.capital,
    VIO.region,
    VIO.successor,
    VIO.predecessor,
    VIO.playedFor,
    VIO.country,
]
# cây quan hệ chỉ đi theo triple khai báo; chiều ngược chỉ mở ở gốc
TREE_OUT = [
    VIO.careerStation,
    VIO.birthProvince,
    VIO.birthPlace,
    VIO.currentClub,
    VIO.position,
    VIO.ground,
    VIO.tenant,
    VIO.league,
    VIO.manager,
    VIO.chairman,
    VIO.rector,
    VIO.affiliation,
    VIO.owner,
    VIO.operator,
    VIO.province,
    VIO.locatedIn,
    VIO.capital,
    VIO.region,
    VIO.successor,
    VIO.predecessor,
]
TREE_IN = [
    VIO.currentClub,
    VIO.playedFor,  # suy luận, nhưng là cách tự nhiên để liệt kê cầu thủ của một CLB
    VIO.birthProvince,
    VIO.ground,
    VIO.tenant,
    VIO.province,
    VIO.affiliation,
    VIO.league,
    VIO.successor,
    VIO.capital,
    VIO.position,
]
STATION_ORDER = {VIO.YouthStation: 0, VIO.ClubStation: 1, VIO.NationalTeamStation: 2}
FIRST_PROPS = [RDF.type, RDFS.label, SKOS.altLabel, RDFS.comment, DBO.abstract]

MAX_DEPTH = 3  # gốc → đội → sân → tỉnh
TREE_BUDGET = 300  # số nút tối đa của cây quan hệ, để trang của tỉnh lớn vẫn nhẹ
MAX_CHILDREN = {1: 15, 2: 8, 3: 6}
MAX_VALUES = 40
GRAPH_SIDE = 14  # số nút tối đa mỗi bên của đồ thị lân cận


def fold(text):
    """Dạng để so khớp: bỏ dấu tiếng Việt, đ → d, chữ thường, '_' → khoảng trắng."""
    t = unicodedata.normalize("NFD", str(text).replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower().replace("_", " ")


def esc(value):
    return html.escape(str(value), quote=True)


def _cut(text, n):
    text = str(text)
    return text if len(text) <= n else text[: n - 1] + "…"


class ResourceView:
    def __init__(self, graph, inferred=None):
        self.g = graph
        self.inferred = inferred if inferred is not None else set()
        self._ns = sorted(((ns, p) for p, ns in PREFIXES.items()), key=lambda x: -len(x[0]))
        self._entries = self._build_index()

    @classmethod
    def from_files(cls, graph, graph_file):
        """Nạp kèm data/parts/inferred.nt (nếu có) để đánh dấu triple suy luận."""
        path = os.path.join(os.path.dirname(os.path.abspath(graph_file)), "parts", "inferred.nt")
        inferred = set(Graph().parse(path, format="nt")) if os.path.exists(path) else set()
        return cls(graph, inferred)

    def _build_index(self):
        main = {}
        for c in MAIN_CLASSES:
            for s in self.g.subjects(RDF.type, c):
                main.setdefault(s, c)
        entries = []
        for s in main:
            names = {str(n) for p in (RDFS.label, SKOS.altLabel) for n in self.g.objects(s, p)}
            entries += [(fold(n), s) for n in names]
        return entries

    def search(self, text, limit=20):
        """[(nhãn hiển thị, local name)]; khớp nguyên văn trước, rồi đầu chuỗi, rồi đầu từ."""
        q = " ".join(fold(text).split())
        if not q:
            return []
        best = {}
        for key, s in self._entries:
            if q not in key:
                continue
            rank = 0 if key == q else 1 if key.startswith(q) else 2 if f" {q}" in f" {key}" else 3
            best[s] = min(rank, best.get(s, 9))
        ranked = sorted(best, key=lambda s: (best[s], len(self.label(s)), self.label(s)))
        return [(self.display(s), self.local(s)) for s in ranked[:limit]]

    def resolve(self, name):
        """Local name hoặc IRI đầy đủ → URIRef có trong graph, hoặc None."""
        if not name:
            return None
        name = str(name).strip()
        if name.startswith("http://") or name.startswith("https://"):
            candidates = [name]
        else:
            name = name.replace(" ", "_")
            encoded = "".join(quote(ch, safe="") if ch in UNSAFE else ch for ch in name)
            candidates = [str(VRES) + name, str(VRES) + encoded]
        for c in candidates:
            iri = URIRef(c)
            if (iri, None, None) in self.g or (None, None, iri) in self.g:
                return iri
        return None

    def local(self, iri):
        s = str(iri)
        return s[len(VRES) :] if s.startswith(str(VRES)) else s

    def qname(self, iri):
        s = str(iri)
        for ns, p in self._ns:
            if s.startswith(ns) and len(s) > len(ns):
                return f"{p}:{s[len(ns) :]}"
        return s

    def label(self, iri):
        fallback = None
        for lbl in self.g.objects(iri, RDFS.label):
            if lbl.language == "vi":
                return str(lbl)
            if fallback is None or lbl.language == "en":
                fallback = str(lbl)
        if fallback:
            return fallback
        pref = self.g.value(iri, SKOS.prefLabel)
        if pref is not None:
            return str(pref)
        s = str(iri)
        return s[len(VRES) :].replace("_", " ") if s.startswith(str(VRES)) else self.qname(iri)

    def types(self, iri):
        return set(self.g.objects(iri, RDF.type))

    def class_name(self, iri):
        types = self.types(iri)
        if VIO.FormerProvince in types:
            return CLASS_NAMES["FormerProvince"]
        for c in MAIN_CLASSES:
            if c in types:
                return CLASS_NAMES[str(c)[len(VIO) :]]
        for t in sorted(types, key=str):
            if str(t).startswith(str(VIO)) and t != VIO.CareerStation:
                return self.label(t)
        return ""

    def display(self, iri):
        cls = self.class_name(iri)
        return f"{self.label(iri)} · {cls}" if cls else self.label(iri)

    def kind(self, iri):
        types = self.types(iri)
        for c, k in NODE_KIND.items():
            if c in types:
                return k
        return "other"

    def is_inferred(self, triple):
        return triple in self.inferred

    def href(self, iri):
        s = str(iri)
        if s.startswith(str(VRES)):
            return "/resource/" + quote(s[len(VRES) :], safe=URL_SAFE)
        if s.startswith(str(VIO)):
            return "/ontology/" + quote(s[len(VIO) :], safe=URL_SAFE)
        return s

    def link(self, iri, text=None):
        """vres:/vio: mở trên máy chủ này, IRI bên ngoài mở tab mới."""
        text = esc(text if text is not None else self.label(iri))
        s = str(iri)
        if s.startswith(str(VIP)):
            return f'<span title="{esc(s)}">{text}</span>'  # vip: chưa có trang riêng
        if s.startswith(str(VRES)) or s.startswith(str(VIO)):
            return f'<a href="{esc(self.href(iri))}" target="_self" title="{esc(s)}">{text}</a>'
        return f'<a href="{esc(s)}" target="_blank" rel="noopener" title="{esc(s)}">{text} ↗</a>'

    def render(self, iri, base_url=""):
        if iri is None or ((iri, None, None) not in self.g and (None, None, iri) not in self.g):
            return (
                '<div class="rv"><p class="rv-empty">Không tìm thấy tài nguyên này trong dataset.</p></div>'
            )
        self._budget = TREE_BUDGET
        sections = [
            (
                "rv-classes",
                "Cây phân lớp",
                self._class_tree(iri),
                "Lớp khai báo và các lớp DBpedia suy ra bằng OWL 2 RL (rdfs:subClassOf).",
            ),
            ("rv-lod", "Liên kết dữ liệu mở", self._lod_card(iri, base_url), ""),
            (
                "rv-graph",
                "Đồ thị lân cận",
                self._graph_svg(iri),
                "Mũi tên → là quan hệ đi ra, ← là quan hệ đi vào; nét đứt là quan hệ có được nhờ suy luận. "
                "Nút viền đứt là liên kết LOD ra ngoài. Bấm vào một nút để mở trang của nút đó.",
            ),
            (
                "rv-rel",
                "Cây quan hệ",
                self._relation_tree(iri),
                "Đi theo các triple khai báo, tối đa 3 bước (ví dụ cầu thủ → đội → sân nhà → tỉnh). Bấm ▸ để mở rộng.",
            ),
            ("rv-props", "Thuộc tính", self._property_table(iri), ""),
            ("rv-rev", "Được tham chiếu bởi", self._reverse_table(iri), ""),
        ]
        html_of = {anchor: self._section(anchor, title, body, note) for anchor, title, body, note in sections}
        nav = (
            '<nav class="rv-nav">'
            + "".join(
                f'<a href="#{anchor}" target="_self">{esc(title)}</a>' for anchor, title, _, _ in sections
            )
            + "</nav>"
        )
        parts = [
            self._header(iri),
            nav,
            self._summary(iri),
            f'<div class="rv-cols">{html_of["rv-classes"]}{html_of["rv-lod"]}</div>',
            html_of["rv-graph"],
            html_of["rv-rel"],
            html_of["rv-props"],
            html_of["rv-rev"],
        ]
        return '<div class="rv">' + "".join(parts) + "</div>"

    def _section(self, anchor, title, body, note=""):
        note_html = f'<p class="rv-note">{esc(note)}</p>' if note else ""
        return f'<section class="rv-sec" id="{anchor}"><h3>{esc(title)}</h3>{note_html}{body}</section>'

    def _header(self, iri):
        g = self.g
        types = sorted(
            (
                t
                for t in g.objects(iri, RDF.type)
                if str(t).startswith(str(VIO)) and not self.is_inferred((iri, RDF.type, t))
            ),
            key=str,
        )
        type_html = ", ".join(self.link(t) for t in types) or "—"
        chips = []
        page = g.value(iri, FOAF.isPrimaryTopicOf)
        if page is not None:
            chips.append(self._chip(page, "Wikipedia tiếng Việt"))
        for o in sorted(g.objects(iri, OWL.sameAs), key=str):
            if str(o).startswith(str(DBR)):
                chips.append(self._chip(o, "DBpedia tiếng Anh"))
            elif str(o).startswith(str(WD)):
                chips.append(self._chip(o, f"Wikidata {str(o)[len(WD) :]}"))
        lat, lon = g.value(iri, VIO.latitude), g.value(iri, VIO.longitude)
        if lat is not None and lon is not None:
            osm = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=12/{lat}/{lon}"
            chips.append(self._chip(osm, "Bản đồ"))
        return (
            '<header class="rv-head">'
            '<p class="rv-eyebrow">Về tài nguyên</p>'
            f'<h2 class="rv-title">{esc(self.label(iri))}</h2>'
            f'<p class="rv-type">Thực thể thuộc lớp {type_html} · đồ thị <code>http://vi.dbpedia.org</code></p>'
            f'<p class="rv-iri"><code>{esc(iri)}</code></p>'
            f'<div class="rv-chips">{"".join(chips)}</div>'
            "</header>"
        )

    def _chip(self, url, text):
        return f'<a class="rv-chip" href="{esc(url)}" target="_blank" rel="noopener">{esc(text)} ↗</a>'

    def _summary(self, iri):
        g = self.g
        abstract = next((o for o in g.objects(iri, DBO.abstract) if o.language == "vi"), None)
        abstract = abstract or g.value(iri, RDFS.comment)
        thumb = g.value(iri, DBO.thumbnail)
        if abstract is None and thumb is None:
            return ""
        text = f'<p class="rv-abstract">{esc(abstract)}</p>' if abstract is not None else "<div></div>"
        img = (
            f'<figure class="rv-img"><img src="{esc(thumb)}" alt="{esc(self.label(iri))}" loading="lazy">'
            f"<figcaption>dbo:thumbnail</figcaption></figure>"
            if thumb is not None
            else ""
        )
        return f'<div class="rv-top{" rv-noimg" if not img else ""}">{text}{img}</div>'

    def _class_tree(self, iri):
        g = self.g
        types = {
            t for t in g.objects(iri, RDF.type) if str(t).startswith(str(VIO)) or str(t).startswith(str(DBO))
        }
        if not types:
            return '<p class="rv-muted">Không có lớp vio:/dbo:.</p>'
        supers = {
            t: sorted({s for s in g.objects(t, RDFS.subClassOf) if s in types and s != t}, key=str)
            for t in types
        }

        def primary(t):
            own = [s for s in supers[t] if str(s).startswith(str(VIO))]
            return (own or supers[t] or [None])[0]

        children, roots = defaultdict(list), []
        for t in sorted(types, key=str):
            p = primary(t)
            (children[p] if p is not None else roots).append(t)

        def node(t):
            asserted = not self.is_inferred((iri, RDF.type, t))
            badge = (
                '<span class="rv-badge">khai báo</span>'
                if asserted
                else '<span class="rv-badge rv-inf">suy luận</span>'
            )
            others = [s for s in supers[t] if s != primary(t)]
            also = (
                f' <span class="rv-muted">⊑ {esc(", ".join(self.qname(s) for s in others))}</span>'
                if others
                else ""
            )
            name = self.label(t)
            name_html = f' <span class="rv-muted">{esc(name)}</span>' if name != self.qname(t) else ""
            kids = sorted(children[t], key=lambda c: (str(c).startswith(str(VIO)), str(c)))
            sub = "<ul>" + "".join(node(c) for c in kids) + "</ul>" if kids else ""
            return f"<li>{self.link(t, self.qname(t))}{name_html} {badge}{also}{sub}</li>"

        return '<ul class="rv-tree">' + "".join(node(r) for r in roots) + "</ul>"

    def _lod_card(self, iri, base_url):
        g = self.g
        rows = [f"<li><b>IRI</b> <code>{esc(iri)}</code></li>"]
        for o in sorted(g.objects(iri, OWL.sameAs), key=str):
            rows.append(f"<li><b>owl:sameAs</b> {self.link(o, self.qname(o))}</li>")
        page = g.value(iri, FOAF.isPrimaryTopicOf)
        if page is not None:
            rows.append(f"<li><b>foaf:isPrimaryTopicOf</b> {self.link(page, 'vi.wikipedia.org')}</li>")
        src = g.value(iri, PROV.wasDerivedFrom)
        if src is not None:
            rev = str(src).split("oldid=")[-1].split("&")[0]
            rows.append(f"<li><b>prov:wasDerivedFrom</b> {self.link(src, f'bản sửa đổi {rev}')}</li>")
        lat, lon = g.value(iri, WGS84.lat) or g.value(iri, VIO.latitude), g.value(iri, VIO.longitude)
        if lat is not None and lon is not None:
            rows.append(f"<li><b>toạ độ</b> {esc(lat)}, {esc(lon)}</li>")
        body = '<ul class="rv-kv">' + "".join(rows) + "</ul>"
        if str(iri).startswith(str(VRES)):
            path = self.href(iri)
            local = path[len("/resource/") :]
            fmts = " · ".join(
                f'<a href="/data/{esc(local)}.{ext}" target="_blank" rel="noopener">{name}</a>'
                for name, ext in (
                    ("Turtle", "ttl"),
                    ("N-Triples", "nt"),
                    ("JSON-LD", "jsonld"),
                    ("RDF/XML", "rdf"),
                )
            )
            body += (
                f'<p class="rv-fmt">Tải RDF: {fmts}</p>'
                '<p class="rv-note">URI dereference được trên máy chủ này (303 + content negotiation):</p>'
                f'<pre class="rv-pre">curl -L -H "Accept: text/turtle" {esc(base_url)}{esc(path)}</pre>'
            )
        return f'<div class="rv-card">{body}</div>'

    def _neighbors(self, iri):
        """(nút, [thuộc tính]) đi ra và đi vào, mỗi nút một lần, sắp theo thứ tự LINK_PROPS."""
        order = {p: i for i, p in enumerate(LINK_PROPS)}
        out, inc = {}, {}
        for p, o in self.g.predicate_objects(iri):
            if p in order and isinstance(o, URIRef) and str(o).startswith(str(VRES)) and o != iri:
                out.setdefault(o, []).append(p)
        for s, p in self.g.subject_predicates(iri):
            if (
                p in order
                and p not in (VIO.team, VIO.country)
                and str(s).startswith(str(VRES))
                and s != iri
                and s not in out
            ):
                inc.setdefault(s, []).append(p)
        for props in (*out.values(), *inc.values()):
            props.sort(key=order.get)

        def key(item):
            return (order[item[1][0]], self.label(item[0]))

        return sorted(out.items(), key=key), sorted(inc.items(), key=key)

    @staticmethod
    def _round_robin(items, n):
        """Lấy n phần tử, xoay vòng giữa các thuộc tính để quan hệ nào cũng có mặt."""
        groups = defaultdict(list)
        for item in items:
            groups[item[1][0]].append(item)
        picked, queues = [], list(groups.values())
        while len(picked) < n and any(queues):
            for q in queues:
                if q and len(picked) < n:
                    picked.append(q.pop(0))
        rank = {id(item): i for i, item in enumerate(items)}
        return sorted(picked, key=lambda item: rank[id(item)])

    def _graph_svg(self, iri):
        out, inc = self._neighbors(iri)
        page = self.g.value(iri, FOAF.isPrimaryTopicOf)
        lod = [(o, [OWL.sameAs], "lod") for o in sorted(self.g.objects(iri, OWL.sameAs), key=str)]
        if page is not None:
            lod.append((page, [FOAF.isPrimaryTopicOf], "lod"))
        cap = 2 * GRAPH_SIDE - len(lod)
        n_out = min(len(out), max(GRAPH_SIDE - len(lod), cap - len(inc)))
        n_in = min(len(inc), cap - n_out)
        outs = [(o, ps, "out") for o, ps in self._round_robin(out, n_out)]
        ins = [(s, ps, "in") for s, ps in self._round_robin(inc, n_in)]
        hidden = len(out) - len(outs) + len(inc) - len(ins)
        if not outs and not ins and not lod:
            return '<p class="rv-muted">Không có liên kết tới tài nguyên khác.</p>'
        # bên phải: LOD rồi quan hệ đi ra; bên trái: quan hệ đi vào; bên nào dư thì chuyển sang bên kia
        right, left = lod + outs, ins
        while len(right) > GRAPH_SIDE and len(left) < GRAPH_SIDE:
            left.insert(0, right.pop())
        while len(left) > GRAPH_SIDE and len(right) < GRAPH_SIDE:
            right.append(left.pop())

        width, row = 960, 40
        height = max(len(right), len(left), 1) * row + 40
        cy = height / 2
        center = _cut(self.label(iri), 34)
        cw = min(max(len(center) * 8 + 32, 150), 300)
        cx = width / 2
        parts = [
            f'<svg viewBox="0 0 {width} {height:.0f}" role="img" aria-label="Đồ thị lân cận của {esc(center)}">',
            '<defs><marker id="rv-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z"/></marker></defs>',
        ]
        nodes = []
        for side, items in ((1, right), (-1, left)):
            for i, (node, props, direction) in enumerate(items):
                y = cy - (len(items) - 1) * row / 2 + i * row
                if direction == "lod":
                    title = "vi.wikipedia.org" if node == page else self.qname(node)
                    rel = f"→ {self.qname(props[0])}"
                    inferred = False
                else:
                    title = _cut(self.label(node), 34)
                    names = ", ".join(self.qname(p).split(":", 1)[1] for p in props[:2])
                    rel = ("→ " if direction == "out" else "← ") + names
                    triples = [(iri, p, node) if direction == "out" else (node, p, iri) for p in props]
                    inferred = all(self.is_inferred(t) for t in triples)
                w = min(max(len(title) * 7 + 24, len(rel) * 6.2 + 24, 120), 300)
                x = width - 20 - w if side == 1 else 20
                ax, bx = (
                    cx + side * cw / 2,
                    (x if side == 1 else x + w),
                )  # điểm nối ở nút giữa và ở nút lân cận
                if direction == "in":
                    d = f"M{bx:.0f} {y:.0f}C{bx - side * 90:.0f} {y:.0f} {ax + side * 90:.0f} {cy:.0f} {ax:.0f} {cy:.0f}"
                else:
                    d = f"M{ax:.0f} {cy:.0f}C{ax + side * 90:.0f} {cy:.0f} {bx - side * 90:.0f} {y:.0f} {bx:.0f} {y:.0f}"
                edge = "rv-edge rv-edge-inf" if inferred else "rv-edge"
                parts.append(f'<path class="{edge}" d="{d}" marker-end="url(#rv-arr)"/>')
                kind = "lod" if direction == "lod" else self.kind(node)
                href, target = (str(node), "_blank") if direction == "lod" else (self.href(node), "_self")
                nodes.append(
                    f'<a href="{esc(href)}" target="{target}"><g class="rv-node rv-k-{kind}">'
                    f"<title>{esc(node)}</title>"
                    f'<rect x="{x:.0f}" y="{y - 15:.0f}" width="{w:.0f}" height="30" rx="5"/>'
                    f'<text class="rv-t1" x="{x + 10:.0f}" y="{y - 2:.0f}">{esc(title)}</text>'
                    f'<text class="rv-t2" x="{x + 10:.0f}" y="{y + 10:.0f}">{esc(rel)}</text></g></a>'
                )
        parts += nodes
        parts.append(
            f'<g class="rv-center"><rect x="{cx - cw / 2:.0f}" y="{cy - 18:.0f}" width="{cw:.0f}" height="36" rx="6"/>'
            f'<text x="{cx:.0f}" y="{cy + 5:.0f}" text-anchor="middle">{esc(center)}</text></g></svg>'
        )
        more = f'<p class="rv-note">Còn {hidden} liên kết khác, xem bảng bên dưới.</p>' if hidden else ""
        legend = (
            '<p class="rv-legend"><span class="rv-lg rv-lg-a"></span>khai báo '
            '<span class="rv-lg rv-lg-i"></span>suy luận '
            '<span class="rv-sw rv-k-player"></span>cầu thủ <span class="rv-sw rv-k-club"></span>CLB / đội tuyển '
            '<span class="rv-sw rv-k-stadium"></span>sân <span class="rv-sw rv-k-prov"></span>tỉnh / quốc gia '
            '<span class="rv-sw rv-k-uni"></span>đại học <span class="rv-sw rv-k-lod"></span>LOD bên ngoài</p>'
        )
        return f'<div class="rv-graph">{"".join(parts)}</div>{legend}{more}'

    def _asserted(self, triple):
        return not self.is_inferred(triple)

    def _tree_groups(self, node, path, root):
        g, groups = self.g, []
        provinces = set(g.objects(node, VIO.province))
        for p in TREE_OUT + ([VIO.country] if root else []):
            objs = {
                o
                for o in g.objects(node, p)
                if isinstance(o, URIRef) and o not in path and self._asserted((node, p, o))
            }
            if p == VIO.locatedIn:
                objs -= provinces
            if objs:
                groups.append((p, "out", self._sorted_targets(p, objs)))
        if root:
            for p in TREE_IN:
                subs = {
                    s
                    for s in g.subjects(p, node)
                    if str(s).startswith(str(VRES))
                    and s not in path
                    and (p == VIO.playedFor or self._asserted((s, p, node)))
                }
                if subs:
                    groups.append((p, "in", self._sorted_targets(p, subs)))
        return groups

    def _sorted_targets(self, prop, targets):
        if prop == VIO.careerStation:

            def key(st):
                kinds = [STATION_ORDER[t] for t in self.g.objects(st, RDF.type) if t in STATION_ORDER]
                return (min(kinds or [9]), str(self.g.value(st, VIO.startYear) or "9999"), str(st))

            return sorted(targets, key=key)
        return sorted(targets, key=self.label)

    def _station_note(self, st):
        g = self.g
        start, end = g.value(st, VIO.startYear), g.value(st, VIO.endYear)
        years = f"{start or '?'}–{end or ''}" if start or end else ""
        bits = [years] if years else []
        apps, goals = g.value(st, VIO.appearances), g.value(st, VIO.goals)
        if apps is not None:
            bits.append(f"{apps} trận" + (f", {goals} bàn" if goals is not None else ""))
        if g.value(st, VIO.onLoan) is not None and str(g.value(st, VIO.onLoan)).lower() == "true":
            bits.append("cho mượn")
        kind = next((self.label(t) for t in g.objects(st, RDF.type) if t in STATION_ORDER), "")
        if kind:
            bits.append(kind.replace("Giai đoạn ", ""))
        return " · ".join(bits)

    def _tree_node(self, target, depth, path, station=None):
        self._budget -= 1
        cls = self.class_name(target)
        head = self.link(target)
        if cls:
            head += f' <span class="rv-cls">{esc(cls)}</span>'
        if station is not None:
            head += f' <span class="rv-muted">{esc(self._station_note(station))}</span>'
        groups = []
        if depth < MAX_DEPTH and self._budget > 0:
            groups = self._tree_groups(target, path | {target}, root=False)
        if not groups:
            return f'<li><div class="rv-leaf">{head}</div></li>'
        inner = self._render_groups(groups, depth + 1, path | {target})
        return f"<li><details><summary>{head}</summary>{inner}</details></li>"

    def _render_groups(self, groups, depth, path):
        items = []
        limit = MAX_CHILDREN.get(depth, 6)
        for p, direction, targets in groups:
            shown = targets[:limit]
            children = []
            for t in shown:
                if p == VIO.careerStation:
                    team = self.g.value(t, VIO.team)
                    if team is None or team in path:
                        self._budget -= 1
                        children.append(f'<li><div class="rv-leaf">{self.link(t)}</div></li>')
                    else:
                        children.append(self._tree_node(team, depth, path | {t}, station=t))
                else:
                    children.append(self._tree_node(t, depth, path))
            if len(targets) > len(shown):
                children.append(f'<li class="rv-more">… và {len(targets) - len(shown)} khác</li>')
            arrow = "→" if direction == "out" else "←"
            name = self.label(p)
            label = f"{name} của" if direction == "in" else name
            items.append(
                f'<li class="rv-group"><span class="rv-prop">{arrow} {esc(self.qname(p))}</span> '
                f'<span class="rv-muted">{esc(label)} ({len(targets)})</span><ul>{"".join(children)}</ul></li>'
            )
        return '<ul class="rv-rtree">' + "".join(items) + "</ul>"

    def _relation_tree(self, iri):
        groups = self._tree_groups(iri, {iri}, root=True)
        if not groups:
            return '<p class="rv-muted">Không có quan hệ tới thực thể khác.</p>'
        root = f'<div class="rv-root">{esc(self.label(iri))}</div>'
        return f'<div class="rv-treebox">{root}{self._render_groups(groups, 1, {iri})}</div>'

    def _prop_key(self, p):
        if p in FIRST_PROPS:
            return (0, FIRST_PROPS.index(p), "")
        s = str(p)
        group = (
            1
            if s.startswith(str(VIO))
            else 2
            if s.startswith(str(DBO))
            else 4
            if s.startswith(str(VIP))
            else 3
        )
        return (group, 0, self.qname(p))

    def _value_html(self, s, p, o):
        if isinstance(o, Literal):
            if o.language:
                tag = f"@{o.language}"
            elif o.datatype is not None:
                tag = self.qname(o.datatype)
            else:
                tag = ""
            value = f"{esc(o)}" + (f' <span class="rv-dt">{esc(tag)}</span>' if tag else "")
        elif str(o).startswith(str(VRES)):
            value = self.link(o)
        else:
            value = self.link(o, self.qname(o))
        if self.is_inferred((s, p, o)):
            value += ' <span class="rv-badge rv-inf">suy luận</span>'
        return f"<li>{value}</li>"

    def _property_table(self, iri):
        groups = defaultdict(list)
        for p, o in self.g.predicate_objects(iri):
            groups[p].append(o)
        rows = []
        for p in sorted(groups, key=self._prop_key):
            values = sorted(
                groups[p],
                key=lambda o: (isinstance(o, Literal), self.label(o) if isinstance(o, URIRef) else str(o)),
            )
            cells = [self._value_html(iri, p, o) for o in values[:MAX_VALUES]]
            if len(values) > MAX_VALUES:
                cells.append(f'<li class="rv-more">… và {len(values) - MAX_VALUES} giá trị khác</li>')
            rows.append(
                f'<tr><td class="rv-p">{self.link(p, self.qname(p))}</td><td><ul class="rv-vals">{"".join(cells)}</ul></td></tr>'
            )
        return (
            '<div class="rv-tbl"><table><thead><tr><th>Thuộc tính</th><th>Giá trị</th></tr></thead>'
            f"<tbody>{''.join(rows)}</tbody></table></div>"
        )

    def _reverse_table(self, iri):
        groups = defaultdict(list)
        for s, p in self.g.subject_predicates(iri):
            if str(s).startswith(str(VRES)):
                groups[p].append(s)
        if not groups:
            return '<p class="rv-muted">Không có tài nguyên nào trỏ tới thực thể này.</p>'
        rows = []
        for p in sorted(groups, key=lambda p: (-len(groups[p]), self.qname(p))):
            subs = sorted(set(groups[p]), key=self.label)
            cells = []
            for s in subs[:MAX_VALUES]:
                badge = (
                    ' <span class="rv-badge rv-inf">suy luận</span>' if self.is_inferred((s, p, iri)) else ""
                )
                cells.append(f"<li>{self.link(s)}{badge}</li>")
            if len(subs) > MAX_VALUES:
                cells.append(f'<li class="rv-more">… và {len(subs) - MAX_VALUES} tài nguyên khác</li>')
            rows.append(
                f'<tr><td class="rv-p">là {self.link(p, self.qname(p))} của</td>'
                f'<td><ul class="rv-vals">{"".join(cells)}</ul></td></tr>'
            )
        return (
            '<div class="rv-tbl"><table><thead><tr><th>Quan hệ</th><th>Tài nguyên</th></tr></thead>'
            f"<tbody>{''.join(rows)}</tbody></table></div>"
        )

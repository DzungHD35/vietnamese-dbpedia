"""Tab Cây tài nguyên: mọi tài nguyên vres: xếp theo cây lớp vio:, chỉ hiện tên.

Mỗi lớp ghi số thành viên (kể cả có lớp nhờ suy luận) và liệt kê thành viên trực tiếp, tức là không thuộc
lớp con nào, giống thư mục và tệp. Thể loại, trang đổi hướng và tài nguyên chỉ có nhãn là ba nhóm riêng.
"""

from collections import defaultdict

from rdflib.namespace import OWL, RDF, RDFS, SKOS

from vidbpedia.vocab import DBO, VIO, VRES
from vidbpedia.web.resource_page import esc, fold

ROOT_ORDER = [VIO.Person, VIO.Organisation, VIO.Location, VIO.CareerStation]
MAX_LIST = 300  # số tên tối đa mỗi nút khi không lọc
MAX_LIST_FILTERED = 100


def num(n):
    """1234 → '1.234' (dấu chấm phân cách hàng nghìn như tiếng Việt)."""
    return f"{n:,}".replace(",", ".")


class ResourceTree:
    def __init__(self, view):
        self.view = view
        g = view.g
        self.classes = sorted(
            (c for c in g.subjects(RDF.type, OWL.Class) if str(c).startswith(str(VIO))), key=str
        )
        known = set(self.classes)
        self.parent, self.dbo, self.children = {}, {}, defaultdict(list)
        for c in self.classes:
            supers = sorted(g.objects(c, RDFS.subClassOf), key=str)
            own = [s for s in supers if s in known]
            self.parent[c] = own[0] if own else None
            self.dbo[c] = [s for s in supers if str(s).startswith(str(DBO))]
            if own:
                self.children[own[0]].append(c)
        self.members = {
            c: {s for s in g.subjects(RDF.type, c) if str(s).startswith(str(VRES))} for c in self.classes
        }
        self.direct = {
            c: self.members[c] - set().union(*(self.members[d] for d in self._descendants(c)))
            for c in self.classes
        }
        self.asserted = {
            c: sum(1 for s in self.members[c] if not view.is_inferred((s, RDF.type, c))) for c in self.classes
        }
        typed = {s for s in g.subjects(RDF.type, None) if str(s).startswith(str(VRES))}
        redirects = {s for s in g.subjects(DBO.wikiPageRedirects, None) if str(s).startswith(str(VRES))}
        subjects = {s for s in g.subjects() if str(s).startswith(str(VRES))}
        self.groups = [
            (
                "skos:Concept",
                "Thể loại Wikipedia",
                "dct:subject của các thực thể",
                set(g.subjects(RDF.type, SKOS.Concept)),
            ),
            ("dbo:wikiPageRedirects", "Trang đổi hướng", "tên khác, trỏ về trang chính", redirects),
            (
                "—",
                "Tài nguyên chỉ có nhãn",
                "đích của liên kết trong infobox, chưa có lớp",
                subjects - typed - redirects,
            ),
        ]
        self._labels = {}
        self.full = self.render()

    def _descendants(self, c):
        out = []
        for d in self.children[c]:
            out += [d, *self._descendants(d)]
        return out

    def label(self, s):
        if s not in self._labels:
            self._labels[s] = self.view.label(s)
        return self._labels[s]

    def render(self, query=""):
        q = " ".join(fold(query).split())
        match = (lambda s: q in fold(self.label(s))) if q else None
        roots = [c for c in ROOT_ORDER if c in self.parent and self.parent[c] is None]
        roots += [c for c in self.classes if self.parent[c] is None and c not in roots]
        nodes = [self._class_node(c, match, depth=0) for c in roots]
        groups = [self._group_node(*grp, match) for grp in self.groups]
        body = "".join(n for n in nodes + groups if n)
        if not body:
            return f'<div class="rv"><p class="rv-empty">Không có tài nguyên nào có tên chứa “{esc(query)}”.</p></div>'
        total = len({s for c in roots for s in self.members[c]}) + sum(len(grp[3]) for grp in self.groups)
        head = (
            f'<p class="ct-sum">{len(self.classes)} lớp <code>vio:</code> · {num(total)} tài nguyên <code>vres:</code>. '
            "Số bên cạnh lớp là số thực thể của lớp và các lớp con (gồm cả thực thể có lớp nhờ suy luận); "
            "danh sách tên chỉ gồm thực thể <b>trực tiếp</b> của lớp đó.</p>"
        )
        return f'<div class="rv ct">{head}<ul class="ct-tree">{body}</ul></div>'

    def _names(self, items, match):
        items = [s for s in items if match is None or match(s)]
        cap = MAX_LIST if match is None else MAX_LIST_FILTERED
        shown = sorted(items, key=self.label)[:cap]
        lis = "".join(f"<li>{self.view.link(s, self.label(s))}</li>" for s in shown)
        rest = len(items) - len(shown)
        more = f'<p class="rv-more">… và {num(rest)} tài nguyên khác (dùng ô lọc để tìm)</p>' if rest else ""
        return (f'<ul class="ct-inst">{lis}</ul>{more}' if lis else ""), len(items)

    def _class_node(self, c, match, depth):
        kids = [self._class_node(d, match, depth + 1) for d in sorted(self.children[c], key=self.label)]
        kids = [k for k in kids if k]
        names, n_direct = self._names(self.direct[c], match)
        if match is not None and not kids and not n_direct:
            return ""
        total, asserted = len(self.members[c]), self.asserted[c]
        count = f'<span class="ct-count">{num(total)}</span>'
        if asserted == 0:
            count += ' <span class="rv-badge rv-inf">suy luận</span>'
        elif asserted < total:
            count += f' <span class="rv-muted">({num(asserted)} khai báo)</span>'
        dbo = (
            ' <span class="rv-muted">⊑ '
            + ", ".join(self.view.link(d, self.view.qname(d)) for d in self.dbo[c])
            + "</span>"
            if self.dbo[c]
            else ""
        )
        summary = f"<b>{esc(self.label(c))}</b> {self.view.link(c, self.view.qname(c))}{dbo} {count}"
        direct = f'<p class="ct-direct">Thực thể trực tiếp ({num(n_direct)})</p>{names}' if names else ""
        inner = (f'<ul class="ct-tree">{"".join(kids)}</ul>' if kids else "") + direct
        is_open = " open" if depth == 0 or match is not None else ""
        return f"<li><details{is_open}><summary>{summary}</summary>{inner}</details></li>"

    def _group_node(self, qname, title, note, items, match):
        names, n = self._names(items, match)
        if match is not None and not n:
            return ""
        is_open = " open" if match is not None else ""
        summary = (
            f'<b>{esc(title)}</b> <code class="rv-muted">{esc(qname)}</code> '
            f'<span class="ct-count">{num(len(items))}</span> <span class="rv-muted">{esc(note)}</span>'
        )
        return f"<li><details{is_open}><summary>{summary}</summary>{names}</details></li>"

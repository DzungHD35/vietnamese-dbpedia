"""Dựng RDF kiểu DBpedia từ data/raw/wikidata và data/raw/wikipedia, không gọi mạng.

Ghi data/raw/rdf/<nhóm>.ttl và mapping_stats.json (khoá infobox đã/chưa ánh xạ).

    python -m vidbpedia build
"""

import json
import logging
import os
import re
from collections import Counter, defaultdict

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import FOAF, OWL, RDF, RDFS, SKOS, XSD

from vidbpedia.common import RAW_DIR, read_json, setup_logging, write_json
from vidbpedia.crawl.infobox import (
    first_url,
    float_vi,
    height_m,
    int_vi,
    is_loan,
    links,
    parse_date,
    parse_year,
    raw_property_name,
    render,
    year_range,
)
from vidbpedia.crawl.infobox_mappings import CLASS_FAMILY, MAPPINGS, PRECEDENCE
from vidbpedia.crawl.iri import category_iri, dbr_iri, norm_title, qid_of, resource_iri, wd_iri, wiki_page_url
from vidbpedia.vocab import DBO, DCTERMS, GEORSS, PROV, VIO, VIP, bind_prefixes

logger = logging.getLogger(__name__)
OUT_DIR = os.path.join(RAW_DIR, "rdf")

GROUP = {
    "FootballPlayer": "players",
    "FootballClub": "clubs",
    "NationalFootballTeam": "national_teams",
    "Stadium": "stadiums",
    "University": "universities",
    "Province": "provinces",
    "Country": "country",
}
SKIP_RAW_KEYS = re.compile(
    r"^(image|logo|hình|ảnh|caption|chú thích|image_size|imagesize|logo_size|alt|signature|module|"
    r"medaltemplates|pcupdate|ntupdate|club-update|nhiều hình|border|total_width|image_style|caption_align|perrow|"
    r"image\d+|caption\d+|bản đồ.*|map.*|pushpin.*|embedded|kit.*|pattern.*|body\d*|shorts\d*|socks\d*|leftarm\d*|rightarm\d*)$",
    re.I,
)
PREFERRED = "http://wikiba.se/ontology#PreferredRank"
CURRENT_PROVINCE_CLASSES = {"Q2824648", "Q1381899"}  # tỉnh, thành phố trực thuộc trung ương của Việt Nam


def lit(value, dtype=None, lang=None):
    return Literal(value, lang=lang) if lang else Literal(value, datatype=dtype)


def safe_iri(url):
    """URL → URIRef, hoặc None nếu có khoảng trắng hay ký tự không hợp lệ."""
    url = str(url).strip()
    if not re.match(r"^https?://[^\s<>\"{}|\\^`]+$", url):
        return None
    return URIRef(url)


def best(stmts):
    """Các statement PreferredRank nếu có, nếu không thì tất cả."""
    pref = [s for s in stmts if s.get("rank") == PREFERRED]
    return pref or stmts


def wd_time(stmt):
    """Thời gian Wikidata → (giá trị, kiểu) theo độ chính xác: 11 = date, 10 = gYearMonth, ≤ 9 = gYear."""
    v, prec = stmt["value"], int(stmt.get("prec", 11))
    sign = "-" if v.startswith("-") else ""
    body = v.lstrip("+-")
    y, m, d = body[:4], body[5:7], body[8:10]
    if prec >= 11:
        return f"{sign}{y}-{m}-{d}", "date"
    if prec == 10:
        return f"{sign}{y}-{m}", "gYearMonth"
    return f"{sign}{y}", "gYear"


def year_of(value):
    m = re.match(r"^(-?\d{4})", str(value).lstrip("+"))
    return m.group(1) if m else None


def parse_point(value):
    """WKT 'Point(lon lat)' → (lat, lon) hoặc None."""
    try:
        inner = str(value).strip()
        inner = inner[inner.index("(") + 1 : inner.rindex(")")]
        lon, lat = (float(x) for x in inner.split())
        return lat, lon
    except (ValueError, TypeError):
        return None


def short_abstract(text, limit=400):
    """Các câu đầu của abstract, tối đa `limit` ký tự (rdfs:comment như DBpedia)."""
    first_para = text.split("\n", 1)[0]
    out = ""
    for sent in re.split(r"(?<=[.!?])\s+", first_para):
        if len(out) + len(sent) > limit and out:
            break
        out = f"{out} {sent}".strip()
    return out[:limit]


class Builder:
    def __init__(self):
        wd = os.path.join(RAW_DIR, "wikidata")
        wp = os.path.join(RAW_DIR, "wikipedia")
        self.seeds = read_json(os.path.join(wd, "seeds.json"))
        self.facts = read_json(os.path.join(wd, "facts.json"))
        self.provinces_of = read_json(os.path.join(wd, "provinces_of.json"))
        self.sitelinks = read_json(os.path.join(wd, "sitelinks.json"))
        self.link_targets = read_json(os.path.join(wp, "link_targets.json"))
        self.aliases = read_json(os.path.join(wp, "template_aliases.json"))
        with open(os.path.join(wp, "pages.jsonl"), encoding="utf-8") as f:
            self.pages = {r["qid"]: r for r in map(json.loads, f)}

        self.graphs = defaultdict(Graph)
        # IRI của seed lấy theo tiêu đề của trang sau khi đi theo redirect
        self.iri_of = {}
        self.title_of = {}
        for s in self.seeds:
            title = (self.pages.get(s["qid"]) or {}).get("title") or s["vi_title"]
            self.iri_of[s["qid"]] = resource_iri(title)
            self.title_of[self.iri_of[s["qid"]]] = norm_title(title)
        self.cls_of_iri = {self.iri_of[s["qid"]]: s["cls"] for s in self.seeds}
        self.province_iris = {iri for iri, c in self.cls_of_iri.items() if c == "Province"}
        self.country_iri = next((self.iri_of[s["qid"]] for s in self.seeds if s["cls"] == "Country"), None)
        self.labels = {}  # IRI không phải seed → nhãn, để các đích liên kết cũng có tên
        self.stats = defaultdict(Counter)
        self.raw_keys = {}

    def ref_qid(self, value):
        """QID được tham chiếu → IRI vres: nếu có bài viwiki, nếu không thì wd: kèm nhãn Wikidata."""
        q = qid_of(value)
        if q in self.iri_of:
            return self.iri_of[q]
        info = self.sitelinks.get(q) or {}
        if info.get("vi"):
            iri = resource_iri(info["vi"])
            self.labels.setdefault(iri, norm_title(info["vi"]))
            return iri
        iri = wd_iri(q)
        if info.get("label"):
            self.labels.setdefault(iri, info["label"])
        return iri

    def ref_title(self, raw_title):
        """Tiêu đề trong infobox → IRI (đi theo redirect); None nếu là trang định hướng."""
        t = self.link_targets.get(raw_title)
        if t and t.get("disambiguation"):
            return None
        if t and t.get("qid") in self.iri_of:
            return self.iri_of[t["qid"]]
        title = t["title"] if t else raw_title
        iri = resource_iri(title)
        self.labels.setdefault(iri, norm_title(title))
        return iri

    def provinces_for(self, qids):
        out = []
        for q in qids:
            for p in self.provinces_of.get(qid_of(q), []):
                if p in self.iri_of:
                    out.append(self.iri_of[p])
        return list(dict.fromkeys(out))

    def build(self):
        for s in self.seeds:
            page = self.pages.get(s["qid"])
            if not page:
                continue
            g = self.graphs[GROUP[s["cls"]]]
            e = self.iri_of[s["qid"]]
            self.core(g, e, s, page)
            facts = self.facts.get(s["qid"], {})
            ib = self.mapped_infobox(s, page)
            getattr(self, f"build_{s['cls']}")(g, e, s, facts, ib, page)
            self.raw_infobox(g, e, page)
        lg = self.graphs["labels"]
        for iri, label in self.labels.items():
            if iri not in self.cls_of_iri:
                lg.add((iri, RDFS.label, Literal(label, lang="vi")))
        return self

    def core(self, g, e, s, page):
        """Các dataset cơ bản của DBpedia: nhãn, abstract, page ID, provenance, ảnh, thể loại, redirect…"""
        g.add((e, RDF.type, VIO[s["cls"]]))
        g.add((e, RDFS.label, Literal(norm_title(page["title"]), lang="vi")))
        if s.get("en_title"):
            g.add((e, RDFS.label, Literal(s["en_title"], lang="en")))
            g.add((e, OWL.sameAs, dbr_iri(s["en_title"])))
        g.add((e, OWL.sameAs, wd_iri(s["qid"])))
        extract = (page.get("extract") or "").strip()
        if extract:
            g.add((e, DBO.abstract, Literal(extract, lang="vi")))
            g.add((e, RDFS.comment, Literal(short_abstract(extract), lang="vi")))
        if page.get("pageid"):
            g.add((e, DBO.wikiPageID, lit(int(page["pageid"]), XSD.integer)))
        if page.get("revid"):
            g.add((e, DBO.wikiPageRevisionID, lit(int(page["revid"]), XSD.integer)))
        if page.get("length"):
            g.add((e, DBO.wikiPageLength, lit(int(page["length"]), XSD.nonNegativeInteger)))
        url = URIRef(wiki_page_url(page["title"]))
        g.add((e, FOAF.isPrimaryTopicOf, url))
        g.add((url, FOAF.primaryTopic, e))
        if page.get("revid"):
            g.add((e, PROV.wasDerivedFrom, URIRef(f"{url}?oldid={page['revid']}&ns=0")))
        for key, prop in (("thumbnail", DBO.thumbnail), ("image", FOAF.depiction)):
            # pageimages gắn thêm ?utm_source=… vào URL ảnh
            iri = safe_iri((page.get(key) or "").split("?", 1)[0])
            if iri:
                g.add((e, prop, iri))
        cg = self.graphs["categories"]
        for cat in page.get("categories", []):
            c = category_iri(cat)
            g.add((e, DCTERMS.subject, c))
            cg.add((c, RDF.type, SKOS.Concept))
            cg.add((c, SKOS.prefLabel, Literal(cat.split(":", 1)[-1], lang="vi")))
        rg = self.graphs["redirects"]
        for r in page.get("redirects", []):
            ri = resource_iri(r)
            if ri == e:
                continue
            rg.add((ri, DBO.wikiPageRedirects, e))
            rg.add((ri, RDFS.label, Literal(norm_title(r), lang="vi")))
            g.add((e, SKOS.altLabel, Literal(norm_title(r), lang="vi")))
        for link in page.get("external_links", [])[:30]:
            iri = safe_iri(link)
            if iri:
                g.add((e, DBO.wikiPageExternalLink, iri))
        p625 = best(self.facts.get(s["qid"], {}).get("P625", []))
        pt = parse_point(p625[0]["value"]) if p625 else None
        if not pt and page.get("coordinates"):
            pt = (page["coordinates"]["lat"], page["coordinates"]["lon"])
        if pt:
            g.add((e, VIO.latitude, lit(round(pt[0], 6), XSD.float)))
            g.add((e, VIO.longitude, lit(round(pt[1], 6), XSD.float)))
            g.add((e, GEORSS.point, Literal(f"{pt[0]} {pt[1]}")))
        if s["cls"] not in ("FootballPlayer", "Country") and self.country_iri:
            g.add((e, VIO.country, self.country_iri))

    def mapped_infobox(self, s, page):
        """{"values": {thuộc tính vio: → [giá trị đã parse]}, "params": tham số infobox gốc}."""
        family = CLASS_FAMILY[s["cls"]]
        spec = MAPPINGS[family]
        ib = page.get("infobox")
        if not ib:
            self.stats[family]["không có infobox"] += 1
            return {"values": {}, "params": {}}
        params = ib["params"]
        self.stats[family]["có infobox"] += 1
        values = defaultdict(list)
        lower = {k.casefold(): k for k in params}
        for key, (prop, parser) in spec["fields"].items():
            raw_key = lower.get(key.casefold())
            if not raw_key:
                continue
            parsed = self.parse(parser, params[raw_key])
            self.stats[family][f"{'✓' if parsed else '✗'} {key}"] += 1
            if parsed:
                values[prop].append(parsed)
        for prop, keys in spec.get("sum", {}).items():
            if prop not in values:
                nums = [int_vi(render(params[lower[k.casefold()]])) for k in keys if k.casefold() in lower]
                nums = [n for n in nums if n]
                if nums:
                    values[prop].append(sum(nums))
        mapped = {k.casefold() for k in spec["fields"]}
        for k in params:
            if k.casefold() not in mapped and not re.search(r"\d+$", k):
                self.stats[family][f"? {k}"] += 1
        return {"values": values, "params": params}

    def parse(self, parser, raw):
        text = render(raw)
        if parser == "date":
            return parse_date(text)
        if parser == "year":
            return parse_year(text)
        if parser == "int":
            return int_vi(text)
        if parser == "float":
            return float_vi(text)
        if parser == "height":
            return height_m(text)
        if parser == "text":
            return text or None
        if parser == "langtext":
            return Literal(text, lang="vi") if text else None
        if parser == "url":
            return first_url(text) or first_url(raw)
        if parser in ("links", "link_or_text"):
            iris = [i for i in (self.ref_title(t) for t in links(raw)) if i is not None]
            if iris:
                return ("iris", iris)
            return ("text", text) if parser == "link_or_text" and text else None
        raise ValueError(parser)

    def ib_iris(self, ib, prop, allow=None):
        """IRI trong infobox cho thuộc tính đối tượng; nếu IRI là seed thì lớp của nó phải thuộc `allow`."""
        out = []
        for v in ib["values"].get(prop, []):
            if isinstance(v, tuple) and v[0] == "iris":
                for iri in v[1]:
                    cls = self.cls_of_iri.get(iri)
                    if cls is None or allow is None or cls in allow:
                        out.append(iri)
        return out

    def ib_first(self, ib, prop):
        vals = ib["values"].get(prop, [])
        return vals[0] if vals else None

    def pick(self, prop, wikidata_value, infobox_value):
        if PRECEDENCE.get(prop, "wikidata") == "wikidata":
            return wikidata_value if wikidata_value is not None else infobox_value
        return infobox_value if infobox_value is not None else wikidata_value

    def raw_infobox(self, g, e, page):
        """Mọi khoá infobox thành thuộc tính thô vip:<khoá>, như dbp: của DBpedia."""
        ib = page.get("infobox")
        if not ib:
            return
        for key, raw in ib["params"].items():
            if SKIP_RAW_KEYS.match(key.strip()):
                continue
            prop = VIP[raw_property_name(key)]
            self.raw_keys[prop] = key
            iris = [i for i in (self.ref_title(t) for t in links(raw)) if i is not None]
            if iris:
                for iri in iris[:10]:
                    g.add((e, prop, iri))
                continue
            text = render(raw)
            if not text or len(text) > 500:
                continue
            if re.fullmatch(r"\d+", text):
                g.add((e, prop, lit(int(text), XSD.integer)))
            else:
                g.add((e, prop, Literal(text, lang="vi")))

    def add_founding(self, g, e, facts, ib):
        wd = best(facts.get("P571", []))
        wd_val = wd_time(wd[0]) if wd else None
        ib_val = self.ib_first(ib, "founding")
        val = self.pick("founding", wd_val, ib_val)
        if not val:
            return
        value, kind = val
        if kind == "date":
            g.add((e, VIO.foundingDate, lit(value, XSD.date)))
        year = year_of(value)
        if year:
            g.add((e, VIO.foundingYear, lit(year, XSD.gYear)))

    def add_homepage(self, g, e, facts, ib):
        wd = best(facts.get("P856", []))
        url = self.pick("homepage", wd[0]["value"] if wd else None, self.ib_first(ib, "homepage"))
        iri = safe_iri(url) if url else None
        if iri:
            g.add((e, FOAF.homepage, iri))

    def add_location(self, g, e, qids_for_province, ib, extra_located=()):
        for p in self.provinces_for(qids_for_province):
            g.add((e, VIO.province, p))
        for iri in list(extra_located) + self.ib_iris(ib, "locatedIn", allow={"Province", "Country"}):
            if iri in self.province_iris:
                g.add((e, VIO.province, iri))
            elif iri != self.country_iri:
                g.add((e, VIO.locatedIn, iri))

    def add_quantity(self, g, e, prop, dtype, wd_value, ib_value, convert=lambda x: x):
        val = self.pick(prop, wd_value, ib_value)
        if val is None:
            return None
        try:
            val = convert(val)
        except (TypeError, ValueError):
            return None
        if dtype in (XSD.nonNegativeInteger, XSD.integer):
            val = int(round(float(val)))
            if val < 0:
                return None
        g.add((e, VIO[prop], lit(val, dtype)))
        return val

    def build_FootballPlayer(self, g, e, s, facts, ib, page):
        birth = best(facts.get("P569", []))
        wd_birth = wd_time(birth[0]) if birth else None
        val = self.pick("birthDate", wd_birth, self.ib_first(ib, "birthDate"))
        if val:
            value, kind = val
            if kind == "date":
                g.add((e, VIO.birthDate, lit(value, XSD.date)))
            elif year_of(value):
                g.add((e, VIO.birthYear, lit(year_of(value), XSD.gYear)))
        death = best(facts.get("P570", []))
        if death and wd_time(death[0])[1] == "date":
            g.add((e, VIO.deathDate, lit(wd_time(death[0])[0], XSD.date)))
        # nơi sinh lấy từ P19; thiếu thì dùng link đầu tiên trong infobox
        places = [st["value"] for st in best(facts.get("P19", []))]
        if places:
            for p in places:
                g.add((e, VIO.birthPlace, self.ref_qid(p)))
            provinces = self.provinces_for(places)
        else:
            ib_places = self.ib_iris(ib, "birthPlace", allow={"Province"})
            if ib_places:
                g.add((e, VIO.birthPlace, ib_places[0]))
            provinces = [i for i in ib_places if i in self.province_iris]
        for p in provinces:
            g.add((e, VIO.birthProvince, p))
        for st in facts.get("P413", []):
            g.add((e, VIO.position, self.ref_qid(st["value"])))
        for iri in self.ib_iris(ib, "position", allow=set()):
            g.add((e, VIO.position, iri))
        h = best(facts.get("P2048", []))
        wd_height = float(h[0]["value"]) if h else None
        if wd_height is not None and not 1.4 <= wd_height <= 2.2:  # Wikidata có giá trị sai như 1,0 m
            wd_height = None
        self.add_quantity(g, e, "height", XSD.double, wd_height, self.ib_first(ib, "height"))
        num = self.ib_first(ib, "shirtNumber")
        if num is not None and 0 < num < 100:
            g.add((e, VIO.shirtNumber, lit(num, XSD.nonNegativeInteger)))
        current = self.ib_iris(ib, "currentClub", allow={"FootballClub"})
        self.career(g, e, s, facts, ib, page, current)

    def career(self, g, e, s, facts, ib, page, current):
        """vio:CareerStation từ chuỗi years{n}/clubs{n}/… của infobox; không có chặng CLB nào thì dùng P54."""
        params = ib["params"]
        lower = {k.casefold(): k for k in params}
        series = MAPPINGS["football_player"]["series"]
        stations, idx = [], 0
        for kind, keys in series.items():
            for n in range(1, 60):
                team_key = lower.get(keys["team"].format(n=n).casefold())
                if not team_key:
                    continue
                raw_team = params[team_key]
                years = render(params.get(lower.get(keys["years"].format(n=n).casefold(), ""), ""))
                apps = goals = None
                if "apps" in keys:
                    apps = int_vi(render(params.get(lower.get(keys["apps"].format(n=n).casefold(), ""), "")))
                    goals = int_vi(
                        render(params.get(lower.get(keys["goals"].format(n=n).casefold(), ""), ""))
                    )
                team_iris = [i for i in (self.ref_title(t) for t in links(raw_team)) if i is not None]
                allow = {"NationalFootballTeam"} if kind == "NationalTeamStation" else {"FootballClub"}
                team_iris = [i for i in team_iris if self.cls_of_iri.get(i, next(iter(allow))) in allow]
                start, end = year_range(years)
                idx += 1
                stations.append(
                    (kind, team_iris[:1], render(raw_team), start, end, apps, goals, is_loan(raw_team), idx)
                )
        source = "infobox"
        if not any(k == "ClubStation" for k, *_ in stations):
            source = "wikidata"
            for st in sorted(facts.get("P54", []), key=lambda x: x.get("start", "")):
                team = self.ref_qid(st["value"])
                team_cls = self.cls_of_iri.get(team)
                if team_cls not in (None, "FootballClub", "NationalFootballTeam"):
                    continue
                kind = "NationalTeamStation" if team_cls == "NationalFootballTeam" else "ClubStation"
                idx += 1
                apps = int(float(st["apps"])) if st.get("apps") else None
                goals = int(float(st["goals"])) if st.get("goals") else None
                stations.append(
                    (
                        kind,
                        [team],
                        self.labels.get(team, ""),
                        year_of(st.get("start", "")),
                        year_of(st.get("end", "")),
                        apps,
                        goals,
                        False,
                        idx,
                    )
                )
        self.stats["football_player"][f"career:{source}"] += 1
        open_club = None
        for kind, team_iris, team_text, start, end, apps, goals, loan, n in stations:
            st = URIRef(f"{e}__{n}")
            g.add((e, VIO.careerStation, st))
            g.add((st, RDF.type, VIO[kind]))
            label = (self.title_of.get(team_iris[0]) or self.labels.get(team_iris[0])) if team_iris else None
            # không có IRI đội thì dùng chữ trong infobox, bỏ ký hiệu cho mượn "→ … (mượn)"
            label = label or re.sub(r"^\s*→\s*|\s*\((cho )?mượn\)\s*$", "", team_text or "").strip()
            span = f"{start or '?'}–{end or ''}"
            g.add((st, RDFS.label, Literal(f"{norm_title(page['title'])} – {label} ({span})", lang="vi")))
            for t in team_iris:
                g.add((st, VIO.team, t))
            if start:
                g.add((st, VIO.startYear, lit(start, XSD.gYear)))
            if end:
                g.add((st, VIO.endYear, lit(end, XSD.gYear)))
            if apps is not None:
                g.add((st, VIO.appearances, lit(apps, XSD.nonNegativeInteger)))
            if goals is not None:
                g.add((st, VIO.goals, lit(goals, XSD.nonNegativeInteger)))
            if loan:
                g.add((st, VIO.onLoan, Literal(True)))
            if kind == "ClubStation" and team_iris and start and not end:
                open_club = team_iris[0]
        for club in current or ([open_club] if open_club else []):
            g.add((e, VIO.currentClub, club))

    def build_FootballClub(self, g, e, s, facts, ib, page):
        self.add_founding(g, e, facts, ib)
        self.add_homepage(g, e, facts, ib)
        grounds = [self.ref_qid(st["value"]) for st in facts.get("P115", [])]
        grounds += self.ib_iris(ib, "ground", allow={"Stadium"})
        for gr in dict.fromkeys(grounds):
            if self.cls_of_iri.get(gr, "Stadium") == "Stadium":
                g.add((e, VIO.ground, gr))
        for st in facts.get("P118", []):
            g.add((e, VIO.league, self.ref_qid(st["value"])))
        for iri in self.ib_iris(ib, "league", allow=set()):
            g.add((e, VIO.league, iri))
        self.add_people(g, e, facts, ib)
        nick = self.ib_first(ib, "nickname")
        if nick is not None:
            g.add((e, VIO.nickname, nick))
        hq = [st["value"] for st in facts.get("P159", []) + facts.get("P131", [])]
        self.add_location(g, e, hq, {"values": {}}, [self.ref_qid(q) for q in hq])

    def add_people(self, g, e, facts, ib):
        managers = [self.ref_qid(st["value"]) for st in best(facts.get("P286", []))]
        for v in ib["values"].get("manager", []):
            if v[0] == "iris":
                managers += [i for i in v[1] if self.cls_of_iri.get(i) in (None, "FootballPlayer")]
            elif v[0] == "text":
                g.add((e, VIO.managerName, Literal(v[1])))
        for m in dict.fromkeys(managers):
            g.add((e, VIO.manager, m))
        for iri in self.ib_iris(ib, "chairman", allow={"FootballPlayer"}):
            g.add((e, VIO.chairman, iri))

    def build_NationalFootballTeam(self, g, e, s, facts, ib, page):
        self.add_founding(g, e, facts, ib)
        self.add_homepage(g, e, facts, ib)
        self.add_people(g, e, facts, ib)

    def build_Stadium(self, g, e, s, facts, ib, page):
        cap = best(facts.get("P1083", []))
        self.add_quantity(
            g,
            e,
            "capacity",
            XSD.nonNegativeInteger,
            float(cap[0]["value"]) if cap else None,
            self.ib_first(ib, "capacity"),
        )
        opened = best(facts.get("P1619", []) or facts.get("P571", []))
        year = self.pick(
            "openingYear",
            year_of(wd_time(opened[0])[0]) if opened else None,
            self.ib_first(ib, "openingYear"),
        )
        if year:
            g.add((e, VIO.openingYear, lit(year, XSD.gYear)))
        tenants = [self.ref_qid(st["value"]) for st in facts.get("P466", [])]
        tenants += self.ib_iris(ib, "tenant", allow={"FootballClub", "NationalFootballTeam"})
        # ô "bên thuê" còn liệt kê cả giải đấu (ASEAN 2024…), nên chỉ giữ đội có trong dataset
        for t in dict.fromkeys(tenants):
            if self.cls_of_iri.get(t) in ("FootballClub", "NationalFootballTeam"):
                g.add((e, VIO.tenant, t))
        for pid, prop in (("P127", VIO.owner), ("P137", VIO.operator)):
            for st in facts.get(pid, []):
                g.add((e, prop, self.ref_qid(st["value"])))
        for prop in ("owner", "operator"):
            for iri in self.ib_iris(ib, prop, allow={"Province", "University", "FootballClub"}):
                g.add((e, VIO[prop], iri))
        self.add_homepage(g, e, facts, ib)
        located = [self.ref_qid(st["value"]) for st in facts.get("P131", [])]
        self.add_location(g, e, [s["qid"]], ib, located)

    def build_University(self, g, e, s, facts, ib, page):
        self.add_founding(g, e, facts, ib)
        self.add_homepage(g, e, facts, ib)
        abbr = best(facts.get("P1813", []))
        val = self.pick("abbreviation", abbr[0]["value"] if abbr else None, self.ib_first(ib, "abbreviation"))
        if val:
            g.add((e, VIO.abbreviation, Literal(str(val)[:60])))
        motto = self.ib_first(ib, "motto")
        if motto is not None:
            g.add((e, VIO.motto, motto))
        students = best(facts.get("P2196", []))
        self.add_quantity(
            g,
            e,
            "numberOfStudents",
            XSD.nonNegativeInteger,
            float(students[0]["value"]) if students else None,
            self.ib_first(ib, "numberOfStudents"),
        )
        staff = self.ib_first(ib, "academicStaffSize")
        if staff:
            g.add((e, VIO.academicStaffSize, lit(staff, XSD.nonNegativeInteger)))
        for v in ib["values"].get("rector", [])[:1]:
            if v[0] == "iris":
                for iri in v[1][:1]:
                    if self.cls_of_iri.get(iri) is None:
                        g.add((e, VIO.rector, iri))
            else:
                g.add((e, VIO.rectorName, Literal(v[1][:120])))
        en = self.ib_first(ib, "englishName")
        if en and not s.get("en_title"):
            g.add((e, RDFS.label, Literal(en[:200], lang="en")))
        elif en:
            g.add((e, SKOS.altLabel, Literal(en[:200], lang="en")))
        parents = [self.ref_qid(st["value"]) for st in facts.get("P749", [])]
        parents += self.ib_iris(ib, "affiliation", allow={"University"})
        for p in dict.fromkeys(parents):
            if p != e:
                g.add((e, VIO.affiliation, p))
        located = [self.ref_qid(st["value"]) for st in facts.get("P131", []) + facts.get("P159", [])]
        self.add_location(g, e, [s["qid"]] + [st["value"] for st in facts.get("P159", [])], ib, located)

    def add_population(self, g, e, facts):
        """Dân số mới nhất theo thời điểm P585; trả False nếu Wikidata không có."""
        pops = best(facts.get("P1082", []))
        if not pops:
            return False
        latest = max(pops, key=lambda st: st.get("pit", ""))
        g.add((e, VIO.population, lit(int(float(latest["value"])), XSD.nonNegativeInteger)))
        if latest.get("pit"):
            g.add((e, VIO.populationYear, lit(year_of(latest["pit"]), XSD.gYear)))
        return True

    def build_Province(self, g, e, s, facts, ib, page):
        if not self.add_population(g, e, facts) and self.ib_first(ib, "population"):
            g.add((e, VIO.population, lit(self.ib_first(ib, "population"), XSD.nonNegativeInteger)))
            year = self.ib_first(ib, "populationYear")
            if year:
                g.add((e, VIO.populationYear, lit(year, XSD.gYear)))
        area = best(facts.get("P2046", []))
        self.add_quantity(
            g,
            e,
            "area",
            XSD.double,
            float(area[0]["value"]) / 1e6 if area else None,
            self.ib_first(ib, "area"),
            convert=lambda x: round(float(x), 2),
        )
        dis = best(facts.get("P576", []))
        if dis:
            g.add((e, VIO.dissolutionYear, lit(year_of(wd_time(dis[0])[0]), XSD.gYear)))
        # tỉnh hiện hành: có P31 tỉnh/thành phố trực thuộc trung ương chưa hết hiệu lực (P582) và không có P576
        current = any(
            qid_of(st["value"]) in CURRENT_PROVINCE_CLASSES and not st.get("end")
            for st in facts.get("P31", [])
        )
        if dis or not current:
            g.add((e, RDF.type, VIO.FormerProvince))
        for pid, prop in (("P1366", VIO.successor), ("P1365", VIO.predecessor)):
            for st in facts.get(pid, []):
                g.add((e, prop, self.ref_qid(st["value"])))
        capitals = [self.ref_qid(st["value"]) for st in best(facts.get("P36", []))]
        capitals += self.ib_iris(ib, "capital", allow=set())
        for c in dict.fromkeys(capitals):
            g.add((e, VIO.capital, c))
        for iri in self.ib_iris(ib, "region", allow=set()):
            g.add((e, VIO.region, iri))
        code = self.ib_first(ib, "administrativeCode")
        if code:
            g.add((e, VIO.administrativeCode, Literal(str(code)[:20])))
        self.add_homepage(g, e, facts, ib)

    def build_Country(self, g, e, s, facts, ib, page):
        self.add_population(g, e, facts)
        area = best(facts.get("P2046", []))
        if area:
            g.add((e, VIO.area, lit(round(float(area[0]["value"]) / 1e6, 2), XSD.double)))
        for st in best(facts.get("P36", [])):
            g.add((e, VIO.capital, self.ref_qid(st["value"])))

    def write(self):
        os.makedirs(OUT_DIR, exist_ok=True)
        vg = self.graphs["vip_properties"]
        for prop, key in self.raw_keys.items():
            vg.add((prop, RDF.type, RDF.Property))
            vg.add((prop, RDFS.label, Literal(key, lang="vi")))
        total = 0
        for name, g in sorted(self.graphs.items()):
            bind_prefixes(g)
            g.serialize(os.path.join(OUT_DIR, f"{name}.ttl"), format="turtle", encoding="utf-8")
            total += len(g)
            logger.info("%-16s %7d triple", name, len(g))
        stats = {
            fam: dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))) for fam, c in self.stats.items()
        }
        write_json(os.path.join(OUT_DIR, "mapping_stats.json"), stats)
        logger.info("Tổng %d triple trong %s", total, OUT_DIR)


def main():
    setup_logging()
    Builder().build().write()


if __name__ == "__main__":
    main()

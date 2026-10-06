"""Chọn thực thể (seed) và lấy dữ kiện từ Wikidata.

Ghi vào data/raw/wikidata/:
  seeds.json         [{qid, cls, vi_title, en_title}]
  facts.json         {qid: {pid: [statement kèm qualifier]}}
  provinces_of.json  {qid địa điểm: [qid tỉnh]} theo P131*
  sitelinks.json     {qid: {vi, en, label}} của mọi QID được tham chiếu

    python -m vidbpedia seeds [--offline] [--refresh]
"""

import argparse
import logging
import os
from collections import Counter, defaultdict

from vidbpedia.common import RAW_DIR, setup_logging, write_json
from vidbpedia.crawl.http import Cache, wdqs_select
from vidbpedia.crawl.iri import qid_of

logger = logging.getLogger(__name__)
OUT_DIR = os.path.join(RAW_DIR, "wikidata")

EXCLUDE = """
  FILTER NOT EXISTS { ?item wdt:P31 wd:Q13406463 }   # trang danh sách Wikimedia
  FILTER NOT EXISTS { ?item wdt:P31 wd:Q4167410 }    # trang định hướng
"""

# thứ tự là độ ưu tiên khi một QID khớp nhiều lớp
SEEDS = [
    ("Country", "VALUES ?item { wd:Q881 }"),
    ("Province", "?item wdt:P31/wdt:P279* wd:Q10864048 ; wdt:P17 wd:Q881 ."),
    ("Stadium", "?item wdt:P31/wdt:P279* wd:Q483110 ; wdt:P17 wd:Q881 ."),
    ("University", "?item wdt:P31/wdt:P279* wd:Q3918 ; wdt:P17 wd:Q881 ."),
    ("NationalFootballTeam", "?item wdt:P31/wdt:P279* wd:Q6979593 ; wdt:P17 wd:Q881 ."),
    ("FootballClub", "?item wdt:P31/wdt:P279* wd:Q476028 ; wdt:P17 wd:Q881 ."),
    ("FootballPlayer", "?item wdt:P31 wd:Q5 ; wdt:P106 wd:Q937857 ; wdt:P27 wd:Q881 ."),
]

SEED_QUERY = """
SELECT DISTINCT ?item ?viTitle ?enTitle WHERE {{
  {pattern}
  {exclude}
  ?vs schema:about ?item ; schema:isPartOf <https://vi.wikipedia.org/> ; schema:name ?viTitle .
  OPTIONAL {{ ?es schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?enTitle . }}
}}"""

TIME_PROPS = {
    "FootballPlayer": ["P569", "P570"],
    "FootballClub": ["P571"],
    "NationalFootballTeam": ["P571"],
    "University": ["P571"],
    "Stadium": ["P1619", "P571"],
    "Province": ["P571", "P576"],
    "Country": [],
}
QUANTITY_PROPS = {  # psn: giá trị đã quy về đơn vị SI, ps: giá trị gốc
    "FootballPlayer": {"P2048": "psn"},
    "Stadium": {"P1083": "ps"},
    "Province": {"P1082": "ps", "P2046": "psn"},
    "University": {"P2196": "ps"},
    "Country": {"P1082": "ps", "P2046": "psn"},
}
ITEM_PROPS = {
    "FootballPlayer": ["P19", "P413", "P54", "P856"],
    "FootballClub": ["P115", "P131", "P159", "P118", "P286", "P856", "P625"],
    "NationalFootballTeam": ["P115", "P286", "P856"],
    "Stadium": ["P131", "P466", "P127", "P137", "P625", "P856"],
    "University": ["P131", "P159", "P749", "P856", "P625", "P1813"],
    "Province": ["P31", "P36", "P1366", "P1365", "P625", "P856", "P2585"],
    "Country": ["P36", "P625"],
}
QUALIFIERS = "?start ?end ?apps ?goals ?pit"


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def values_block(qids):
    return " ".join(f"wd:{q}" for q in qids)


def fetch_seeds(cache):
    rows_by_cls = {}
    for cls, pattern in SEEDS:
        rows = wdqs_select(SEED_QUERY.format(pattern=pattern, exclude=EXCLUDE), cache, f"seed {cls}")
        rows_by_cls[cls] = [r for r in rows if not r["viTitle"].startswith("Danh sách")]
    seeds, owner = {}, {}
    for cls, _ in SEEDS:
        for r in rows_by_cls[cls]:
            q = qid_of(r["item"])
            if q in seeds:
                if owner[q] != cls:
                    logger.info(
                        "QID %s (%s) khớp cả %s và %s; giữ %s", q, r["viTitle"], owner[q], cls, owner[q]
                    )
                continue
            seeds[q] = {"qid": q, "cls": cls, "vi_title": r["viTitle"], "en_title": r.get("enTitle")}
            owner[q] = cls
    return list(seeds.values())


def _rows_to_facts(rows, facts):
    for r in rows:
        stmt = {
            k: r[k]
            for k in ("value", "prec", "unit", "start", "end", "apps", "goals", "pit", "rank")
            if k in r
        }
        facts[qid_of(r["item"])][r["pid"]].append(stmt)


def fetch_facts(seeds, cache):
    by_cls = defaultdict(list)
    for s in seeds:
        by_cls[s["cls"]].append(s["qid"])
    facts = defaultdict(lambda: defaultdict(list))
    for cls, qids in by_cls.items():
        for part in chunks(sorted(qids), 300):
            vals = values_block(part)
            # giá trị "unknown value" không có nút psv: nên tự bị loại
            for pid in TIME_PROPS.get(cls, []):
                q = f"""SELECT ?item ?pid ?value ?prec ?rank WHERE {{
                  VALUES ?item {{ {vals} }} BIND("{pid}" AS ?pid)
                  ?item p:{pid} ?st . ?st wikibase:rank ?rank ; psv:{pid} [ wikibase:timeValue ?value ; wikibase:timePrecision ?prec ] .
                  FILTER(?rank != wikibase:DeprecatedRank) }}"""
                _rows_to_facts(wdqs_select(q, cache, f"time {cls} {pid}"), facts)
            for pid, mode in QUANTITY_PROPS.get(cls, {}).items():
                node = (
                    f"psn:{pid} [ wikibase:quantityAmount ?value ; wikibase:quantityUnit ?unit ]"
                    if mode == "psn"
                    else f"ps:{pid} ?value"
                )
                q = f"""SELECT ?item ?pid ?value ?unit ?pit ?rank WHERE {{
                  VALUES ?item {{ {vals} }} BIND("{pid}" AS ?pid)
                  ?item p:{pid} ?st . ?st wikibase:rank ?rank ; {node} .
                  OPTIONAL {{ ?st pq:P585 ?pit }}
                  FILTER(?rank != wikibase:DeprecatedRank) }}"""
                _rows_to_facts(wdqs_select(q, cache, f"qty {cls} {pid}"), facts)
            for pid in ITEM_PROPS.get(cls, []):
                q = f"""SELECT ?item ?pid ?value {QUALIFIERS} ?rank WHERE {{
                  VALUES ?item {{ {vals} }} BIND("{pid}" AS ?pid)
                  ?item p:{pid} ?st . ?st wikibase:rank ?rank ; ps:{pid} ?value .
                  FILTER(?rank != wikibase:DeprecatedRank)
                  FILTER(!isBlank(?value) && !STRSTARTS(STR(?value), "http://www.wikidata.org/.well-known/genid/"))
                  OPTIONAL {{ ?st pq:P580 ?start }} OPTIONAL {{ ?st pq:P582 ?end }}
                  OPTIONAL {{ ?st pq:P1350 ?apps }} OPTIONAL {{ ?st pq:P1351 ?goals }} OPTIONAL {{ ?st pq:P585 ?pit }} }}"""
                _rows_to_facts(wdqs_select(q, cache, f"item {cls} {pid}"), facts)
    return {q: dict(p) for q, p in facts.items()}


def referenced_qids(facts):
    refs = set()
    for props in facts.values():
        for stmts in props.values():
            for st in stmts:
                v = st.get("value", "")
                if v.startswith("http://www.wikidata.org/entity/Q"):
                    refs.add(qid_of(v))
    return refs


def fetch_provinces_of(places, province_qids, cache):
    """Một nơi có thể thuộc cả tỉnh cũ lẫn tỉnh mới."""
    out = defaultdict(set)
    provs = values_block(sorted(province_qids))
    for part in chunks(sorted(places), 200):
        q = f"""SELECT ?place ?prov WHERE {{
          VALUES ?place {{ {values_block(part)} }} VALUES ?prov {{ {provs} }}
          ?place wdt:P131* ?prov . }}"""
        for r in wdqs_select(q, cache, f"P131* ({len(part)} nơi)"):
            out[qid_of(r["place"])].add(qid_of(r["prov"]))
    return {k: sorted(v) for k, v in out.items()}


def fetch_sitelinks(qids, cache):
    out = {}
    for part in chunks(sorted(qids), 300):
        q = f"""SELECT ?item ?vi ?en ?label WHERE {{
          VALUES ?item {{ {values_block(part)} }}
          OPTIONAL {{ ?vs schema:about ?item ; schema:isPartOf <https://vi.wikipedia.org/> ; schema:name ?vi . }}
          OPTIONAL {{ ?es schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?en . }}
          OPTIONAL {{ ?item rdfs:label ?label FILTER(lang(?label) = "vi") }} }}"""
        for r in wdqs_select(q, cache, f"sitelinks ({len(part)})"):
            out[qid_of(r["item"])] = {k: r.get(k) for k in ("vi", "en", "label")}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true", help="chỉ đọc cache, không gọi mạng")
    ap.add_argument("--refresh", action="store_true", help="bỏ qua cache, gọi lại toàn bộ")
    args = ap.parse_args()
    setup_logging()
    cache = Cache(refresh=args.refresh, offline=args.offline)

    seeds = fetch_seeds(cache)
    counts = Counter(s["cls"] for s in seeds)
    en = Counter(s["cls"] for s in seeds if s["en_title"])
    for cls, _ in SEEDS:
        logger.info(
            "seed %-21s %4d thực thể, %3d%% có enwiki", cls, counts[cls], 100 * en[cls] // max(counts[cls], 1)
        )

    facts = fetch_facts(seeds, cache)
    refs = referenced_qids(facts)
    province_qids = {s["qid"] for s in seeds if s["cls"] == "Province"}
    place_props = {"P19", "P131", "P159", "P115"}
    places = {
        qid_of(st["value"])
        for props in facts.values()
        for pid, stmts in props.items()
        if pid in place_props
        for st in stmts
        if st.get("value", "").startswith("http://www.wikidata.org/entity/Q")
    }
    places |= {s["qid"] for s in seeds if s["cls"] in ("Stadium", "University", "FootballClub")}
    provinces_of = fetch_provinces_of(places, province_qids, cache)
    sitelinks = fetch_sitelinks(refs | {s["qid"] for s in seeds}, cache)

    write_json(os.path.join(OUT_DIR, "seeds.json"), seeds)
    write_json(os.path.join(OUT_DIR, "facts.json"), facts)
    write_json(os.path.join(OUT_DIR, "provinces_of.json"), provinces_of)
    write_json(os.path.join(OUT_DIR, "sitelinks.json"), sitelinks)
    logger.info(
        "Xong: %d seed, %d thực thể có dữ kiện, %d QID tham chiếu, %d nơi quy được về tỉnh",
        len(seeds),
        len(facts),
        len(refs),
        len(provinces_of),
    )


if __name__ == "__main__":
    main()

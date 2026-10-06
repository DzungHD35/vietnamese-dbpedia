"""Lấy nội dung bài viết viwiki cho mọi seed.

Ghi vào data/raw/wikipedia/:
  pages.jsonl            mỗi dòng một thực thể: meta trang, abstract, ảnh, toạ độ, thể loại, redirect,
                         tham số infobox (wikitext gốc), link ngoài
  link_targets.json      tiêu đề được link trong infobox → {title, qid, disambiguation}
  template_aliases.json  họ template → mọi tên của template (kể cả redirect)

    python -m vidbpedia enrich [--offline] [--refresh]
"""

import argparse
import json
import logging
import os
from collections import Counter

from vidbpedia.common import RAW_DIR, read_json, setup_logging, write_json
from vidbpedia.crawl.http import Cache, query_pages
from vidbpedia.crawl.infobox import external_links_section, find_infobox, links
from vidbpedia.crawl.infobox_mappings import CLASS_FAMILY, MAPPINGS

logger = logging.getLogger(__name__)
OUT_DIR = os.path.join(RAW_DIR, "wikipedia")

KINDS = {
    "meta": (
        {
            "prop": "info|pageprops|pageimages|coordinates",
            "ppprop": "wikibase_item|disambiguation",
            "piprop": "original|thumbnail|name",
            "pithumbsize": 300,
            "pilicense": "any",
            "redirects": 1,
        },
        50,
    ),
    "extract": ({"prop": "extracts", "exintro": 1, "explaintext": 1, "exlimit": 20, "redirects": 1}, 20),
    "categories": ({"prop": "categories", "clshow": "!hidden", "cllimit": "max", "redirects": 1}, 50),
    "redirects": ({"prop": "redirects", "rdnamespace": 0, "rdlimit": "max", "redirects": 1}, 50),
    "wikitext": ({"prop": "revisions", "rvprop": "ids|content", "rvslots": "main", "redirects": 1}, 10),
}


def template_aliases(cache):
    """Tên chuẩn của mỗi template infobox cùng các trang đổi hướng tới nó (namespace Bản mẫu)."""
    out = {}
    for family, spec in MAPPINGS.items():
        names = set(spec["templates"])
        titles = [f"Bản mẫu:{t}" for t in spec["templates"]]
        pages = query_pages(
            "tpl-redirects",
            titles,
            {"prop": "redirects", "rdnamespace": 10, "rdlimit": "max", "redirects": 1},
            cache,
        )
        for page in pages.values():
            if not page:
                continue
            names.add(page["title"].split(":", 1)[-1])
            names.update(r["title"].split(":", 1)[-1] for r in page.get("redirects", []))
        out[family] = sorted(names)
    return out


def wikitext_of(page):
    try:
        return page["revisions"][0]["slots"]["main"]["content"]
    except (KeyError, IndexError, TypeError):
        return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true", help="chỉ đọc cache, không gọi mạng")
    ap.add_argument("--refresh", action="store_true", help="bỏ qua cache, gọi lại toàn bộ")
    args = ap.parse_args()
    setup_logging()
    cache = Cache(refresh=args.refresh, offline=args.offline)

    seeds = read_json(os.path.join(RAW_DIR, "wikidata", "seeds.json"))
    titles = [s["vi_title"] for s in seeds]
    fetched = {
        kind: query_pages(kind, titles, params, cache, batch=batch) for kind, (params, batch) in KINDS.items()
    }
    aliases = template_aliases(cache)

    records, link_titles, stats = [], set(), Counter()
    for s in seeds:
        t = s["vi_title"]
        meta = fetched["meta"].get(t)
        if not meta:
            logger.warning("Không tìm thấy trang: %s (%s)", t, s["qid"])
            stats["missing"] += 1
            continue
        if meta.get("pageprops", {}).get("wikibase_item") not in (None, s["qid"]):
            logger.warning("QID lệch: %s trang=%s seed=%s", t, meta["pageprops"]["wikibase_item"], s["qid"])
        wt = wikitext_of(fetched["wikitext"].get(t))
        family = CLASS_FAMILY.get(s["cls"])
        ib = find_infobox(wt, aliases.get(family, [])) if wt else None
        if ib:
            stats[f"infobox:{s['cls']}"] += 1
            for value in ib[1].values():
                link_titles.update(links(value))
        coords = (meta.get("coordinates") or [{}])[0]
        rev = (fetched["wikitext"].get(t) or {}).get("revisions", [{}])[0]
        records.append(
            {
                **s,
                "title": meta["title"],
                "pageid": meta.get("pageid"),
                "revid": rev.get("revid") or meta.get("lastrevid"),
                "length": meta.get("length"),
                "touched": meta.get("touched"),
                "image": (meta.get("original") or {}).get("source"),
                "thumbnail": (meta.get("thumbnail") or {}).get("source"),
                "coordinates": {"lat": coords["lat"], "lon": coords["lon"]} if "lat" in coords else None,
                "extract": (fetched["extract"].get(t) or {}).get("extract", ""),
                "categories": [
                    c["title"] for c in (fetched["categories"].get(t) or {}).get("categories", [])
                ],
                "redirects": [r["title"] for r in (fetched["redirects"].get(t) or {}).get("redirects", [])],
                "infobox": {"template": ib[0], "params": ib[1]} if ib else None,
                "external_links": external_links_section(wt),
            }
        )
        stats[s["cls"]] += 1

    targets = query_pages(
        "linktarget",
        sorted(link_titles),
        {"prop": "pageprops", "ppprop": "wikibase_item|disambiguation", "redirects": 1},
        cache,
    )
    link_targets = {
        raw: (
            {
                "title": p["title"],
                "qid": p.get("pageprops", {}).get("wikibase_item"),
                "disambiguation": "disambiguation" in p.get("pageprops", {}),
            }
            if p
            else None
        )
        for raw, p in targets.items()
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "pages.jsonl"), "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    write_json(os.path.join(OUT_DIR, "link_targets.json"), link_targets)
    write_json(os.path.join(OUT_DIR, "template_aliases.json"), aliases)

    for cls in sorted({s["cls"] for s in seeds}):
        rows = [r for r in records if r["cls"] == cls]
        have = {
            key: sum(1 for r in rows if r.get(key))
            for key in ("extract", "image", "coordinates", "categories", "redirects")
        }
        logger.info(
            "%-21s %4d trang | infobox %3d | abstract %3d | ảnh %3d | toạ độ %3d | thể loại %3d | redirect %3d",
            cls,
            stats[cls],
            stats[f"infobox:{cls}"],
            *have.values(),
        )
    logger.info(
        "Link trong infobox: %d tiêu đề, %d tồn tại, %d trang định hướng",
        len(link_targets),
        sum(1 for v in link_targets.values() if v),
        sum(1 for v in link_targets.values() if v and v["disambiguation"]),
    )


if __name__ == "__main__":
    main()

"""Tạo IRI theo quy ước DBpedia: một hàm cho mọi nơi để mỗi thực thể chỉ có một IRI."""

import unicodedata
from urllib.parse import quote

from rdflib import URIRef

from vidbpedia.vocab import DBR, VRES, WD

UNSAFE = set('"%<>\\^`{|}?#[]')
URL_SAFE = ":/()_,-.~!*'"


def norm_title(title):
    """Chuẩn hoá như MediaWiki: NFC, gộp khoảng trắng, viết hoa ký tự đầu."""
    t = unicodedata.normalize("NFC", str(title)).replace("_", " ").strip()
    t = " ".join(t.split())
    return t[:1].upper() + t[1:] if t else t


def iri_local(title):
    """Khoảng trắng → '_', giữ Unicode, chỉ mã hoá ký tự không được phép trong IRI."""
    out = []
    for ch in norm_title(title).replace(" ", "_"):
        if ch in UNSAFE or ord(ch) < 0x21 or unicodedata.category(ch).startswith("Z"):
            out.append(quote(ch, safe=""))
        else:
            out.append(ch)
    return "".join(out)


def resource_iri(title):
    return URIRef(str(VRES) + iri_local(title))


def dbr_iri(en_title):
    return URIRef(str(DBR) + iri_local(en_title))


def category_iri(name):
    name = str(name)
    for prefix in ("Thể loại:", "Category:"):
        if name.startswith(prefix):
            name = name[len(prefix) :]
    return URIRef(str(VRES) + "Thể_loại:" + iri_local(name))


def qid_of(value):
    """'Q881' hoặc 'http://www.wikidata.org/entity/Q881' → 'Q881'."""
    return str(value).rsplit("/", 1)[-1]


def wd_iri(value):
    return URIRef(str(WD) + qid_of(value))


def wiki_page_url(title, lang="vi"):
    path = quote(norm_title(title).replace(" ", "_"), safe=URL_SAFE)
    return f"https://{lang}.wikipedia.org/wiki/{path}"

"""Namespace và prefix dùng chung."""

from rdflib import Namespace
from rdflib.namespace import DCTERMS, FOAF, OWL, RDF, RDFS, SKOS, XSD

VIO = Namespace("http://vi.dbpedia.org/ontology/")  # ontology riêng của dự án
VRES = Namespace("http://vi.dbpedia.org/resource/")  # tài nguyên (thực thể)
VIP = Namespace("http://vi.dbpedia.org/property/")  # thuộc tính thô từ infobox, như dbp: của DBpedia
VCAT = Namespace("http://vi.dbpedia.org/resource/Thể_loại:")  # thể loại Wikipedia
DBO = Namespace("http://dbpedia.org/ontology/")
DBR = Namespace("http://dbpedia.org/resource/")
WD = Namespace("http://www.wikidata.org/entity/")
WGS84 = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")
GEORSS = Namespace("http://www.georss.org/georss/")
PROV = Namespace("http://www.w3.org/ns/prov#")
VOID = Namespace("http://rdfs.org/ns/void#")
SCHEMA = Namespace("http://schema.org/")
DC = Namespace("http://purl.org/dc/elements/1.1/")

PREFIXES = {
    "vio": str(VIO),
    "vres": str(VRES),
    "vip": str(VIP),
    "vcat": str(VCAT),
    "dbo": str(DBO),
    "dbr": str(DBR),
    "wd": str(WD),
    "rdf": str(RDF),
    "rdfs": str(RDFS),
    "owl": str(OWL),
    "xsd": str(XSD),
    "foaf": str(FOAF),
    "skos": str(SKOS),
    "dct": str(DCTERMS),
    "dc": str(DC),
    "prov": str(PROV),
    "wgs84": str(WGS84),
    "georss": str(GEORSS),
    "void": str(VOID),
}


def bind_prefixes(graph):
    """Gắn prefix chuẩn của dự án vào graph trước khi ghi file."""
    for prefix, ns in PREFIXES.items():
        graph.bind(prefix, ns, override=True, replace=True)
    return graph

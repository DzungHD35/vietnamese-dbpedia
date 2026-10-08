"""python -m vidbpedia <lệnh> [tuỳ chọn]

Các bước theo thứ tự: seeds → enrich → ontology → build → postprocess, rồi serve; query để truy vấn từ terminal.
"""

import importlib
import sys

from vidbpedia.common import utf8_console

COMMANDS = {
    "seeds": ("vidbpedia.crawl.wikidata_seeds", "chọn thực thể và lấy dữ kiện từ Wikidata"),
    "enrich": ("vidbpedia.crawl.wiki_enrich", "lấy bài viết, infobox, thể loại, redirect từ viwiki"),
    "ontology": ("vidbpedia.kg.ontology", "ghép ontology/*.ttl thành vi-ontology.ttl"),
    "build": ("vidbpedia.crawl.build_rdf", "dựng RDF từ dữ liệu thô"),
    "postprocess": ("vidbpedia.kg.postprocess", "kiểm tra, suy luận, VoID, xuất dataset"),
    "serve": ("vidbpedia.web.app", "chạy giao diện, SPARQL endpoint và Linked Data"),
    "query": ("vidbpedia.kg.query", "chạy truy vấn SPARQL từ terminal"),
}


def main():
    utf8_console()
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        for name, (_, help_text) in COMMANDS.items():
            print(f"  {name:<12} {help_text}")
        sys.exit(0 if len(sys.argv) < 2 else 2)
    name = sys.argv[1]
    module = importlib.import_module(COMMANDS[name][0])
    sys.argv = [f"python -m vidbpedia {name}", *sys.argv[2:]]
    module.main()


if __name__ == "__main__":
    main()

"""/api/entity/{id}/tree: cây quan hệ sâu 3 bước của một thực thể, như mục "Cây quan hệ" ở tab Tài nguyên.

Cùng dữ liệu và cùng giới hạn với trang của team (`ResourceView._tree_groups`, MAX_DEPTH, MAX_CHILDREN,
TREE_BUDGET): gốc → đội → sân → tỉnh; chỉ triple khai báo (trừ vio:playedFor); chặng thi đấu được thay bằng
đội của chặng kèm ghi chú năm, số trận, bàn thắng, cho mượn. Ở đây chỉ trả JSON lồng nhau, không sinh HTML.
"""

from fastapi import APIRouter

from ui.api import adapters, serialize
from ui.api.state import kg, resolve_or_404
from vidbpedia.vocab import VIO
from vidbpedia.web.resource_page import MAX_CHILDREN, MAX_DEPTH, TREE_BUDGET

router = APIRouter(prefix="/api")


def _leaf(view, target, station=None) -> dict:
    return {
        "node": serialize.node(view, target),
        "station": view.local(station) if station is not None else None,
        "note": adapters.station_note(view, station) if station is not None else None,
        "groups": [],
    }


def _node(view, target, depth, path, budget, station=None) -> dict:
    budget[0] -= 1
    out = _leaf(view, target, station)
    if depth < MAX_DEPTH and budget[0] > 0:
        groups = adapters.tree_groups(view, target, path | {target}, root=False)
        if groups:
            out["groups"] = _groups(view, groups, depth + 1, path | {target}, budget)
    return out


def _groups(view, groups, depth, path, budget) -> list[dict]:
    g = view.g
    limit = MAX_CHILDREN.get(depth, 6)
    out = []
    for p, direction, targets in groups:
        shown = targets[:limit]
        children = []
        for t in shown:
            if p == VIO.careerStation:
                team = g.value(t, VIO.team)
                if team is None or team in path:
                    budget[0] -= 1
                    children.append(_leaf(view, t))  # chặng không có đội (hoặc đội đã nằm trên đường đi)
                else:
                    children.append(_node(view, team, depth, path | {t}, budget, station=t))
            else:
                children.append(_node(view, t, depth, path, budget))
        out.append(
            {
                "prop": view.qname(p),
                "label": view.label(p),
                "direction": direction,
                "total": len(targets),
                "more": len(targets) - len(shown),
                "children": children,
            }
        )
    return out


@router.get("/entity/{name:path}/tree")
def relation_tree(name: str):
    iri = resolve_or_404(name)
    view = kg.view
    budget = [TREE_BUDGET]
    groups = adapters.tree_groups(view, iri, {iri}, root=True)
    return {
        "root": serialize.node(view, iri),
        "maxDepth": MAX_DEPTH,
        "groups": _groups(view, groups, 1, {iri}, budget) if groups else [],
    }

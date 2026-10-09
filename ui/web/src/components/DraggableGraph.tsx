import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { useNavigate } from "react-router-dom";
import type { GraphLayout, GraphLayoutNode } from "../api/types";
import { useApi } from "../api/useApi";
import { ErrorState, Loading } from "./States";

/**
 * Đồ thị lân cận kéo thả được. Bố cục ban đầu là đúng bố cục của trang tài nguyên Gradio (máy chủ dùng chung
 * `ResourceView._graph_layout`): hai phía, cùng cách chọn và sắp xếp nút. Khác Gradio ở hai điểm: kéo thả để
 * di chuyển nút, và tên quan hệ (playedFor, birthProvince…) ghi ngay giữa mũi tên thay vì dưới tên nút.
 */

type Pos = { x: number; y: number };
type Drag = { id: string; dx: number; dy: number; sx: number; sy: number; moved: boolean };

const CENTER = "__center__";
const BOX_H = 28;
const CURVE = 90; // độ cong của mũi tên, như Gradio

const MAX_TITLE = 26; // tên dài được rút gọn trong hộp để chừa chỗ ghi tên quan hệ giữa mũi tên
const short = (title: string) => (title.length > MAX_TITLE ? `${title.slice(0, MAX_TITLE - 1).trimEnd()}…` : title);
const boxWidth = (title: string) => Math.min(Math.max(short(title).length * 7 + 24, 96), 210);
const centerWidth = (label: string) => Math.min(Math.max(label.length * 8 + 32, 150), 300);
const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi);

function initialPositions(lay: GraphLayout): Record<string, Pos> {
  const pos: Record<string, Pos> = { [CENTER]: { x: lay.cx, y: lay.cy } };
  for (const n of lay.nodes) {
    const w = boxWidth(n.title);
    pos[n.id] = { x: n.side === 1 ? lay.width - 16 - w : 16, y: n.y };
  }
  return pos;
}

/** Đường cong từ cạnh nút giữa tới cạnh nút lân cận (phía nào gần thì nối phía đó) và điểm giữa để ghi nhãn. */
function edgeGeometry(n: GraphLayoutNode, p: Pos, c: Pos, cw: number) {
  const w = boxWidth(n.title);
  const right = p.x + w / 2 >= c.x;
  const ax = c.x + (right ? cw / 2 : -cw / 2);
  const ay = c.y;
  const bx = right ? p.x : p.x + w;
  const by = p.y;
  const s = right ? 1 : -1;
  // P0 → P3 theo hướng của triple: đi ra thì từ nút giữa, đi vào thì từ nút lân cận
  const [p0, p1, p2, p3] =
    n.direction === "in"
      ? [
          [bx, by],
          [bx - s * CURVE, by],
          [ax + s * CURVE, ay],
          [ax, ay],
        ]
      : [
          [ax, ay],
          [ax + s * CURVE, ay],
          [bx - s * CURVE, by],
          [bx, by],
        ];
  const d = `M${p0[0]} ${p0[1]}C${p1[0]} ${p1[1]} ${p2[0]} ${p2[1]} ${p3[0]} ${p3[1]}`;
  // điểm t = 0,5 của đường cong bậc ba: (P0 + 3P1 + 3P2 + P3) / 8
  const mx = (p0[0] + 3 * p1[0] + 3 * p2[0] + p3[0]) / 8;
  const my = (p0[1] + 3 * p1[1] + 3 * p2[1] + p3[1]) / 8;
  return { d, mx, my };
}

export function DraggableGraph({ id, showInferred }: { id: string; showInferred: boolean }) {
  const navigate = useNavigate();
  const url = `/api/entity/${encodeURIComponent(id)}/graph${showInferred ? "" : "?inferred=false"}`;
  const graph = useApi<{ layout: GraphLayout | null }>(url);
  const lay = graph.data?.layout ?? null;

  const start = useMemo(() => (lay ? initialPositions(lay) : {}), [lay]);
  const [pos, setPos] = useState<Record<string, Pos>>(start);
  useEffect(() => setPos(start), [start]); // thực thể khác hoặc bật/tắt suy luận: về bố cục ban đầu
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<Drag | null>(null);

  if (graph.loading && !graph.data) return <Loading text="Đang vẽ đồ thị lân cận…" />;
  if (graph.error) return <ErrorState message={graph.error} />;
  if (!lay) return <p className="muted">Không có liên kết tới tài nguyên khác.</p>;

  const cw = centerWidth(lay.center);
  const c = pos[CENTER] ?? { x: lay.cx, y: lay.cy };
  const moved = Object.keys(start).some((k) => pos[k] && (pos[k].x !== start[k].x || pos[k].y !== start[k].y));

  const toSvg = (ev: PointerEvent) => {
    const svg = svgRef.current!;
    const pt = svg.createSVGPoint();
    pt.x = ev.clientX;
    pt.y = ev.clientY;
    return pt.matrixTransform(svg.getScreenCTM()!.inverse());
  };

  const open = (n: GraphLayoutNode) => {
    if (n.external) window.open(n.href ?? n.iri, "_blank", "noopener");
    else navigate(`/entity/${encodeURIComponent(n.id)}`);
  };

  const onDown = (key: string) => (ev: PointerEvent<SVGGElement>) => {
    if (ev.button !== 0) return;
    ev.currentTarget.setPointerCapture(ev.pointerId);
    const p = toSvg(ev);
    const cur = pos[key];
    drag.current = { id: key, dx: p.x - cur.x, dy: p.y - cur.y, sx: p.x, sy: p.y, moved: false };
  };

  const onMove = (ev: PointerEvent<SVGGElement>) => {
    const dr = drag.current;
    if (!dr) return;
    const p = toSvg(ev);
    if (!dr.moved && Math.hypot(p.x - dr.sx, p.y - dr.sy) < 3) return; // rung tay khi bấm: chưa tính là kéo
    dr.moved = true;
    const node = lay.nodes.find((n) => n.id === dr.id);
    const w = node ? boxWidth(node.title) : 0;
    const next =
      dr.id === CENTER
        ? { x: clamp(p.x - dr.dx, cw / 2, lay.width - cw / 2), y: clamp(p.y - dr.dy, 18, lay.height - 18) }
        : { x: clamp(p.x - dr.dx, 0, lay.width - w), y: clamp(p.y - dr.dy, BOX_H / 2, lay.height - BOX_H / 2) };
    setPos((old) => ({ ...old, [dr.id]: next }));
  };

  const onUp = (n: GraphLayoutNode | null) => (ev: PointerEvent<SVGGElement>) => {
    const dr = drag.current;
    drag.current = null;
    if (ev.currentTarget.hasPointerCapture(ev.pointerId)) ev.currentTarget.releasePointerCapture(ev.pointerId);
    if (dr && !dr.moved && n) open(n); // bấm (không kéo) thì mở trang của nút
  };

  const onKey = (n: GraphLayoutNode) => (ev: KeyboardEvent<SVGGElement>) => {
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      open(n);
    }
  };

  const edges = lay.nodes.map((n) => ({ n, ...edgeGeometry(n, pos[n.id] ?? start[n.id], c, cw) }));

  return (
    <div className="static-graph dgraph">
      <div className="dgraph-bar">
        <span className="muted small">Kéo thả để di chuyển nút · bấm một nút để mở trang của nút đó.</span>
        <button type="button" className="btn btn-sm" onClick={() => setPos(start)} disabled={!moved}>
          Đặt lại vị trí
        </button>
      </div>
      <div className="rv-graph">
        <svg ref={svgRef} viewBox={`0 0 ${lay.width} ${lay.height}`} role="img" aria-label={`Đồ thị lân cận của ${lay.center}`}>
          <defs>
            <marker id="dg-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0 0L10 5L0 10z" />
            </marker>
            <marker id="dg-arr-inf" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0 0L10 5L0 10z" />
            </marker>
          </defs>
          {edges.map(({ n, d }) => (
            <path
              key={`e-${n.id}`}
              className={n.inferred ? "rv-edge rv-edge-inf" : "rv-edge"}
              d={d}
              markerEnd={n.inferred ? "url(#dg-arr-inf)" : "url(#dg-arr)"}
            />
          ))}
          {edges.map(({ n, mx, my }) => (
            <text key={`l-${n.id}`} className={n.inferred ? "dg-label inf" : "dg-label"} x={mx} y={my + 3.5} textAnchor="middle">
              <title>{n.props.join(", ")}</title>
              {n.label}
            </text>
          ))}
          {lay.nodes.map((n) => {
            const p = pos[n.id] ?? start[n.id];
            const w = boxWidth(n.title);
            return (
              <g
                key={`n-${n.id}`}
                className={`rv-node rv-k-${n.kind} dg-node`}
                tabIndex={0}
                role="link"
                aria-label={n.title}
                onPointerDown={onDown(n.id)}
                onPointerMove={onMove}
                onPointerUp={onUp(n)}
                onPointerCancel={onUp(null)}
                onKeyDown={onKey(n)}
              >
                <title>{`${n.title}
${n.iri}`}</title>
                <rect x={p.x} y={p.y - BOX_H / 2} width={w} height={BOX_H} rx={5} />
                <text className="rv-t1" x={p.x + 10} y={p.y + 4}>
                  {short(n.title)}
                </text>
              </g>
            );
          })}
          <g
            className="rv-center dg-node"
            onPointerDown={onDown(CENTER)}
            onPointerMove={onMove}
            onPointerUp={onUp(null)}
            onPointerCancel={onUp(null)}
          >
            <rect x={c.x - cw / 2} y={c.y - 18} width={cw} height={36} rx={6} />
            <text x={c.x} y={c.y + 5} textAnchor="middle">
              {lay.center}
            </text>
          </g>
        </svg>
      </div>
      <p className="rv-legend">
        <span className="rv-lg rv-lg-a" />
        khai báo <span className="rv-lg rv-lg-i" />
        suy luận <span className="rv-sw rv-k-player" />
        cầu thủ <span className="rv-sw rv-k-club" />
        CLB / đội tuyển <span className="rv-sw rv-k-stadium" />
        sân <span className="rv-sw rv-k-prov" />
        tỉnh / quốc gia <span className="rv-sw rv-k-uni" />
        đại học <span className="rv-sw rv-k-lod" />
        LOD bên ngoài
      </p>
      {lay.hidden > 0 && <p className="rv-note">Còn {lay.hidden} liên kết khác, xem bảng bên dưới.</p>}
    </div>
  );
}

import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import fcose from "cytoscape-fcose";
import { useEffect, useRef, useState } from "react";
import { getJson } from "../api/client";
import type { GraphData, Kind, Neighbors, Node } from "../api/types";
import { KIND_LABEL, cssColor, kindColorVar } from "../utils/kinds";

cytoscape.use(fcose);

const MAX_NODES = 150;
const EXPAND_LIMIT = 12; // số lân cận thêm vào mỗi lần mở rộng
const EXPAND_DELAY_MS = 250; // chờ xem có phải bấm đúp không trước khi mở rộng

interface Props {
  title: string;
  data: GraphData;
  centerId?: string;
  expandable: boolean;
  showInferred: boolean;
  onOpen: (id: string) => void;
}

function toElements(data: GraphData, centerId?: string): ElementDefinition[] {
  const ids = new Set(data.nodes.map((n) => n.id));
  const nodes = data.nodes.map((n) => nodeElement(n, n.id === centerId));
  const edges = data.edges.filter((e) => ids.has(e.source) && ids.has(e.target)).map(edgeElement);
  return [...nodes, ...edges];
}

function nodeElement(n: Node, center: boolean): ElementDefinition {
  const label = n.label.length > 26 ? `${n.label.slice(0, 25)}…` : n.label;
  return {
    group: "nodes",
    data: { id: n.id, label, kind: n.kind, color: cssColor(`--k-${n.kind}`), center, external: !!n.external, full: n },
  };
}

function edgeElement(e: GraphData["edges"][number]): ElementDefinition {
  return {
    group: "edges",
    data: {
      id: `${e.source}|${e.prop}|${e.target}`,
      source: e.source,
      target: e.target,
      label: e.prop.split(":").pop(),
      inferred: e.inferred,
    },
  };
}

function stylesheet(): cytoscape.StylesheetJson {
  const asserted = cssColor("--asserted");
  const inferred = cssColor("--inferred");
  return [
    {
      selector: "node",
      style: {
        label: "data(label)",
        "font-family": "Be Vietnam Pro, system-ui, sans-serif",
        "font-size": 10,
        color: "#16202e",
        "text-valign": "bottom",
        "text-margin-y": 4,
        "text-background-color": "#fbfcfd",
        "text-background-opacity": 0.85,
        "text-background-padding": "1px",
        "background-color": "data(color)",
        width: 22,
        height: 22,
        "border-width": 1.5,
        "border-color": "#ffffff",
      },
    },
    {
      selector: "node[?center]",
      style: { width: 40, height: 40, "border-width": 3, "border-color": "#16202e", "font-size": 12, "font-weight": 700 },
    },
    {
      selector: "node[kind = 'lod']",
      style: { shape: "diamond", "background-color": "#ffffff", "border-style": "dashed", "border-width": 2, "border-color": "data(color)" },
    },
    { selector: "node.expanded", style: { "border-style": "double", "border-width": 4, "border-color": "#16202e" } },
    { selector: "node:selected", style: { "border-color": cssColor("--accent"), "border-width": 3.5 } },
    {
      selector: "edge",
      style: {
        width: 1.5,
        "line-color": asserted,
        "target-arrow-color": asserted,
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
        label: "data(label)",
        "font-size": 8,
        color: asserted,
        "text-rotation": "autorotate",
        "text-background-color": "#fbfcfd",
        "text-background-opacity": 0.9,
        "text-background-padding": "1px",
      },
    },
    {
      selector: "edge[?inferred]",
      style: { "line-style": "dashed", "line-color": inferred, "target-arrow-color": inferred, color: inferred },
    },
    { selector: ".hidden", style: { display: "none" } },
  ];
}

/** Ẩn cạnh suy luận khi tắt công tắc; nút chỉ còn nối bằng cạnh suy luận cũng ẩn (trừ nút trung tâm). */
function applyVisibility(cy: Core, showInferred: boolean) {
  cy.batch(() => {
    cy.edges().forEach((e) => {
      e.toggleClass("hidden", !showInferred && !!e.data("inferred"));
    });
    cy.nodes().forEach((n) => {
      const alone = !showInferred && !n.data("center") && n.connectedEdges().not(".hidden").empty();
      n.toggleClass("hidden", alone);
    });
  });
}

/** Đồ thị Cytoscape (fcose): bấm một nút để mở rộng lân cận, bấm đúp để mở trang; cạnh suy luận nét đứt tím. */
export function GraphView({ title, data, centerId, expandable, showInferred, onOpen }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const inferredRef = useRef(showInferred);
  const openRef = useRef(onOpen);
  const [selected, setSelected] = useState<Node | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [size, setSize] = useState(0); // tổng số nút trên canvas, đổi khi dựng lại hoặc mở rộng
  const [visible, setVisible] = useState(0);
  const [note, setNote] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState(0);
  inferredRef.current = showInferred;
  openRef.current = onOpen;

  // dựng lại đồ thị khi dữ liệu gốc đổi hoặc bấm "Thu gọn"
  useEffect(() => {
    const container = box.current;
    if (!container) return;
    const cy = cytoscape({
      container,
      elements: toElements(data, centerId),
      style: stylesheet(),
      minZoom: 0.3,
      maxZoom: 2.5,
      userZoomingEnabled: false, // cuộn thường phải cuộn trang; chỉ zoom khi giữ Ctrl/⌘ (xem onWheel)
    });
    const onWheel = (ev: WheelEvent) => {
      if (!ev.ctrlKey && !ev.metaKey) return;
      ev.preventDefault();
      const rect = container.getBoundingClientRect();
      cy.zoom({ level: cy.zoom() * (ev.deltaY < 0 ? 1.15 : 1 / 1.15), renderedPosition: { x: ev.clientX - rect.left, y: ev.clientY - rect.top } });
    };
    container.addEventListener("wheel", onWheel, { passive: false });
    cyRef.current = cy;
    setSelected(null);
    setExpanded(new Set());
    setNote(null);
    setSize(cy.nodes().length);
    cy.layout({ name: "fcose", animate: false, randomize: true, fit: true, padding: 30, nodeRepulsion: () => 9000, idealEdgeLength: () => 95 } as cytoscape.LayoutOptions).run();
    applyVisibility(cy, inferredRef.current);

    let timer: number | undefined;
    const expand = (id: string) => {
      const node = cy.getElementById(id);
      if (node.empty() || node.data("external") || node.hasClass("expanded")) return;
      if (cy.nodes().length >= MAX_NODES) {
        setNote(`Đã đạt giới hạn ${MAX_NODES} nút, không mở rộng thêm.`);
        return;
      }
      getJson<Neighbors>(`/api/neighbors/${encodeURIComponent(id)}?limit=${EXPAND_LIMIT}`)
        .then((res) => {
          if (cy.destroyed()) return;
          const origin = node.position();
          const room = MAX_NODES - cy.nodes().length;
          const candidates = res.nodes.filter((n) => cy.getElementById(n.id).empty());
          const fresh = candidates.slice(0, room);
          const old = cy.nodes().map((n) => ({ nodeId: n.id(), position: { ...n.position() } }));
          cy.add(fresh.map((n) => ({ ...nodeElement(n, false), position: { x: origin.x + (Math.random() - 0.5) * 60, y: origin.y + (Math.random() - 0.5) * 60 } })));
          cy.add(
            res.edges
              .map(edgeElement)
              .filter((e) => cy.getElementById(e.data.id as string).empty())
              .filter((e) => !cy.getElementById(e.data.source as string).empty() && !cy.getElementById(e.data.target as string).empty()),
          );
          node.addClass("expanded");
          setExpanded((s) => new Set(s).add(id));
          setSize(cy.nodes().length);
          if (fresh.length < candidates.length) setNote(`Đã đạt giới hạn ${MAX_NODES} nút.`);
          applyVisibility(cy, inferredRef.current);
          if (fresh.length > 0) {
            cy.layout({ name: "fcose", animate: true, animationDuration: 400, randomize: false, fit: false, nodeRepulsion: () => 9000, idealEdgeLength: () => 95, fixedNodeConstraint: old } as unknown as cytoscape.LayoutOptions).run();
          }
        })
        .catch((e: unknown) => setNote(e instanceof Error ? e.message : String(e)));
    };

    cy.on("tap", "node", (evt) => {
      const n = evt.target;
      setSelected(n.data("full") as Node);
      window.clearTimeout(timer);
      if (expandable && n.data("kind") !== "lod") timer = window.setTimeout(() => expand(n.id()), EXPAND_DELAY_MS);
    });
    cy.on("dbltap", "node", (evt) => {
      window.clearTimeout(timer);
      const full = evt.target.data("full") as Node;
      if (full.external) window.open(full.iri, "_blank", "noopener");
      else openRef.current(full.id);
    });
    cy.on("tap", (evt) => {
      if (evt.target === cy) setSelected(null);
    });

    return () => {
      window.clearTimeout(timer);
      container.removeEventListener("wheel", onWheel);
      cy.destroy();
      cyRef.current = null;
    };
  }, [data, centerId, expandable, resetKey]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    applyVisibility(cy, showInferred);
    setVisible(cy.nodes().not(".hidden").length);
  }, [showInferred, size]);

  const kinds = Array.from(new Set(data.nodes.map((n) => n.kind))) as Kind[];
  const canExpand = expandable && selected && !selected.external && !expanded.has(selected.id);

  return (
    <section className="card graph-card">
      <div className="graph-bar">
        <h2>{title}</h2>
        <span className="muted small">{visible} nút</span>
        <button type="button" className="btn" onClick={() => cyRef.current?.fit(undefined, 30)}>
          Vừa khung
        </button>
        {expandable && (
          <button type="button" className="btn" onClick={() => setResetKey((k) => k + 1)}>
            Thu gọn về ban đầu
          </button>
        )}
      </div>
      <div className="graph-canvas" ref={box} />
      <div className="graph-info">
        {selected ? (
          <>
            <span>
              <i className="dot" style={{ background: kindColorVar(selected.kind) }} />
              <strong>{selected.label}</strong> {selected.cls && <span className="muted">· {selected.cls}</span>}
            </span>
            {selected.external ? (
              <a className="btn" href={selected.iri} target="_blank" rel="noopener noreferrer">Mở ↗</a>
            ) : (
              <button type="button" className="btn" onClick={() => onOpen(selected.id)}>Mở trang</button>
            )}
            {canExpand && <span className="muted small">đang mở rộng lân cận…</span>}
          </>
        ) : (
          <span className="muted small">{expandable ? "Bấm một nút để mở rộng lân cận, bấm đúp để mở trang · Ctrl + cuộn để phóng to." : "Bấm đúp một nút để mở trang · Ctrl + cuộn để phóng to."}</span>
        )}
        {note && <span className="graph-note small">{note}</span>}
        <span className="graph-legend">
          <span><i className="lg-edge" />khai báo</span>
          <span><i className="lg-edge inf" />suy luận</span>
          {kinds.map((k) => (
            <span key={k}><i className="dot" style={{ background: kindColorVar(k) }} />{KIND_LABEL[k]}</span>
          ))}
        </span>
      </div>
    </section>
  );
}

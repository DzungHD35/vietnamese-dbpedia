import type { Feature, FeatureCollection, Geometry } from "geojson";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useMemo, useState } from "react";
import { CircleMarker, GeoJSON, MapContainer, Marker, Polyline, Tooltip } from "react-leaflet";
import { Link } from "react-router-dom";
import { feature, merge, mesh } from "topojson-client";
import type { GeometryCollection, MultiPolygon, Polygon, Topology } from "topojson-specification";
import type { MapData, MapPoint, ProvinceCounts, ProvinceDetail, ProvinceStat } from "../api/types";
import { useApi } from "../api/useApi";
import { EntityLink } from "../components/EntityLink";
import { ErrorState, Loading } from "../components/States";
import { useInference } from "../context/InferenceContext";
import { formatNumber } from "../utils/format";
import { cssColor } from "../utils/kinds";

type Era = "before" | "after";
type Metric = keyof ProvinceCounts;
type Shapes = Topology<{ provinces: GeometryCollection<{ name: string }> }>;
type Props = { id: string; label: string; value: number };

const ERAS: { id: Era; label: string; note: string }[] = [
  { id: "before", label: "Trước 2025", note: "63 tỉnh" },
  { id: "after", label: "Sau sáp nhập", note: "34 tỉnh" },
];
const METRICS: { id: Metric; label: string }[] = [
  { id: "players", label: "Cầu thủ" },
  { id: "clubs", label: "CLB" },
  { id: "unis", label: "Đại học" },
];
const METRIC_UNITS: Record<Metric, string> = { players: "cầu thủ quê ở đây", clubs: "CLB", unis: "trường đại học" };
// thang màu tuần tự một sắc độ; 0 là xám để tách "không có dữ liệu" khỏi "ít"
const SCALE = ["#d7efe9", "#a6dbcf", "#6cc0b0", "#35998a", "#0f6e64"];
const ZERO = "#eef1f4";
const BOUNDS: L.LatLngBoundsExpression = [
  [8.4, 102.2],
  [23.4, 114.4],
];
const ISLANDS: { name: string; at: [number, number] }[] = [
  { name: "Quần đảo Hoàng Sa", at: [17.15, 112.0] },
  { name: "Quần đảo Trường Sa", at: [11.2, 114.6] },
];

/** 5 ngưỡng theo phân vị của các giá trị > 0 (dữ liệu lệch mạnh: Hà Nội, Nghệ An rất lớn). */
function breaks(values: number[]): number[] {
  const v = values.filter((x) => x > 0).sort((a, b) => a - b);
  if (v.length === 0) return [1];
  const q = [0.2, 0.4, 0.6, 0.8].map((p) => v[Math.min(v.length - 1, Math.floor(p * v.length))]);
  return [...new Set([1, ...q.map((x) => Math.max(1, x))])];
}

function colorOf(value: number, th: number[]): string {
  if (value <= 0) return ZERO;
  let i = 0;
  while (i + 1 < th.length && value >= th[i + 1]) i += 1;
  return SCALE[Math.min(SCALE.length - 1, i + (SCALE.length - th.length))];
}

/** Mũi tên ở 70% đoạn nối, xoay theo hướng from → to (đủ chính xác ở phạm vi Việt Nam). */
function arrowIcon(a: MapPoint, b: MapPoint, color: string) {
  const angle = (Math.atan2(b.lat - a.lat, (b.lon - a.lon) * Math.cos((a.lat * Math.PI) / 180)) * 180) / Math.PI;
  return L.divIcon({
    className: "map-arrow",
    iconSize: [14, 14],
    iconAnchor: [7, 7],
    html: `<svg width="14" height="14" viewBox="0 0 14 14" style="transform:rotate(${-angle}deg)"><path d="M2 2 L13 7 L2 12 Z" fill="${color}"/></svg>`,
  });
}

/** Điểm đặt nhãn: tâm khung bao của mảnh lớn nhất (tránh đặt giữa biển với tỉnh có quần đảo). */
function labelPoint(g: Geometry): [number, number] | null {
  const rings = g.type === "Polygon" ? [g.coordinates[0]] : g.type === "MultiPolygon" ? g.coordinates.map((p) => p[0]) : [];
  const ring = rings.sort((a, b) => b.length - a.length)[0];
  if (!ring) return null;
  const lons = ring.map((c) => c[0]);
  const lats = ring.map((c) => c[1]);
  return [(Math.min(...lats) + Math.max(...lats)) / 2, (Math.min(...lons) + Math.max(...lons)) / 2];
}

const TOP_LABELS = 6;
const LABEL_BOX: [number, number] = [0.6, 1.6]; // khung nhãn tính bằng độ (vĩ, kinh) để tránh chồng nhau
const labelIcon = (name: string, value: number) =>
  L.divIcon({ className: "map-label", iconSize: [140, 30], iconAnchor: [70, 15], html: `${name}<br><b>${value}</b>` });

const islandIcon = (name: string) =>
  L.divIcon({ className: "map-island", iconSize: [160, 20], iconAnchor: [80, 10], html: name });

/** Bản đồ tỉnh: 63 tỉnh cũ, hoặc 34 tỉnh mới ghép từ chính graph (vio:successor); tô màu theo số liệu. */
export function MapPage() {
  const shapes = useApi<Shapes>("/api/map/shapes");
  const stats = useApi<ProvinceStat[]>("/api/map/provinces");
  const points = useApi<MapData>("/api/map");
  const { showInferred } = useInference();
  const [era, setEra] = useState<Era>("after");
  const [metric, setMetric] = useState<Metric>("players");
  const [selected, setSelected] = useState<string | null>(null);
  const [arrows, setArrows] = useState(false);
  const [unis, setUnis] = useState(false);
  const [stadiums, setStadiums] = useState(false);

  const byId = useMemo(() => new Map((stats.data ?? []).map((s) => [s.id, s])), [stats.data]);

  // mỗi hình 63 tỉnh → tỉnh hiện hành mà nó thuộc về (theo successor trong graph)
  const geo = useMemo(() => {
    if (!shapes.data || !stats.data) return null;
    const topo = shapes.data;
    const obj = topo.objects.provinces;
    const finalOf = (id: string | number | undefined) => byId.get(String(id))?.final ?? String(id);
    const before = feature(topo, obj) as FeatureCollection<Geometry, { name: string }>;
    const groups = new Map<string, typeof obj.geometries>();
    for (const g of obj.geometries) {
      if (g.id == null) continue;
      const f = finalOf(g.id);
      groups.set(f, [...(groups.get(f) ?? []), g]);
    }
    const after: Feature<Geometry, { id: string }>[] = [...groups].map(([id, geoms]) => ({
      type: "Feature",
      properties: { id },
      geometry: merge(topo, geoms as (Polygon | MultiPolygon)[]),
    }));
    // ranh giới giữa hai tỉnh cũ nay đã cùng một tỉnh mới: vẽ mờ để thấy "ghép từ"
    const seams = mesh(topo, obj, (a, b) => a !== b && a.id !== b.id && finalOf(a.id) === finalOf(b.id));
    return { before, after, seams, groups: groups.size };
  }, [shapes.data, stats.data, byId]);

  const layer = useMemo(() => {
    if (!geo) return null;
    const value = (id: string) => {
      const s = byId.get(id);
      if (!s) return 0;
      return era === "after" ? (s.groupCounts ?? s.counts)[metric] : s.counts[metric];
    };
    const src =
      era === "after"
        ? geo.after.map((f) => f.properties.id)
        : geo.before.features.map((f) => String(f.id ?? ""));
    const features: Feature<Geometry, Props>[] = (era === "after" ? geo.after : geo.before.features).map((f, i) => {
      const id = src[i];
      return { ...f, properties: { id, label: byId.get(id)?.label ?? id, value: value(id) } };
    });
    const th = breaks(features.map((f) => f.properties.value));
    // nhãn cố định cho vài tỉnh dẫn đầu; bỏ tỉnh có nhãn chồng lên nhãn đã đặt (miền Bắc nhiều tỉnh nhỏ)
    const top: { id: string; label: string; value: number; at: [number, number] }[] = [];
    for (const f of [...features].sort((a, b) => b.properties.value - a.properties.value)) {
      if (top.length >= TOP_LABELS || f.properties.value <= 0) break;
      const at = labelPoint(f.geometry);
      if (!at || top.some((t) => t.id === f.properties.id || (Math.abs(t.at[0] - at[0]) < LABEL_BOX[0] && Math.abs(t.at[1] - at[1]) < LABEL_BOX[1]))) continue;
      top.push({ id: f.properties.id, label: f.properties.label.replace(/\s*\(.*\)$/, ""), value: f.properties.value, at });
    }
    return { fc: { type: "FeatureCollection", features } as FeatureCollection<Geometry, Props>, th, top };
  }, [geo, era, metric, byId]);

  if (shapes.loading || stats.loading) return <Loading text="Đang tải bản đồ…" />;
  if (shapes.error || stats.error || !layer || !geo)
    return <ErrorState message={shapes.error ?? stats.error ?? "Không có dữ liệu bản đồ."} />;

  const pointById = new Map((points.data?.points ?? []).map((p) => [p.node.id, p]));
  const successions = (points.data?.successions ?? []).filter((s) => showInferred || !s.inferred);
  const accent = cssColor("--accent");

  return (
    <div className="map-page">
      <h1 className="page-title">
        {era === "after" ? "34 tỉnh mới, ghép từ 63 tỉnh cũ ngay trên graph" : "63 tỉnh trước sáp nhập 2025"}
      </h1>
      <p className="muted lead">
        Ranh giới sau sáp nhập không tải từ nguồn ngoài: mỗi tỉnh cũ được gộp vào tỉnh kế thừa theo{" "}
        <code>vio:successor</code> trong graph ({formatNumber(geo.groups)} nhóm). Đường đứt mờ là ranh giới tỉnh cũ
        bên trong một tỉnh mới.
      </p>
      <div className="map-layout">
        <aside className="map-side">
          <div className="card">
            <div className="seg" role="group" aria-label="Thời điểm">
              {ERAS.map((e) => (
                <button key={e.id} type="button" className={era === e.id ? "active" : ""} onClick={() => setEra(e.id)}>
                  {e.label}
                  <span>{e.note}</span>
                </button>
              ))}
            </div>
            <h2 className="map-h">Tô màu theo</h2>
            <div className="seg seg-small" role="group" aria-label="Chỉ số">
              {METRICS.map((m) => (
                <button key={m.id} type="button" className={metric === m.id ? "active" : ""} onClick={() => setMetric(m.id)}>
                  {m.label}
                </button>
              ))}
            </div>
            <Legend th={layer.th} />
            <h2 className="map-h">Lớp phủ</h2>
            <label className="map-check">
              <input type="checkbox" checked={arrows} onChange={(e) => setArrows(e.target.checked)} />
              Mũi tên kế thừa <span className="muted small">({formatNumber(successions.length)})</span>
            </label>
            <label className="map-check">
              <input type="checkbox" checked={unis} onChange={(e) => setUnis(e.target.checked)} />
              Trường đại học
            </label>
            <label className="map-check">
              <input type="checkbox" checked={stadiums} onChange={(e) => setStadiums(e.target.checked)} />
              Sân vận động
            </label>
          </div>
          {selected ? (
            <ProvincePanel id={selected} era={era} metric={metric} onClose={() => setSelected(null)} />
          ) : (
            <p className="muted small map-hint">Bấm một tỉnh để xem tỉnh đó gộp từ đâu, có bao nhiêu cầu thủ, CLB, trường.</p>
          )}
        </aside>
        <div className="card map-card">
          <MapContainer
            bounds={BOUNDS}
            zoomSnap={0.25}
            minZoom={5}
            maxBounds={[
              [4, 98],
              [27, 120],
            ]}
            scrollWheelZoom={false}
            attributionControl={false}
            className="map-canvas"
          >
            <GeoJSON
              key={`${era}-${metric}-${selected}`}
              data={layer.fc}
              style={(f) => {
                const sel = f?.properties.id === selected;
                return {
                  color: sel ? accent : "#ffffff",
                  weight: sel ? 3 : 1,
                  fillColor: colorOf(f?.properties.value ?? 0, layer.th),
                  fillOpacity: 1,
                };
              }}
              onEachFeature={(f, l) => {
                const p = f.properties as Props;
                l.bindTooltip(
                  `<b>${p.label}</b><br>${formatNumber(p.value)} ${METRIC_UNITS[metric]}`,
                  { sticky: true, className: "map-tip" },
                );
                l.on({
                  click: () => setSelected(p.id),
                  mouseover: () => (l as L.Path).setStyle({ weight: 2.5, color: "#16202e" }),
                  mouseout: () =>
                    (l as L.Path).setStyle({ weight: p.id === selected ? 3 : 1, color: p.id === selected ? accent : "#ffffff" }),
                });
              }}
            />
            {era === "after" && (
              <GeoJSON
                key="seams"
                data={geo.seams}
                interactive={false}
                style={{ color: "#ffffff", weight: 1, opacity: 0.9, dashArray: "3 4" }}
              />
            )}
            {layer.top.map((t) => (
              <Marker key={`lbl-${t.id}`} position={t.at} icon={labelIcon(t.label, t.value)} interactive={false} />
            ))}
            {ISLANDS.map((i) => (
              <Marker key={i.name} position={i.at} icon={islandIcon(i.name)} interactive={false} />
            ))}
            {arrows &&
              successions.map((s) => {
                const a = pointById.get(s.from);
                const b = pointById.get(s.to);
                if (!a || !b) return null;
                const color = s.inferred ? cssColor("--inferred") : "#16202e";
                const mid: [number, number] = [a.lat + (b.lat - a.lat) * 0.7, a.lon + (b.lon - a.lon) * 0.7];
                return (
                  <span key={`${s.from}|${s.to}`}>
                    <Polyline
                      positions={[
                        [a.lat, a.lon],
                        [b.lat, b.lon],
                      ]}
                      pathOptions={{ color, weight: 1.5, dashArray: s.inferred ? "5 5" : undefined, opacity: 0.85 }}
                      interactive={false}
                    />
                    <Marker position={mid} icon={arrowIcon(a, b, color)} interactive={false} />
                  </span>
                );
              })}
            {(points.data?.points ?? [])
              .filter((p) => (unis && p.node.kind === "uni") || (stadiums && p.node.kind === "stadium"))
              .map((p) => {
                const color = cssColor(p.node.kind === "uni" ? "--k-uni" : "--k-stadium");
                return (
                  <CircleMarker
                    key={p.node.id}
                    center={[p.lat, p.lon]}
                    radius={4}
                    pathOptions={{ color: "#fff", weight: 1, fillColor: color, fillOpacity: 0.95 }}
                  >
                    <Tooltip>{p.node.label}</Tooltip>
                  </CircleMarker>
                );
              })}
          </MapContainer>
        </div>
      </div>
    </div>
  );
}

function Legend({ th }: { th: number[] }) {
  const colors = SCALE.slice(SCALE.length - th.length);
  return (
    <div className="map-legend">
      <span>
        <i style={{ background: ZERO }} />0
      </span>
      {th.map((t, i) => (
        <span key={t}>
          <i style={{ background: colors[i] }} />
          {i + 1 < th.length ? (th[i + 1] - 1 > t ? `${t}–${th[i + 1] - 1}` : `${t}`) : `${t}+`}
        </span>
      ))}
    </div>
  );
}

function ProvincePanel({ id, era, metric, onClose }: { id: string; era: Era; metric: Metric; onClose: () => void }) {
  const d = useApi<ProvinceDetail>(`/api/map/province/${encodeURIComponent(id)}?era=${era}`);
  if (d.loading) return <div className="card"><Loading text="Đang tải tỉnh…" /></div>;
  if (d.error || !d.data) return <div className="card"><ErrorState message={d.error ?? "Không có dữ liệu."} /></div>;
  const p = d.data;
  const others = p.members.filter((m) => m.id !== p.node.id);
  return (
    <div className="card map-panel" aria-label={`Chi tiết ${p.node.label}`}>
      <div className="map-panel-head">
        <h2>
          <EntityLink node={p.node} />
        </h2>
        <button type="button" className="btn" onClick={onClose} aria-label="Đóng">
          ✕
        </button>
      </div>
      {p.former ? (
        <p className="small">
          Tỉnh cũ{p.year ? `, giải thể ${p.year}` : ""} → nay thuộc <EntityLink node={p.final} />
        </p>
      ) : era === "after" && others.length > 0 ? (
        <p className="small">
          Gộp từ:{" "}
          {others.map((m, i) => (
            <span key={m.id}>
              {i > 0 && ", "}
              <EntityLink node={m} />
            </span>
          ))}
        </p>
      ) : (
        <p className="small muted">Không gộp với tỉnh nào.</p>
      )}
      <div className="map-stats">
        {(
          [
            ["players", "cầu thủ quê"],
            ["clubs", "CLB"],
            ["unis", "trường ĐH"],
          ] as [Metric, string][]
        ).map(([k, label]) => (
          <div key={k} className={metric === k ? "on" : ""}>
            <b>{formatNumber(p.counts[k])}</b>
            <span>{label}</span>
          </div>
        ))}
      </div>
      <NodeList title="Cầu thủ tiêu biểu" nodes={p.players} total={p.counts.players} />
      <NodeList title="Câu lạc bộ" nodes={p.clubs} total={p.counts.clubs} />
      <NodeList title="Trường đại học" nodes={p.unis} total={p.counts.unis} />
      <Link className="btn" to={`/sparql?query=${encodeURIComponent(p.sparql)}`}>
        Xem SPARQL cầu thủ quê ở đây
      </Link>
    </div>
  );
}

function NodeList({ title, nodes, total }: { title: string; nodes: ProvinceDetail["players"]; total: number }) {
  if (nodes.length === 0) return null;
  return (
    <div className="map-list">
      <h3>
        {title} <span className="muted small">({formatNumber(total)})</span>
      </h3>
      <ul className="plain">
        {nodes.map((n) => (
          <li key={n.id}>
            <EntityLink node={n} />
          </li>
        ))}
      </ul>
    </div>
  );
}

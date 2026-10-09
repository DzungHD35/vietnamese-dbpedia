import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useMemo, useState } from "react";
import { CircleMarker, MapContainer, Marker, Polyline, Popup, TileLayer, Tooltip } from "react-leaflet";
import { Link } from "react-router-dom";
import type { MapData, MapPoint, Succession } from "../api/types";
import { useApi } from "../api/useApi";
import { ErrorState, Loading } from "../components/States";
import { useInference } from "../context/InferenceContext";
import { formatNumber } from "../utils/format";
import { cssColor } from "../utils/kinds";

type Layer = "current" | "former" | "uni" | "stadium";
const LAYERS: { id: Layer; label: string; color: string }[] = [
  { id: "current", label: "Tỉnh, thành phố hiện hành", color: "--k-prov" },
  { id: "former", label: "Tỉnh đã sáp nhập / giải thể", color: "--k-prov" },
  { id: "uni", label: "Trường đại học", color: "--k-uni" },
  { id: "stadium", label: "Sân vận động", color: "--k-stadium" },
];
const CENTER: [number, number] = [16.2, 106.2];

function layerOf(p: MapPoint): Layer | null {
  if (p.node.kind === "prov") return p.former ? "former" : "current";
  if (p.node.kind === "uni") return "uni";
  if (p.node.kind === "stadium") return "stadium";
  return null;
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

function PointPopup({ p, out, into, name }: { p: MapPoint; out: Succession[]; into: Succession[]; name: (id: string) => string }) {
  return (
    <div className="map-popup">
      <strong>{p.node.label}</strong>
      <div className="muted small">{p.node.cls}{p.former ? " · đã giải thể" : ""}</div>
      {out.map((s) => (
        <div key={s.to} className="small">→ nhập vào <b>{name(s.to)}</b>{s.year ? ` (${s.year})` : ""}</div>
      ))}
      {into.map((s) => (
        <div key={s.from} className="small">← từ <b>{name(s.from)}</b></div>
      ))}
      <Link className="btn" to={`/entity/${encodeURIComponent(p.node.id)}`}>Mở trang</Link>
    </div>
  );
}

/** Bản đồ: tỉnh hiện hành (đặc) và tỉnh cũ (rỗng) kèm mũi tên kế thừa; cần mạng để tải nền OpenStreetMap. */
export function MapPage() {
  const { data, error, loading } = useApi<MapData>("/api/map");
  const { showInferred } = useInference();
  const [on, setOn] = useState<Record<Layer, boolean>>({ current: true, former: true, uni: false, stadium: false });
  const [arrows, setArrows] = useState(true);

  const byId = useMemo(() => new Map((data?.points ?? []).map((p) => [p.node.id, p])), [data]);
  // id là tên cục bộ đã giải mã (vd. Hà_Tây): lấy nhãn của điểm nếu có, không thì bỏ dấu gạch dưới
  const labelOf = (id: string) => byId.get(id)?.node.label ?? id.replace(/_/g, " ");
  const counts = useMemo(() => {
    const c: Record<Layer, number> = { current: 0, former: 0, uni: 0, stadium: 0 };
    for (const p of data?.points ?? []) {
      const l = layerOf(p);
      if (l) c[l] += 1;
    }
    return c;
  }, [data]);

  if (loading) return <Loading text="Đang tải dữ liệu bản đồ…" />;
  if (error || !data) return <ErrorState message={error ?? "Không có dữ liệu bản đồ."} />;

  const successions = data.successions.filter((s) => showInferred || !s.inferred);
  const inferredColor = cssColor("--inferred");
  const assertedColor = cssColor("--asserted");
  return (
    <div className="map-page">
      <h1 className="page-title">Bản đồ và thay đổi hành chính</h1>
      <p className="muted lead">
        Ontology mô hình được việc sáp nhập tỉnh nhờ <code>vio:successor</code> / <code>vio:predecessor</code>: mỗi mũi tên đi từ tỉnh cũ sang tỉnh kế thừa.
      </p>
      <div className="map-layout">
        <aside className="card map-side">
          <h2>Lớp hiển thị</h2>
          {LAYERS.map((l) => (
            <label key={l.id} className="map-check">
              <input type="checkbox" checked={on[l.id]} onChange={(e) => setOn({ ...on, [l.id]: e.target.checked })} />
              <i className={`map-dot ${l.id === "former" ? "hollow" : ""}`} style={{ borderColor: cssColor(l.color), background: l.id === "former" ? "transparent" : cssColor(l.color) }} />
              {l.label} <span className="muted small">({formatNumber(counts[l.id])})</span>
            </label>
          ))}
          <label className="map-check">
            <input type="checkbox" checked={arrows} onChange={(e) => setArrows(e.target.checked)} />
            Mũi tên kế thừa <span className="muted small">({formatNumber(successions.length)})</span>
          </label>
          <p className="muted small">
            Chú giải mũi tên: <span className="map-key" style={{ borderColor: assertedColor }} /> khai báo ·{" "}
            <span className="map-key dashed" style={{ borderColor: inferredColor }} /> suy luận (từ nghịch đảo).
          </p>
          <p className="muted small">
            Nền bản đồ OpenStreetMap cần Internet; chấm và mũi tên vẫn hiện khi offline.
          </p>
          <p className="muted small">
            Chỉ vẽ {formatNumber(data.successions.length)} / {formatNumber(data.successionsTotal)} quan hệ kế thừa mà cả hai đầu đều có toạ độ.
          </p>
        </aside>
        <div className="card map-card">
          <MapContainer center={CENTER} zoom={6} minZoom={5} scrollWheelZoom={false} className="map-canvas">
            <TileLayer attribution="&copy; OpenStreetMap" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
            {data.points.map((p) => {
              const layer = layerOf(p);
              if (!layer || !on[layer]) return null;
              const color = cssColor(LAYERS.find((l) => l.id === layer)?.color ?? "--k-other");
              const small = layer === "uni" || layer === "stadium";
              return (
                <CircleMarker
                  key={p.node.id}
                  center={[p.lat, p.lon]}
                  radius={small ? 4 : 8}
                  pathOptions={{ color, weight: 2, fillColor: color, fillOpacity: layer === "former" ? 0.04 : 0.8 }}
                >
                  <Tooltip>{p.node.label}</Tooltip>
                  <Popup>
                    <PointPopup
                      p={p}
                      out={data.successions.filter((s) => s.from === p.node.id)}
                      into={data.successions.filter((s) => s.to === p.node.id)}
                      name={labelOf}
                    />
                  </Popup>
                </CircleMarker>
              );
            })}
            {arrows &&
              successions.map((s) => {
                const a = byId.get(s.from);
                const b = byId.get(s.to);
                if (!a || !b) return null;
                const color = s.inferred ? inferredColor : assertedColor;
                const mid: [number, number] = [a.lat + (b.lat - a.lat) * 0.7, a.lon + (b.lon - a.lon) * 0.7];
                return (
                  <span key={`${s.from}|${s.to}`}>
                    <Polyline positions={[[a.lat, a.lon], [b.lat, b.lon]]} pathOptions={{ color, weight: 1.5, dashArray: s.inferred ? "5 5" : undefined, opacity: 0.8 }} />
                    <Marker position={mid} icon={arrowIcon(a, b, color)} interactive={false} />
                  </span>
                );
              })}
          </MapContainer>
        </div>
      </div>
    </div>
  );
}

import { useState, type MouseEvent } from "react";
import { useNavigate } from "react-router-dom";
import type { CareerStation, StationKind } from "../api/types";
import { shortTeamName } from "../utils/format";
import { EntityLink } from "./EntityLink";

const W = 640;
const PAD = 6;
const ROW_H = 22;
const ROW_GAP = 3;
const LANE_HEAD = 16;
const LANE_GAP = 8;
const AXIS_H = 18;
const CHAR_W = 6.1; // bề rộng ước lượng của một ký tự (để cắt nhãn cho vừa thanh)

const LANES: { kind: StationKind; label: string; color: string }[] = [
  { kind: "youth", label: "Đội trẻ", color: "var(--lane-youth)" },
  { kind: "club", label: "Câu lạc bộ", color: "var(--lane-club)" },
  { kind: "national", label: "Đội tuyển", color: "var(--lane-national)" },
];

interface Bar {
  s: CareerStation;
  x: number;
  w: number;
  row: number;
  open: boolean;
}

function tickStep(span: number): number {
  return span <= 14 ? 2 : span <= 60 ? 5 : 10;
}

function describe(s: CareerStation): string {
  const years = s.end === null && s.start !== null ? `${s.start}–nay` : s.start === s.end ? `${s.start}` : `${s.start}–${s.end ?? ""}`;
  const bits = [s.team?.label ?? "Không rõ đội", years];
  if (s.apps !== null) bits.push(`${s.apps} trận${s.goals !== null ? `, ${s.goals} bàn` : ""}`);
  if (s.onLoan) bits.push("cho mượn");
  return bits.join(" · ");
}

/** Sự nghiệp theo thời gian: 3 làn (trẻ / CLB / đội tuyển), mỗi chặng là một thanh, chặng chồng lấn xếp nhiều hàng. */
export function CareerTimeline({ career }: { career: CareerStation[] }) {
  const navigate = useNavigate();
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);

  const dated = career.filter((c) => c.start !== null);
  const unknown = career.filter((c) => c.start === null);
  if (dated.length === 0 && unknown.length === 0) return null;

  const now = new Date().getFullYear();
  const minY = dated.length ? Math.min(...dated.map((c) => c.start!)) : now;
  const maxY = dated.length ? Math.max(...dated.map((c) => c.end ?? now)) : now;
  const years = Math.max(maxY - minY + 1, 1);
  const plotW = W - 2 * PAD;
  const x = (year: number) => PAD + ((year - minY) / years) * plotW;

  // xếp thanh vào hàng: hàng đầu tiên còn trống tại thời điểm bắt đầu
  let y = 0;
  const lanes = LANES.map((lane) => {
    const stations = dated.filter((c) => c.kind === lane.kind).sort((a, b) => a.start! - b.start!);
    if (stations.length === 0) return null;
    const rowEnd: number[] = [];
    const bars: Bar[] = stations.map((s) => {
      const end = Math.max((s.end ?? now) + 1, s.start! + 1);
      let row = rowEnd.findIndex((e) => e <= s.start!);
      if (row === -1) row = rowEnd.length;
      rowEnd[row] = end;
      return { s, x: x(s.start!), w: x(end) - x(s.start!), row, open: s.end === null };
    });
    const top = y;
    y += LANE_HEAD + rowEnd.length * (ROW_H + ROW_GAP) + LANE_GAP;
    return { ...lane, top, bars };
  }).filter((l) => l !== null);
  const plotH = y;
  const height = plotH + AXIS_H;

  const step = tickStep(years);
  const ticks = Array.from({ length: years }, (_, i) => minY + i);

  const showTip = (e: MouseEvent, s: CareerStation) => {
    const box = e.currentTarget.closest(".timeline")!.getBoundingClientRect();
    setTip({ x: e.clientX - box.left, y: e.clientY - box.top - 10, text: describe(s) });
  };

  return (
    <div className="timeline">
      {dated.length > 0 && (
        <svg viewBox={`0 0 ${W} ${height}`} role="img" aria-label="Dòng thời gian sự nghiệp">
          <defs>
            {LANES.map((l) => (
              <linearGradient key={l.kind} id={`tl-fade-${l.kind}`} x1="0" x2="1" y1="0" y2="0">
                <stop offset="0" style={{ stopColor: l.color }} stopOpacity="1" />
                <stop offset="1" style={{ stopColor: l.color }} stopOpacity="0.3" />
              </linearGradient>
            ))}
            <pattern id="tl-loan" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="3" height="6" fill="rgba(255,255,255,0.4)" />
            </pattern>
          </defs>
          {ticks.map((t) => (
            <line key={t} className="tl-grid" x1={x(t)} x2={x(t)} y1={0} y2={plotH} />
          ))}
          {lanes.map((lane) => (
            <g key={lane.kind}>
              <text className="tl-lane" x={PAD} y={lane.top + 11}>
                {lane.label}
              </text>
              {lane.bars.map(({ s, x: bx, w, row, open }) => {
                const by = lane.top + LANE_HEAD + row * (ROW_H + ROW_GAP);
                const name = shortTeamName(s.team?.label ?? "?");
                const fit = Math.floor((w - 8) / CHAR_W);
                const text = fit >= 3 ? (name.length > fit ? `${name.slice(0, fit - 1)}…` : name) : "";
                const bw = Math.max(w - 1, 2);
                return (
                  <g
                    key={s.station}
                    className={`tl-bar${s.team ? " link" : ""}`}
                    onMouseMove={(e) => showTip(e, s)}
                    onMouseLeave={() => setTip(null)}
                    onClick={() => s.team && navigate(`/entity/${encodeURIComponent(s.team.id)}`)}
                  >
                    <rect className="tl-fill" x={bx} y={by} width={bw} height={ROW_H} rx={4} style={{ fill: open ? `url(#tl-fade-${lane.kind})` : lane.color }} />
                    {s.onLoan && <rect x={bx} y={by} width={bw} height={ROW_H} rx={4} fill="url(#tl-loan)" />}
                    {text && (
                      <text className="tl-text" x={bx + 5} y={by + 14.5}>
                        {text}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          ))}
          {ticks
            .filter((t) => (t - minY) % step === 0)
            .map((t) => (
              <text key={t} className="tl-axis" x={x(t) + plotW / years / 2} y={plotH + 12}>
                {t}
              </text>
            ))}
        </svg>
      )}
      {tip && (
        <div className="tl-tip" style={{ left: tip.x, top: tip.y }}>
          {tip.text}
        </div>
      )}
      {unknown.length > 0 && (
        <p className="tl-unknown">
          <strong>Không rõ năm:</strong>{" "}
          {unknown.map((s) => (
            <span key={s.station}>{s.team ? <EntityLink node={s.team} text={shortTeamName(s.team.label)} /> : "?"}</span>
          ))}
        </p>
      )}
      <p className="muted small" style={{ margin: "8px 0 0" }}>
        Thanh mờ dần = đến nay · sọc chéo = cho mượn · bấm một thanh để mở trang đội.
      </p>
    </div>
  );
}

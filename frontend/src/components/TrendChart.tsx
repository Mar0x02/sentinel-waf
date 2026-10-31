import { useMemo, useState } from "react";
import type { TrendPoint } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";

const WIDTH = 760;
const HEIGHT = 220;
const PAD = { top: 16, right: 16, bottom: 28, left: 36 };

export function TrendChart({ data }: { data: TrendPoint[] }) {
  const { t } = useLanguage();
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const plot = useMemo(() => {
    if (data.length === 0) return null;
    const innerW = WIDTH - PAD.left - PAD.right;
    const innerH = HEIGHT - PAD.top - PAD.bottom;
    const maxTotal = Math.max(1, ...data.map((d) => d.total));

    const x = (i: number) =>
      PAD.left + (data.length === 1 ? innerW / 2 : (i / (data.length - 1)) * innerW);
    const y = (v: number) => PAD.top + innerH - (v / maxTotal) * innerH;

    const totalPath = data.map((d, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(d.total)}`).join(" ");
    const blockedPath = data
      .map((d, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(d.blocked)}`)
      .join(" ");

    return { x, y, totalPath, blockedPath, maxTotal };
  }, [data]);

  if (!plot || data.length === 0) {
    return <p className="muted">{t("trend.noData")}</p>;
  }

  const hovered = hoverIdx !== null ? data[hoverIdx] : null;

  return (
    <div style={{ position: "relative" }}>
      <div className="legend">
        <span className="legend-item">
          <span className="legend-swatch" style={{ background: "var(--series-1)" }} />
          {t("trend.totalRequests")}
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ background: "var(--series-2)" }} />
          {t("trend.blocked")}
        </span>
      </div>
      <svg
        width="100%"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={t("trend.ariaLabel")}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const px = ((e.clientX - rect.left) / rect.width) * WIDTH;
          const innerW = WIDTH - PAD.left - PAD.right;
          const ratio = Math.min(1, Math.max(0, (px - PAD.left) / innerW));
          const idx = Math.round(ratio * (data.length - 1));
          setHoverIdx(idx);
        }}
        onMouseLeave={() => setHoverIdx(null)}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <line
            key={f}
            x1={PAD.left}
            x2={WIDTH - PAD.right}
            y1={PAD.top + f * (HEIGHT - PAD.top - PAD.bottom)}
            y2={PAD.top + f * (HEIGHT - PAD.top - PAD.bottom)}
            stroke="var(--gridline)"
            strokeWidth={1}
          />
        ))}
        <path d={plot.totalPath} fill="none" stroke="var(--series-1)" strokeWidth={2} strokeLinecap="round" />
        <path d={plot.blockedPath} fill="none" stroke="var(--series-2)" strokeWidth={2} strokeLinecap="round" />

        {hoverIdx !== null && (
          <line
            x1={plot.x(hoverIdx)}
            x2={plot.x(hoverIdx)}
            y1={PAD.top}
            y2={HEIGHT - PAD.bottom}
            stroke="var(--baseline)"
            strokeWidth={1}
          />
        )}
      </svg>
      {hovered && hoverIdx !== null && (
        <div
          style={{
            position: "absolute",
            left: `min(${(plot.x(hoverIdx) / WIDTH) * 100}%, calc(100% - 160px))`,
            top: 8,
            background: "var(--text-primary)",
            color: "var(--surface-1)",
            padding: "6px 10px",
            borderRadius: 6,
            fontSize: 12,
            pointerEvents: "none",
            whiteSpace: "nowrap",
          }}
        >
          <div className="muted" style={{ color: "var(--text-muted)" }}>
            {hovered.bucket}
          </div>
          <div>
            <strong>{hovered.total}</strong> {t("trend.total")}
          </div>
          <div>
            <strong>{hovered.blocked}</strong> {t("trend.blockedWord")}
          </div>
        </div>
      )}
    </div>
  );
}

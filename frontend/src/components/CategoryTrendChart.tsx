import { ArrowUpRight } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { CategorySeries, CategoryTrend } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";
import { smoothPath } from "../lib/smoothPath";

const WIDTH = 760;
const HEIGHT = 240;
const PAD = { top: 16, right: 16, bottom: 28, left: 36 };

// Fixed category -> color slot, in a stable priority order (the 8-hue
// categorical palette validated with scripts/validate_palette.js from the
// dataviz skill, dark-mode steps, checked against this app's --surface-1
// card background). Assignment never changes based on which categories are
// currently present/visible - "color follows the entity, never its rank".
// Anything not in this list folds into a single gray "Other" series rather
// than generating a 9th hue.
export const CATEGORY_COLORS: Record<string, string> = {
  XSS: "#3987e5",
  "SQL Injection": "#d95926",
  "Protocol Enforcement": "#199e70",
  "Remote Code Execution": "#c98500",
  "Local File Inclusion": "#d55181",
  "Remote File Inclusion": "#008300",
  "Information Disclosure": "#9085e9",
  "Generic Injection": "#e66767",
};
const OTHER_LABEL = "Other";
const OTHER_COLOR = "#70708f"; // var(--text-muted)

function formatDay(bucket: string, lang: string): string {
  const d = new Date(`${bucket}T00:00:00`);
  return d.toLocaleDateString(lang === "id" ? "id-ID" : "en-US", { day: "numeric", month: "short" });
}

function foldOthers(series: CategorySeries[], dayCount: number): CategorySeries[] {
  const known = series.filter((s) => s.category in CATEGORY_COLORS);
  const unknown = series.filter((s) => !(s.category in CATEGORY_COLORS));
  if (unknown.length === 0) return known;
  const otherCounts = Array(dayCount).fill(0);
  for (const s of unknown) {
    s.counts.forEach((c, i) => {
      otherCounts[i] += c;
    });
  }
  return [...known, { category: OTHER_LABEL, counts: otherCounts }];
}

export function CategoryTrendChart({ data }: { data: CategoryTrend }) {
  const { t, lang } = useLanguage();
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const series = useMemo(() => foldOthers(data.series, data.buckets.length), [data]);
  const visible = series.filter((s) => !hidden.has(s.category));

  const plot = useMemo(() => {
    const n = data.buckets.length;
    if (n === 0) return null;
    const innerW = WIDTH - PAD.left - PAD.right;
    const innerH = HEIGHT - PAD.top - PAD.bottom;
    const maxCount = Math.max(1, ...visible.flatMap((s) => s.counts));
    const x = (i: number) => PAD.left + (n === 1 ? innerW / 2 : (i / (n - 1)) * innerW);
    const y = (v: number) => PAD.top + innerH - (v / maxCount) * innerH;
    return { x, y, n };
  }, [data.buckets.length, visible]);

  // Thins the day labels so they never collide - rough budget of ~42px per
  // "2 Nov"-style label, always keeping the first and last day regardless
  // of step so the range's edges are never unlabeled.
  const labelIndices = useMemo(() => {
    const n = data.buckets.length;
    if (n === 0) return [];
    const maxLabels = Math.max(1, Math.floor((WIDTH - PAD.left - PAD.right) / 42));
    const step = Math.max(1, Math.ceil(n / maxLabels));
    const indices = new Set<number>();
    for (let i = 0; i < n; i += step) indices.add(i);
    indices.add(n - 1);
    return [...indices].sort((a, b) => a - b);
  }, [data.buckets.length]);

  function toggle(category: string) {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      return next;
    });
  }

  if (series.length === 0 || !plot) {
    return <p className="muted">{t("common.noData")}</p>;
  }

  const hoveredDate = hoverIdx !== null ? data.buckets[hoverIdx] : null;
  // The true day total - every category, including ones currently hidden
  // from the chart via the legend, since unchecking a series is a display
  // preference, not a claim that those attacks didn't happen.
  const hoveredTotal = hoverIdx !== null ? series.reduce((sum, s) => sum + s.counts[hoverIdx], 0) : 0;

  return (
    <div>
      <div style={{ position: "relative" }}>
        <svg
          width="100%"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-label={t("dashboard.topCategories")}
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const px = ((e.clientX - rect.left) / rect.width) * WIDTH;
            const innerW = WIDTH - PAD.left - PAD.right;
            const ratio = Math.min(1, Math.max(0, (px - PAD.left) / innerW));
            setHoverIdx(Math.round(ratio * (plot.n - 1)));
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

          {visible.map((s) => {
            const color = s.category === OTHER_LABEL ? OTHER_COLOR : CATEGORY_COLORS[s.category];
            const path = smoothPath(s.counts.map((v, i) => [plot.x(i), plot.y(v)]));
            return (
              <g key={s.category}>
                <path d={path} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
                {s.counts.map((v, i) => (
                  <circle key={i} cx={plot.x(i)} cy={plot.y(v)} r={4} fill={color} stroke="var(--surface-1)" strokeWidth={2} />
                ))}
              </g>
            );
          })}

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

          {labelIndices.map((i) => (
            <text
              key={i}
              x={plot.x(i)}
              y={HEIGHT - PAD.bottom + 16}
              textAnchor={i === 0 ? "start" : i === plot.n - 1 ? "end" : "middle"}
              fontSize={10}
              fill="var(--text-muted)"
            >
              {formatDay(data.buckets[i], lang)}
            </text>
          ))}
        </svg>

        {hoveredDate && hoverIdx !== null && (
          <div
            style={{
              position: "absolute",
              left: `min(${(plot.x(hoverIdx) / WIDTH) * 100}%, calc(100% - 180px))`,
              top: 8,
              background: "var(--text-primary)",
              color: "var(--surface-1)",
              padding: "8px 10px",
              borderRadius: 6,
              fontSize: 12,
              pointerEvents: "none",
              whiteSpace: "nowrap",
            }}
          >
            <div style={{ color: "var(--text-muted)", marginBottom: 4 }}>{formatDay(hoveredDate, lang)}</div>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 6 }}>
              {hoveredTotal} {t("dashboard.totalAttacksWord")}
            </div>
            {visible.map((s) => {
              const color = s.category === OTHER_LABEL ? OTHER_COLOR : CATEGORY_COLORS[s.category];
              return (
                <div key={s.category} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ width: 10, height: 2, background: color, display: "inline-block", borderRadius: 2 }} />
                  <strong>{s.counts[hoverIdx]}</strong>
                  <span>{s.category}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="legend" style={{ flexWrap: "wrap", marginTop: 10, marginBottom: 0 }}>
        {series.map((s) => {
          const color = s.category === OTHER_LABEL ? OTHER_COLOR : CATEGORY_COLORS[s.category];
          const total = s.counts.reduce((a, b) => a + b, 0);
          const isHidden = hidden.has(s.category);
          return (
            <label
              key={s.category}
              className="legend-item"
              style={{ cursor: "pointer", opacity: isHidden ? 0.45 : 1 }}
            >
              <input type="checkbox" checked={!isHidden} onChange={() => toggle(s.category)} style={{ margin: 0 }} />
              <span className="legend-swatch" style={{ background: color }} />
              {s.category} <span className="muted">({total})</span>
              {s.category !== OTHER_LABEL && (
                <Link
                  to={`/logs?category=${encodeURIComponent(s.category)}`}
                  onClick={(e) => e.stopPropagation()}
                  title={t("dashboard.viewInLogs")}
                  className="legend-logs-link"
                >
                  <ArrowUpRight size={12} />
                </Link>
              )}
            </label>
          );
        })}
      </div>
    </div>
  );
}

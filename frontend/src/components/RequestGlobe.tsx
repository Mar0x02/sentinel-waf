import { useEffect, useRef, useState } from "react";
import Globe, { GlobeMethods } from "react-globe.gl";
import { api, CountryCount } from "../api/client";
import { useLanguage } from "../i18n/LanguageContext";

// Copied from three-globe's own example assets (frontend/public/earth-dark.jpg)
// rather than imported as a package specifier - three-globe's package.json
// "exports" map doesn't list ./example/img/*, so Vite/esbuild refuse to
// resolve a deep import from the installed package (confirmed: "Missing
// './example/img/earth-dark.jpg' specifier in 'three-globe' package").
// Served from public/ as a plain static asset instead.
const earthDarkUrl = "/earth-dark.jpg";

// There's no single real "server location" to point arcs at - this is a
// self-hosted dashboard, not a service with one known datacenter. This is
// a fixed illustrative vantage point (arcs show "a request came from
// here", not a literal network path), not a claim about where the WAF
// physically runs.
const ORIGIN = { lat: 20, lng: 10 };

const POLL_INTERVAL_MS = 8000;
// How long a newly-appeared arc/ring stays on screen before being swept
// out of state - keeps the animation list from growing forever on a busy
// site while still reading as "something just happened".
const EFFECT_LIFETIME_MS = 3000;

interface ArcDatum {
  id: string;
  startLat: number;
  startLng: number;
  endLat: number;
  endLng: number;
  color: string;
}

interface RingDatum {
  id: string;
  lat: number;
  lng: number;
}

export function RequestGlobe() {
  const { t } = useLanguage();
  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);
  const previousCounts = useRef<Map<string, number>>(new Map());

  const [countries, setCountries] = useState<CountryCount[]>([]);
  const [arcs, setArcs] = useState<ArcDatum[]>([]);
  const [rings, setRings] = useState<RingDatum[]>([]);
  const [size, setSize] = useState({ width: 560, height: 420 });

  useEffect(() => {
    function updateSize() {
      if (containerRef.current) {
        setSize({ width: containerRef.current.clientWidth, height: 420 });
      }
    }
    updateSize();
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      let data: CountryCount[];
      try {
        data = await api.statsCountries(60);
      } catch {
        return; // best-effort - dashboard's own stat tiles already surface load failures
      }
      if (cancelled) return;
      setCountries(data);

      const newArcs: ArcDatum[] = [];
      const newRings: RingDatum[] = [];
      for (const c of data) {
        const prev = previousCounts.current.get(c.country_code) ?? 0;
        // Only animate growth, not the first poll's whole baseline - the
        // first load would otherwise fire an arc for every country at
        // once, which reads as noise rather than "activity just
        // happened".
        if (prev > 0 && c.count > prev) {
          const id = `${c.country_code}-${Date.now()}`;
          const color = c.blocked_count > 0 ? "#f87171" : "#22d3ee";
          newArcs.push({ id, startLat: c.lat, startLng: c.lng, endLat: ORIGIN.lat, endLng: ORIGIN.lng, color });
          newRings.push({ id, lat: c.lat, lng: c.lng });
        }
        previousCounts.current.set(c.country_code, c.count);
      }

      if (newArcs.length > 0) {
        setArcs((prev) => [...prev, ...newArcs]);
        setRings((prev) => [...prev, ...newRings]);
        setTimeout(() => {
          if (cancelled) return;
          setArcs((prev) => prev.filter((a) => !newArcs.some((n) => n.id === a.id)));
          setRings((prev) => prev.filter((r) => !newRings.some((n) => n.id === r.id)));
        }, EFFECT_LIFETIME_MS);
      }
    }

    poll();
    const handle = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(handle);
    };
  }, []);

  useEffect(() => {
    const globe = globeRef.current;
    if (!globe) return;
    globe.pointOfView({ lat: 15, lng: 20, altitude: 2.2 });
    const controls = globe.controls();
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.35;
  }, []);

  return (
    <div className="card globe-card" ref={containerRef}>
      <h3>{t("dashboard.requestGlobe")}</h3>
      {countries.length === 0 && <p className="muted globe-waiting">{t("dashboard.globeWaiting")}</p>}
      <Globe
        ref={globeRef}
        width={size.width}
        height={size.height}
        backgroundColor="rgba(0,0,0,0)"
        globeImageUrl={earthDarkUrl}
        atmosphereColor="#22d3ee"
        atmosphereAltitude={0.16}
        pointsData={countries as unknown as object[]}
        pointLat="lat"
        pointLng="lng"
        pointColor={(d) => ((d as CountryCount).blocked_count > 0 ? "#f87171" : "#22d3ee")}
        pointAltitude={(d) => Math.min(0.3, 0.02 + (d as CountryCount).count * 0.01)}
        pointRadius={0.45}
        pointLabel={(d) => {
          const c = d as CountryCount;
          return `${c.country_name}: ${c.count} ${t("dashboard.requests")}, ${c.blocked_count} ${t("dashboard.blocked")}`;
        }}
        arcsData={arcs as unknown as object[]}
        arcColor="color"
        arcDashLength={0.4}
        arcDashGap={0.2}
        arcDashAnimateTime={1400}
        arcStroke={0.5}
        ringsData={rings as unknown as object[]}
        ringColor={() => (frac: number) => `rgba(34, 211, 238, ${1 - frac})`}
        ringMaxRadius={5}
        ringPropagationSpeed={3}
        ringRepeatPeriod={700}
      />
    </div>
  );
}

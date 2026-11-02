import { Calendar, Check } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export function DateRangePicker({
  value,
  onChange,
  options,
}: {
  value: number;
  onChange: (days: number) => void;
  options: { days: number; label: string }[];
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  const current = options.find((o) => o.days === value) ?? options[0];

  return (
    <div className="date-range-picker" ref={ref}>
      <button type="button" className="btn date-range-trigger" onClick={() => setOpen((v) => !v)}>
        <Calendar size={14} />
        {current.label}
      </button>
      {open && (
        <div className="date-range-menu" role="menu">
          {options.map((o) => (
            <button
              key={o.days}
              type="button"
              className="date-range-row"
              role="menuitemradio"
              aria-checked={o.days === value}
              onClick={() => {
                onChange(o.days);
                setOpen(false);
              }}
            >
              <span className="date-range-check">{o.days === value && <Check size={16} strokeWidth={3} />}</span>
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

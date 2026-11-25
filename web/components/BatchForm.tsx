"use client";
import type { Batch, Transport, Zone } from "@/lib/api";
import s from "./BatchForm.module.css";

type NumKey = "distance_km" | "tiffins" | "handovers" | "wait_at_station_min" | "temp_c" | "rider_age";

const NUMBERS: { key: NumKey; label: string; unit?: string; step: number; min: number; max: number; slider?: [number, number] }[] = [
  { key: "distance_km", label: "Distance", unit: "km", step: 0.1, min: 0.1, max: 35, slider: [0.5, 35] },
  { key: "tiffins", label: "Tiffins", step: 1, min: 1, max: 200, slider: [1, 80] },
  { key: "handovers", label: "Handovers", step: 1, min: 0, max: 8, slider: [0, 8] },
  { key: "wait_at_station_min", label: "Station wait", unit: "min", step: 0.5, min: 0, max: 120, slider: [0, 40] },
  { key: "temp_c", label: "Noon temperature", unit: "°C", step: 0.5, min: 5, max: 55, slider: [5, 50] },
  { key: "rider_age", label: "Runner's age", unit: "years", step: 1, min: 14, max: 90 },
];

const TRANSPORT: [Transport, string][] = [["bicycle", "Bicycle"], ["local_train", "Local train"], ["scooter", "Scooter"]];
const ZONES: [Zone, string][] = [["Central", "Central"], ["Suburb", "Suburb"], ["Old City", "Old City"]];

interface Props {
  batch: Batch;
  errors: Partial<Record<keyof Batch, string>>;
  onChange: (patch: Partial<Batch>) => void;
  pickup: string;
  onPickup: (v: string) => void;
}

function Segmented<T extends string>({ id, label, value, options, onPick, error }:
  { id: string; label: string; value: T; options: [T, string][]; onPick: (v: T) => void; error?: string }) {
  return (
    <div className={s.field}>
      <span className={s.label} id={id}>{label}</span>
      <div className={s.seg} role="group" aria-labelledby={id}>
        {options.map(([v, text]) => (
          <button key={v} type="button" aria-pressed={value === v} onClick={() => onPick(v)}>{text}</button>
        ))}
      </div>
      {error && <p className={s.err}>{error}</p>}
    </div>
  );
}

export default function BatchForm({ batch, errors, onChange, pickup, onPickup }: Props) {
  const set = (key: NumKey, raw: string) => {
    const v = raw === "" ? null : key === "tiffins" || key === "handovers" || key === "rider_age" ? parseInt(raw, 10) : parseFloat(raw);
    onChange({ [key]: Number.isNaN(v) ? null : v } as Partial<Batch>);
  };
  return (
    <div>
      {NUMBERS.map(f => (
        <div key={f.key} className={`${s.field} ${errors[f.key] ? s.bad : ""}`}>
          <label htmlFor={f.key}>{f.label} {f.unit && <span className={s.unit}>{f.unit}</span>}</label>
          <input id={f.key} className={s.num} type="number" step={f.step} min={f.min} max={f.max}
            value={batch[f.key] ?? ""} onChange={e => set(f.key, e.target.value)}
            aria-invalid={!!errors[f.key]} aria-describedby={errors[f.key] ? `${f.key}-err` : undefined} />
          {f.slider && (
            <input className={s.range} type="range" aria-label={`${f.label} slider`} step={f.step}
              min={f.slider[0]} max={f.slider[1]} value={batch[f.key] ?? f.slider[0]}
              onChange={e => set(f.key, e.target.value)} />
          )}
          {errors[f.key] && <p className={s.err} id={`${f.key}-err`}>{errors[f.key]}</p>}
        </div>
      ))}
      <Segmented id="transport-l" label="Transport" value={batch.transport} options={TRANSPORT}
        onPick={v => onChange({ transport: v })} error={errors.transport} />
      <Segmented id="zone-l" label="Route zone" value={batch.route_zone} options={ZONES}
        onPick={v => onChange({ route_zone: v })} error={errors.route_zone} />
      <div className={s.field}>
        <label htmlFor="pickup">Pick-up time</label>
        <input id="pickup" className={s.num} type="time" value={pickup} onChange={e => onPickup(e.target.value)} />
      </div>
    </div>
  );
}

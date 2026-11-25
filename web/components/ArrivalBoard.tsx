"use client";
import type { Batch } from "@/lib/api";
import RouteStrip from "./RouteStrip";
import s from "./ArrivalBoard.module.css";

const MODE = { bicycle: "Bicycle", local_train: "Local train", scooter: "Scooter" } as const;

function arrival(pickup: string, minutes: number) {
  const [h, m] = (pickup || "11:30").split(":").map(Number);
  const t = new Date(2026, 0, 1, h, m + Math.round(minutes));
  const hh = t.getHours() % 12 || 12, mm = String(t.getMinutes()).padStart(2, "0");
  return <>{hh}:{mm}<small>{t.getHours() < 12 ? "am" : "pm"}</small></>;
}

export default function ArrivalBoard({ batch, minutes, pickup, problem, pending }:
  { batch: Batch; minutes: number | null; pickup: string; problem?: string; pending: boolean }) {
  const n = batch.handovers ?? 0;
  return (
    <div className={s.board} aria-live="polite">
      <div className={pending ? s.stale : undefined}>
        <p className={s.when}>Lunch reaches the desk at</p>
        <p className={s.clock}>{minutes === null ? "--:--" : arrival(pickup, minutes)}</p>
        <p className={s.mins}>
          {problem ? <span className={s.problem}>{problem}</span>
            : minutes === null ? "Working out the relay"
            : <><b>{Math.round(minutes)} minutes</b> after a {pickup} pick-up</>}
        </p>
      </div>
      <div className={s.route}>
        <RouteStrip mode={batch.transport} handovers={n} minutes={minutes} />
        <div className={s.legend}>
          <span>Home kitchen</span>
          <span>{MODE[batch.transport]}, {batch.distance_km ?? "?"} km, {n} handover{n === 1 ? "" : "s"}</span>
          <span>Office desk</span>
        </div>
      </div>
    </div>
  );
}

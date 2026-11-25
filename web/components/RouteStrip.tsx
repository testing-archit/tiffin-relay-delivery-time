"use client";
import { useEffect, useRef } from "react";
import type { Transport } from "@/lib/api";

const X0 = 40, X1 = 600, Y = 58;

function Track({ mode }: { mode: Transport }) {
  if (mode === "local_train") {
    return (
      <g>
        <line x1={X0} y1={Y - 5} x2={X1} y2={Y - 5} stroke="#B9C6CD" strokeWidth={2} />
        <line x1={X0} y1={Y + 5} x2={X1} y2={Y + 5} stroke="#B9C6CD" strokeWidth={2} />
        {Array.from({ length: 40 }, (_, i) => (
          <line key={i} x1={X0 + i * 14 + 4} y1={Y - 8} x2={X0 + i * 14 + 4} y2={Y + 8} stroke="#55656F" strokeWidth={2} />
        ))}
      </g>
    );
  }
  if (mode === "bicycle") {
    return <line x1={X0} y1={Y} x2={X1} y2={Y} stroke="#B9C6CD" strokeWidth={3} strokeDasharray="4 8" strokeLinecap="round" />;
  }
  return <line x1={X0} y1={Y} x2={X1} y2={Y} stroke="#B9C6CD" strokeWidth={6} strokeLinecap="round" />;
}

// The relay: home kitchen on the left, office desk on the right, one tiffin
// carrier for every handover. A runner dot travels the route on each new estimate.
export default function RouteStrip({ mode, handovers, minutes }: { mode: Transport; handovers: number; minutes: number | null }) {
  const runner = useRef<SVGCircleElement>(null);
  const n = Math.max(0, Math.min(8, handovers));

  useEffect(() => {
    if (minutes === null || !runner.current || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const a = runner.current.animate(
      [{ transform: "translateX(0px)" }, { transform: `translateX(${X1 - X0}px)` }],
      { duration: 1100, easing: "cubic-bezier(.4,0,.2,1)", fill: "forwards" },
    );
    return () => a.cancel();
  }, [minutes, mode, n]);

  return (
    <svg viewBox="0 0 640 110" role="img" aria-label={`Relay route with ${n} handovers`}>
      <Track mode={mode} />
      {Array.from({ length: n }, (_, k) => {
        const x = X0 + ((X1 - X0) * (k + 1)) / (n + 1);
        return (
          <g key={k}>
            <g transform={`translate(${x - 11},${Y - 15})`}>
              <rect width={22} height={30} rx={4} fill="#F4F6F7" stroke="#1C2830" strokeWidth={2} />
              <rect width={22} height={7} rx={3} fill="#F2B705" />
              <text x={11} y={24} textAnchor="middle" fontFamily="var(--display)" fontWeight={700} fontSize={13} fill="#1C2830">{k + 1}</text>
            </g>
            <text x={x} y={Y + 34} textAnchor="middle" fontSize={11} fill="#B9C6CD">handover</text>
          </g>
        );
      })}
      <circle cx={X0} cy={Y} r={9} fill="#1C2830" stroke="#F4F6F7" strokeWidth={3} />
      <circle cx={X1} cy={Y} r={9} fill="#F2B705" stroke="#F4F6F7" strokeWidth={3} />
      <text x={X0} y={Y - 20} textAnchor="middle" fontSize={12} fill="#B9C6CD">0 min</text>
      {minutes !== null && <text x={X1} y={Y - 20} textAnchor="middle" fontSize={12} fill="#F2B705">{Math.round(minutes)} min</text>}
      <circle ref={runner} cx={X0} cy={Y} r={6} fill="#F2B705" />
    </svg>
  );
}

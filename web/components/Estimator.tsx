"use client";
import { useEffect, useState, type ReactNode } from "react";
import BatchForm from "./BatchForm";
import { api, ApiError, DEFAULT_BATCH, type Batch, type Explanation, type Health } from "@/lib/api";
import { fieldErrors } from "@/lib/errors";

export default function Estimator({ brand }: { brand: ReactNode }) {
  const [batch, setBatch] = useState<Batch>(DEFAULT_BATCH);
  const [pickup, setPickup] = useState("11:30");
  const [health, setHealth] = useState<Health | null | "down">(null);
  const [result, setResult] = useState<Explanation | null>(null);
  const [errors, setErrors] = useState<Partial<Record<keyof Batch, string>>>({});

  useEffect(() => { api<Health>("health").then(setHealth, () => setHealth("down")); }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      api<Explanation>("explain", batch, ctrl.signal).then(
        r => { setResult(r); setErrors({}); },
        e => { if (e instanceof ApiError && e.status === 422) { setErrors(fieldErrors(e.detail)); setResult(null); } },
      );
    }, 180);
    return () => { clearTimeout(t); ctrl.abort(); };
  }, [batch]);

  const update = (patch: Partial<Batch>) => setBatch(b => ({ ...b, ...patch }));
  const up = health && health !== "down";

  return (
    <>
      <header className="top">
        {brand}
        <div className="status" aria-live="polite">
          <span className={`chip ${health === null ? "" : up ? "on" : "off"}`}><i />{up ? `Model v${health.model_version}` : health === "down" ? "Model offline" : "Model loading"}</span>
          <span className={`chip ${up && health.ai_enabled ? "on" : "off"}`}><i />{up && health.ai_enabled ? "Gemini on" : "Gemini off"}</span>
        </div>
      </header>
      <main className="layout">
        <section className="card" aria-labelledby="batch-title">
          <h2 id="batch-title">The batch</h2>
          <BatchForm batch={batch} errors={errors} onChange={update} pickup={pickup} onPickup={setPickup} />
        </section>
        <section aria-label="Estimate">
          <p>{result ? `${result.delivery_min} min` : ""}</p>
        </section>
      </main>
    </>
  );
}

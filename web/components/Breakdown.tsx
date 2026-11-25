"use client";
import { useState } from "react";
import { api, ApiError, type Batch, type Explanation } from "@/lib/api";
import { hasDevanagari, speak } from "@/lib/speech";
import s from "./Breakdown.module.css";

const LANGS: [string, string][] = [
  ["English", "English"],
  ["Hindi (Devanagari script)", "हिन्दी"],
  ["Hinglish (Hindi in Roman letters mixed with English)", "Hinglish"],
];

export default function Breakdown({ result, batch, aiOn }: { result: Explanation | null; batch: Batch; aiOn: boolean }) {
  const [lang, setLang] = useState(LANGS[0][0]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  const explain = async () => {
    setBusy(true); setText("Gemini is writing the explanation");
    try {
      const r = await api<{ text: string }>("ai/explain", { batch, language: lang });
      setText(r.text);
    } catch (e) {
      setText(e instanceof ApiError && e.status === 422 ? "Fix the highlighted fields first." : String((e as Error).message));
    }
    setBusy(false);
  };

  const parts = result?.parts ?? [];
  const max = Math.max(4, ...parts.map(p => Math.abs(p.minutes)));
  return (
    <div className="card">
      <h2>Why this time</h2>
      <div className={s.axis} aria-hidden="true"><span /><span>saves minutes</span><span>adds minutes</span><span /></div>
      <div className={s.bars}>
        {parts.map(p => {
          const fill = <span className={s.fill} style={{ width: `${(Math.abs(p.minutes) / max) * 100}%` }} />;
          return (
            <div key={p.feature} className={s.bar}>
              <span>{p.label}</span>
              <span className={s.left}>{p.minutes < 0 && fill}</span>
              <span className={s.right}>{p.minutes >= 0 && fill}</span>
              <span className={s.val}>{p.minutes > 0 ? "+" : ""}{p.minutes.toFixed(1)}</span>
            </div>
          );
        })}
      </div>
      {result && <p className={s.base}>A typical batch takes about {Math.round(result.typical_min)} minutes. The bars show how this one differs.</p>}

      <div className={s.explain}>
        <div className={s.row}>
          <label htmlFor="lang" className="sr">Language</label>
          <select id="lang" value={lang} onChange={e => setLang(e.target.value)}>
            {LANGS.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
          </select>
          <button className="btn ghost" type="button" onClick={explain} disabled={!aiOn || busy || !result}>Explain in plain words</button>
          {text && !busy && (
            <button className="icon" type="button" aria-label="Read the explanation aloud" title="Read it aloud"
              onClick={() => speak(text, lang.startsWith("English") ? "en-IN" : "hi-IN")}>
              <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 9v6h4l5 5V4L7 9H3Zm13.5 3A4.5 4.5 0 0 0 14 8v8a4.5 4.5 0 0 0 2.5-4Z" /></svg>
            </button>
          )}
        </div>
        {!aiOn && <p className="hint" style={{ marginTop: 8 }}>Gemini is off. Set GEMINI_API_KEY on the API to turn on explanations.</p>}
        <p className={s.out} aria-live="polite" lang={hasDevanagari(text) ? "hi" : undefined}>{text}</p>
      </div>
    </div>
  );
}

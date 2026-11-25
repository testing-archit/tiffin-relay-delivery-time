"use client";
import { useState } from "react";
import { api, type Batch } from "@/lib/api";
import { canListen, listen } from "@/lib/speech";
import s from "./NoteFill.module.css";

export function MicIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 15a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v7a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.9V22h2v-3.1A7 7 0 0 0 19 12Z" /></svg>;
}

// A dispatcher types or speaks a note in any language; Gemini fills the form.
export default function NoteFill({ aiOn, onFill }: { aiOn: boolean; onFill: (f: Partial<Batch>) => void }) {
  const [text, setText] = useState("");
  const [hint, setHint] = useState("Gemini reads the note and fills the fields below.");
  const [busy, setBusy] = useState(false);
  const [hearing, setHearing] = useState(false);

  const fill = async (note = text) => {
    if (!note.trim()) { setHint("Write or speak a note first."); return; }
    setBusy(true); setHint("Gemini is reading the note");
    try {
      const { fields } = await api<{ fields: Partial<Batch> }>("ai/parse", { text: note });
      const n = Object.keys(fields).length;
      onFill(fields);
      setHint(n ? `Filled ${n} field${n > 1 ? "s" : ""}. The rest keep their values.`
        : "Couldn't find batch details in that note. Try naming the distance, tiffins or transport.");
    } catch (e) { setHint(String((e as Error).message)); }
    setBusy(false);
  };

  const mic = () => {
    if (!canListen()) { setHint("This browser can't take voice input. Try Chrome or Edge."); return; }
    setHearing(true);
    listen("hi-IN", setText, (final, err) => {
      setHearing(false);
      if (err) setHint(err === "not-allowed" ? "Allow microphone access to speak the note." : "Didn't catch that. Try again.");
      else if (final) fill(final);
    });
  };

  return (
    <div className={s.note}>
      <label htmlFor="note" className="sr">Describe the batch in your own words</label>
      <textarea id="note" value={text} onChange={e => setText(e.target.value)} disabled={!aiOn}
        placeholder="Describe it in English, हिन्दी or Hinglish. For example: 45 dabbe purane shehar ke liye, local train se, 22 km, 3 handover" />
      <button type="button" className={`icon ${s.mic} ${hearing ? "live" : ""}`} onClick={mic} disabled={!aiOn}
        aria-label="Speak the note" title="Speak the note"><MicIcon /></button>
      <div className={s.row}>
        <button type="button" className="btn" onClick={() => fill()} disabled={!aiOn || busy}>Fill the form</button>
        <p className="hint" aria-live="polite">{aiOn ? hint : "Gemini is off. Set GEMINI_API_KEY on the API to fill the form from a note."}</p>
      </div>
    </div>
  );
}

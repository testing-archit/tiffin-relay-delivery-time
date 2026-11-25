"use client";
import { useEffect, useRef, useState } from "react";
import { api, type Batch, type ChatReply, type ChatTurn } from "@/lib/api";
import { canListen, hasDevanagari, listen, speak, stopSpeaking } from "@/lib/speech";
import { MicIcon } from "./NoteFill";
import s from "./ChatPanel.module.css";

type Line = { role: "user" | "model" | "note"; text: string; minutes?: number };

const SUGGESTIONS = ["Agar scooter se bhejein to kitna time?", "अगर 2 handover कम कर दें तो?", "Which transport is fastest for this batch?"];

export default function ChatPanel({ batch, onEstimate }: { batch: Batch; onEstimate: (b: Batch) => void }) {
  const [open, setOpen] = useState(false);
  const [lines, setLines] = useState<Line[]>([{ role: "model", text: "Namaste! Ask me about any batch in English, हिन्दी or Hinglish. I use the form for anything you don't mention, and I can fill it for you." }]);
  const [input, setInput] = useState("");
  const [voiceLang, setVoiceLang] = useState("hi-IN");
  const [voice, setVoice] = useState<string | null>(null); // status text while voice chat is on
  const history = useRef<ChatTurn[]>([]);
  const voiceOn = useRef(false);
  const rec = useRef<{ abort: () => void } | null>(null);
  const log = useRef<HTMLDivElement>(null);
  const batchRef = useRef(batch);
  useEffect(() => { batchRef.current = batch; }, [batch]);
  useEffect(() => { log.current?.scrollTo({ top: 1e9 }); }, [lines]);

  const add = (l: Line) => setLines(x => [...x, l]);

  async function send(text: string): Promise<string | null> {
    text = text.trim();
    if (!text) return null;
    add({ role: "user", text });
    history.current.push({ role: "user", text });
    add({ role: "note", text: "Thinking" });
    try {
      const r = await api<ChatReply>("ai/chat", { messages: history.current.slice(-20), form: batchRef.current });
      history.current.push({ role: "model", text: r.reply });
      setLines(x => [...x.slice(0, -1), { role: "model", text: r.reply, minutes: r.estimate?.delivery_min }]);
      if (r.estimate) { onEstimate(r.estimate.batch); add({ role: "note", text: "Form updated with this batch." }); }
      return r.reply;
    } catch (e) {
      setLines(x => [...x.slice(0, -1), { role: "note", text: String((e as Error).message) }]);
      return null;
    }
  }

  // Voice chat: listen -> Gemini -> speak the reply -> listen again.
  function voiceTurn() {
    if (!voiceOn.current) return;
    setVoice("Listening. Speak in Hindi, Hinglish or English");
    rec.current = listen(voiceLang, t => setVoice(t || "Listening"), async (final, err) => {
      if (!voiceOn.current) return;
      if (err === "not-allowed") { add({ role: "note", text: "Allow microphone access to talk." }); return stopVoice(); }
      if (!final) return voiceTurn();
      setVoice("Thinking");
      const reply = await send(final);
      if (!voiceOn.current) return;
      if (reply) { setVoice("Speaking"); speak(reply, voiceLang, voiceTurn); } else voiceTurn();
    });
  }
  function startVoice() {
    if (!canListen()) { add({ role: "note", text: "This browser can't do voice. Try Chrome or Edge." }); return; }
    voiceOn.current = true; voiceTurn();
  }
  function stopVoice() {
    voiceOn.current = false; rec.current?.abort(); stopSpeaking(); setVoice(null);
  }
  const close = () => { stopVoice(); setOpen(false); };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  return (
    <>
      <button className={s.fab} type="button" aria-expanded={open} aria-controls="chat" onClick={() => (open ? close() : setOpen(true))}>
        <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M4 4h16v12H7l-3 3V4Zm4 5v2h2V9H8Zm4 0v2h2V9h-2Zm4 0v2h2V9h-2Z" /></svg>
        Ask the dispatcher
      </button>
      {open && (
        <section className={s.panel} id="chat" aria-label="Dispatch assistant">
          <div className={s.head}>
            <h2>Dispatch assistant</h2>
            <label className="sr" htmlFor="voice-lang">Language you will speak in</label>
            <select id="voice-lang" value={voiceLang} onChange={e => setVoiceLang(e.target.value)}>
              <option value="hi-IN">हिन्दी / Hinglish voice</option>
              <option value="en-IN">English voice</option>
            </select>
            <button className={s.close} type="button" aria-label="Close chat" onClick={close}>×</button>
          </div>
          <div className={s.log} ref={log} aria-live="polite">
            {lines.map((l, i) => (
              <div key={i} className={`${s.msg} ${s[l.role]}`} lang={hasDevanagari(l.text) ? "hi" : undefined}>
                {l.text}
                {l.minutes !== undefined && <span className={s.est}>{Math.round(l.minutes)} min</span>}
              </div>
            ))}
          </div>
          {lines.length === 1 && (
            <div className={s.suggest}>
              {SUGGESTIONS.map(q => <button key={q} type="button" onClick={() => send(q)}>{q}</button>)}
            </div>
          )}
          {voice !== null && (
            <div className={s.voice}>
              <span className={s.wave} aria-hidden="true"><i /><i /><i /><i /></span>
              <span aria-live="polite">{voice}</span>
              <button className="btn ghost" type="button" onClick={stopVoice}>End voice chat</button>
            </div>
          )}
          <form className={s.compose} onSubmit={e => { e.preventDefault(); const v = input; setInput(""); send(v); }}>
            <label htmlFor="chat-input" className="sr">Message</label>
            <input id="chat-input" autoFocus autoComplete="off" value={input} onChange={e => setInput(e.target.value)} placeholder="Type, or press the mic to talk" />
            <button type="button" className={`icon ${voice !== null ? "live" : ""}`} onClick={() => (voice !== null ? stopVoice() : startVoice())}
              aria-label={voice !== null ? "End voice chat" : "Start voice chat"} title="Talk with the assistant"><MicIcon /></button>
            <button className="btn" type="submit">Send</button>
          </form>
        </section>
      )}
    </>
  );
}

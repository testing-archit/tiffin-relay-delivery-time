// Browser speech: recognition in (hi-IN / en-IN), synthesis out.
// Gemini Live is not available for this project's key, so voice runs on the
// browser's own speech engines and Gemini handles the thinking.

type Rec = {
  lang: string; interimResults: boolean; continuous: boolean;
  onresult: (e: { results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }) => void;
  onend: () => void; onerror: (e: { error: string }) => void;
  start: () => void; abort: () => void;
};

export const hasDevanagari = (t: string) => /[ऀ-ॿ]/.test(t);

export function canListen(): boolean {
  return typeof window !== "undefined" && !!((window as never)["SpeechRecognition"] || (window as never)["webkitSpeechRecognition"]);
}

export function listen(lang: string, onText: (t: string) => void, onEnd: (final: string, error?: string) => void): Rec {
  const Ctor = ((window as never)["SpeechRecognition"] || (window as never)["webkitSpeechRecognition"]) as new () => Rec;
  const r = new Ctor();
  r.lang = lang; r.interimResults = true; r.continuous = false;
  let final = "", failed = false;
  r.onresult = e => {
    let t = "";
    for (const res of Array.from(e.results)) { t += res[0].transcript; if (res.isFinal) final = t; }
    onText(t);
  };
  r.onerror = e => { failed = true; onEnd("", e.error); };
  r.onend = () => { if (!failed) onEnd(final); };
  r.start();
  return r;
}

export function speak(text: string, preferLang: string, onEnd?: () => void) {
  if (!("speechSynthesis" in window)) { onEnd?.(); return; }
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  const want = hasDevanagari(text) || preferLang === "hi-IN" ? "hi-IN" : "en-IN";
  const voices = speechSynthesis.getVoices();
  u.voice = voices.find(v => v.lang === want) ?? voices.find(v => v.lang.startsWith(want.slice(0, 2))) ?? null;
  u.lang = want; u.rate = 1.02;
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  speechSynthesis.speak(u);
}

export function stopSpeaking() {
  if (typeof window !== "undefined" && "speechSynthesis" in window) speechSynthesis.cancel();
}

import type { Batch, FieldError } from "./api";

// Turn FastAPI 422 details into one plain sentence per field.
export function fieldErrors(detail: unknown): Partial<Record<keyof Batch, string>> {
  const out: Partial<Record<keyof Batch, string>> = {};
  if (!Array.isArray(detail)) return out;
  for (const d of detail as FieldError[]) {
    const name = d.loc[d.loc.length - 1] as keyof Batch;
    out[name] = friendly(name, d);
  }
  return out;
}

function friendly(name: keyof Batch, d: FieldError): string {
  if (name === "distance_km" && d.type.includes("less_than")) return "The union never runs routes longer than 35 km.";
  if (name === "temp_c" && d.type.includes("greater_than")) return "Below 5 °C is always a typing mistake. Check the reading.";
  if (d.type === "missing" || d.type.includes("parsing") || d.type.includes("type")) return "Enter a number.";
  return d.msg.replace(/^Input should be/, "Should be");
}

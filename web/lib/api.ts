export type Transport = "bicycle" | "local_train" | "scooter";
export type Zone = "Central" | "Suburb" | "Old City";

export interface Batch {
  distance_km: number | null;
  tiffins: number | null;
  handovers: number | null;
  wait_at_station_min: number | null;
  rider_age: number | null;
  temp_c: number | null;
  transport: Transport;
  route_zone: Zone;
}

export interface Part { feature: keyof Batch; label: string; minutes: number }
export interface Explanation { delivery_min: number; model_version: string; typical_min: number; parts: Part[] }
export interface FieldError { loc: (string | number)[]; msg: string; type: string }
export interface Health { status: string; model_version: string; ai_enabled: boolean }
export interface ChatTurn { role: "user" | "model"; text: string }
export interface ChatReply { reply: string; estimate: { batch: Batch; delivery_min: number } | null }

export const DEFAULT_BATCH: Batch = {
  distance_km: 12, tiffins: 35, handovers: 3, wait_at_station_min: 12,
  rider_age: 38, temp_c: 30, transport: "local_train", route_zone: "Old City",
};

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
  }
}

export async function api<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`/api/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, (data as { detail?: unknown }).detail);
  return data as T;
}

// Forwards browser calls to the FastAPI service. The API address is read at
// request time, so one image works locally (localhost:8000) and in Kubernetes
// (http://mp098-svc).
import type { NextRequest } from "next/server";

const ALLOWED = new Set(["health", "predict", "explain", "ai/parse", "ai/explain", "ai/chat"]);

async function forward(req: NextRequest, ctx: RouteContext<"/api/[...path]">) {
  const path = (await ctx.params).path.join("/");
  if (!ALLOWED.has(path)) return Response.json({ detail: "Not found" }, { status: 404 });

  const base = process.env.API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${base}/${path}`, {
      method: req.method,
      headers: { "content-type": "application/json" },
      body: req.method === "POST" ? await req.text() : undefined,
      cache: "no-store",
    });
    return new Response(await res.text(), {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return Response.json({ detail: "The prediction service is not reachable." }, { status: 502 });
  }
}

export { forward as GET, forward as POST };

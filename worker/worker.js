const ALLOWED_ORIGIN = "https://sinsinwilliam1981-png.github.io";
const API = "https://api.github.com/repos/sinsinwilliam1981-png/taiwan-150-scanner";

const cors = origin => ({
  "Access-Control-Allow-Origin": origin === ALLOWED_ORIGIN ? origin : ALLOWED_ORIGIN,
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Cache-Control": "no-store",
  "Vary": "Origin",
});

const json = (data, status, origin) => new Response(JSON.stringify(data), {
  status,
  headers: { ...cors(origin), "Content-Type": "application/json; charset=utf-8" },
});

async function latestRun(env) {
  const response = await fetch(`${API}/actions/workflows/scan.yml/runs?per_page=1`, {
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "taiwan-150-trigger",
    },
  });
  if (!response.ok) throw new Error(`GitHub status ${response.status}`);
  return (await response.json()).workflow_runs?.[0] || null;
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(origin) });
    if (origin !== ALLOWED_ORIGIN) return json({ error: "origin_not_allowed" }, 403, origin);
    try {
      if (request.method === "GET" && url.pathname === "/status") {
        const run = await latestRun(env);
        return json({ ok: true, run: run && { id: run.id, status: run.status, conclusion: run.conclusion, created_at: run.created_at, updated_at: run.updated_at } }, 200, origin);
      }
      if (request.method === "POST" && url.pathname === "/scan") {
        const run = await latestRun(env);
        const recent = run && Date.now() - Date.parse(run.created_at) < 10 * 60 * 1000;
        if (run && (run.status !== "completed" || recent)) {
          return json({ ok: true, already_running: run.status !== "completed", cooldown: run.status === "completed", run_id: run.id }, 200, origin);
        }
        const response = await fetch(`${API}/actions/workflows/scan.yml/dispatches`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${env.GITHUB_TOKEN}`,
            Accept: "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "taiwan-150-trigger",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ ref: "main" }),
        });
        if (response.status !== 204) throw new Error(`GitHub dispatch ${response.status}`);
        return json({ ok: true, started: true }, 202, origin);
      }
      return json({ error: "not_found" }, 404, origin);
    } catch (error) {
      return json({ error: "backend_error", detail: String(error.message || error) }, 502, origin);
    }
  },
};

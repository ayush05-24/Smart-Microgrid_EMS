const configuredBase = import.meta.env.VITE_API_BASE?.replace(/\/$/, "");
let activeBase = configuredBase || "http://127.0.0.1:8000";
let connectionMode = "api";

function apiCandidates() {
  const candidates = [];
  if (configuredBase) candidates.push(configuredBase);

  if (typeof window !== "undefined") {
    const protocol = window.location.protocol === "https:" ? "https:" : "http:";
    const host = window.location.hostname;
    if (host && host !== "127.0.0.1" && host !== "localhost") {
      candidates.push(`${protocol}//${host}:8000`);
    }
  }

  candidates.push("http://127.0.0.1:8000", "http://localhost:8000");
  return [...new Set(candidates)];
}

async function request(path, options = {}) {
  const candidates = [activeBase, ...apiCandidates()].filter(Boolean);
  const uniqueCandidates = [...new Set(candidates)];
  let lastError = null;

  for (const base of uniqueCandidates) {
    try {
      const response = await fetch(`${base}${path}`, {
        mode: "cors",
        headers: {
          "Content-Type": "application/json",
          ...(options.headers || {})
        },
        ...options
      });
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      activeBase = base;
      connectionMode = "api";
      return response.json();
    } catch (error) {
      lastError = error;
    }
  }

  const fallbackPath = cachePath(path, options.method || "GET");
  if (fallbackPath) {
    try {
      const response = await fetch(fallbackPath, { cache: "no-store" });
      if (response.ok) {
        activeBase = "local dashboard cache";
        connectionMode = "cache";
        return response.json();
      }
    } catch {
      // Keep the real API error below; it is more useful to operators.
    }
  }

  throw new Error(
    `API unreachable. Tried ${uniqueCandidates.join(", ")}. Start backend with: venv\\Scripts\\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000. Last error: ${lastError?.message || "unknown"}`
  );
}

function cachePath(path, method) {
  if (method.toUpperCase() !== "GET") return "";
  if (path.startsWith("/forecast")) return "/api-cache/forecast.json";
  if (path.startsWith("/optimize")) return "/api-cache/optimize.json";
  if (path.startsWith("/metrics")) return "/api-cache/metrics.json";
  if (path.startsWith("/alerts")) return "/api-cache/alerts.json";
  return "";
}

export function getApiBase() {
  return activeBase;
}

export function getApiMode() {
  return connectionMode;
}

export function getForecast(hours = 24) {
  return request(`/forecast?horizon_hours=${hours}`);
}

export function getOptimization(hours = 24) {
  return request(`/optimize?horizon_hours=${hours}`);
}

export function getDecisions(hours = 24) {
  return request(`/decisions?horizon_hours=${hours}`);
}

export function getMetrics(hours = 168) {
  return request(`/metrics?horizon_hours=${hours}`);
}

export function getAlerts(hours = 48) {
  return request(`/alerts?horizon_hours=${hours}`);
}

export function runScenario(scenario, horizonHours = 48) {
  return request("/simulate", {
    method: "POST",
    body: JSON.stringify({ scenario, horizon_hours: horizonHours })
  });
}

export function getLiveStatus() {
  return request("/live/status");
}

export function startLiveSimulation(intervalSeconds = 1.5, reset = false) {
  return request("/live/start", {
    method: "POST",
    body: JSON.stringify({ interval_seconds: intervalSeconds, reset })
  });
}

export function stopLiveSimulation() {
  return request("/live/stop", { method: "POST" });
}

export function setLiveOverride(mode) {
  return request("/live/override", {
    method: "POST",
    body: JSON.stringify({ mode })
  });
}

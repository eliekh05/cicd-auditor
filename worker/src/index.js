/**
 * Pipeline Scout — Cloudflare Worker
 *
 * Responsibilities:
 *   1. Cache analysis results in KV for 1 hour (keyed by repo URL)
 *   2. Proxy all other requests to the FastAPI backend
 *   3. Security headers on every response
 *   4. CORS pre-flight
 *
 * Environment variables:
 *   BACKEND_URL  — e.g. https://api.example.com
 *
 * KV Namespaces:
 *   CACHE        — analysis result cache
 */

const CACHE_TTL_SEC = 3600; // 1 hour

const SECURITY_HEADERS = {
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "strict-origin-when-cross-origin",
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") return corsPreFlight();

    if (url.pathname === "/health" && request.method === "GET") {
      return json({ status: "ok", layer: "worker" });
    }

    if (url.pathname === "/api/analyze" && request.method === "POST") {
      return handleAnalyze(request, env);
    }

    return proxyToBackend(request, env);
  },
};

async function handleAnalyze(request, env) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ detail: "Invalid JSON body." }, 400);
  }

  const repoUrl = (body?.url ?? "").trim();
  if (!repoUrl) return json({ detail: "Missing 'url' field." }, 400);

  if (!isGithubUrl(repoUrl)) {
    return json({ detail: "Only public GitHub repository URLs are supported." }, 400);
  }

  // Cache lookup
  const cacheKey = `analysis:${repoUrl}`;
  if (env.CACHE) {
    const cached = await env.CACHE.get(cacheKey);
    if (cached) {
      return addHeaders(new Response(cached, {
        headers: { "Content-Type": "application/json", "X-Cache": "HIT" },
      }));
    }
  }

  // Forward to backend
  const backendUrl = `${env.BACKEND_URL ?? ""}/api/analyze`;
  let backendRes;
  try {
    backendRes = await fetch(backendUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: repoUrl }),
    });
  } catch (err) {
    return json({ detail: `Backend unreachable: ${err.message}` }, 502);
  }

  const text = await backendRes.text();

  if (backendRes.ok && env.CACHE) {
    await env.CACHE.put(cacheKey, text, { expirationTtl: CACHE_TTL_SEC });
  }

  return addHeaders(new Response(text, {
    status: backendRes.status,
    headers: { "Content-Type": "application/json", "X-Cache": "MISS" },
  }));
}

async function proxyToBackend(request, env) {
  const origin = env.BACKEND_URL ?? "";
  const url = new URL(request.url);
  const target = `${origin}${url.pathname}${url.search}`;

  let res;
  try {
    res = await fetch(target, {
      method: request.method,
      headers: request.headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
    });
  } catch (err) {
    return json({ detail: `Proxy error: ${err.message}` }, 502);
  }

  return addHeaders(new Response(res.body, { status: res.status, headers: res.headers }));
}

function json(data, status = 200) {
  return addHeaders(new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  }));
}

function addHeaders(res) {
  const r = new Response(res.body, res);
  Object.entries(SECURITY_HEADERS).forEach(([k, v]) => r.headers.set(k, v));
  r.headers.set("Access-Control-Allow-Origin", "*");
  r.headers.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  r.headers.set("Access-Control-Allow-Headers", "Content-Type");
  return r;
}

function corsPreFlight() {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400",
    },
  });
}

function isGithubUrl(url) {
  return /^https?:\/\/github\.com\/[\w.\-]+\/[\w.\-]+\/?$/.test(url);
}

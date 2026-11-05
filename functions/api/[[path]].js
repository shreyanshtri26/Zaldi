// Cloudflare Pages Function: forwards /api/* to the Flask backend so the site and API share one origin (no CORS).
// Set BACKEND_URL (e.g. https://zaldi-api.example.com) as a Pages environment variable.
export async function onRequest({ request, env }) {
  if (!env.BACKEND_URL) return new Response(JSON.stringify({ error: "BACKEND_URL is not configured" }), { status: 503, headers: { "Content-Type": "application/json" } });
  const url = new URL(request.url);
  return fetch(new Request(new URL(url.pathname + url.search, env.BACKEND_URL), request));
}

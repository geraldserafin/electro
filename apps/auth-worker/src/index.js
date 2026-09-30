/**
 * What the notebook (a static page) cannot do by itself with GitHub:
 *
 *   POST /token {code} → {access_token}   connecting: the code GitHub sent back traded for a token
 *                                         (that takes the OAuth app's secret)
 *   /git/github.com/<owner>/<repo>.git/…  git over HTTP to GitHub, passed on as it is (isomorphic-git's
 *                                         corsProxy): GitHub's git answers no page (no CORS)
 *
 * Only for the notebook's own addresses (ALLOWED_ORIGINS, comma-separated).
 *
 *   GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET   the OAuth app's (secrets: `wrangler secret put …`;
 *                                            in development .dev.vars)
 */
const GIT = /^\/git\/(github\.com\/[\w.-]+\/[\w.-]+\.git\/(?:info\/refs|git-upload-pack|git-receive-pack))$/;
// what a git client sends, and what it reads back
const REQUEST_HEADERS = ["accept", "authorization", "content-type", "git-protocol"];
const RESPONSE_HEADERS = ["content-type", "cache-control", "etag", "last-modified"];

export default {
  /** @param {Request} request @param {Record<string, string>} env */
  async fetch(request, env) {
    const origin = request.headers.get("Origin") ?? "";
    const allowed = (env.ALLOWED_ORIGINS ?? "").split(",").map((o) => o.trim());
    if (!allowed.includes(origin)) return new Response("Forbidden", { status: 403 });
    const cors = {
      "Access-Control-Allow-Origin": origin,
      "Access-Control-Allow-Methods": "GET, POST",
      "Access-Control-Allow-Headers": REQUEST_HEADERS.join(", "),
      "Access-Control-Expose-Headers": RESPONSE_HEADERS.join(", "),
      Vary: "Origin",
    };
    const json = (body, status = 200) =>
      new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });

    const url = new URL(request.url);
    const git = GIT.exec(url.pathname);
    if (git) {
      const headers = new Headers({ "User-Agent": "git/electro" });
      for (const name of REQUEST_HEADERS) {
        const value = request.headers.get(name);
        if (value) headers.set(name, value);
      }
      const response = await fetch(`https://${git[1]}${url.search}`, {
        method: request.method,
        headers,
        body: request.method === "POST" ? await request.arrayBuffer() : null,
      });
      const out = new Headers(cors);
      for (const name of RESPONSE_HEADERS) {
        const value = response.headers.get(name);
        if (value) out.set(name, value);
      }
      return new Response(response.body, { status: response.status, headers: out });
    }

    if (request.method !== "POST" || url.pathname !== "/token") return json({ error: "not_found" }, 404);
    const { code } = await request.json().catch(() => ({}));
    if (typeof code !== "string") return json({ error: "no_code" }, 400);
    const response = await fetch("https://github.com/login/oauth/access_token", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: env.GITHUB_CLIENT_ID, client_secret: env.GITHUB_CLIENT_SECRET, code }),
    });
    const body = await response.json().catch(() => ({}));
    return body.access_token
      ? json({ access_token: body.access_token })
      : json({ error: body.error ?? "exchange_failed" }, 400);
  },
};

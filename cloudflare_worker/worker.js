/**
 * Cloudflare Worker Script - Polymarket AI Bot Emergency Switch
 * KV Store Binding Name: BOT_KV
 */

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
  "Content-Type": "application/json;charset=UTF-8",
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const method = request.method;

    // Handle Preflight OPTIONS Request
    if (method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }

    // Endpoint: GET /status
    if (url.pathname === "/status" && method === "GET") {
      try {
        let status = "RUNNING";
        if (env.BOT_KV) {
          const kvValue = await env.BOT_KV.get("bot_status");
          if (kvValue) {
            status = kvValue;
          }
        }
        return new Response(JSON.stringify({ status: status }), {
          status: 200,
          headers: CORS_HEADERS,
        });
      } catch (err) {
        return new Response(
          JSON.stringify({ error: "Failed to read KV status", details: err.message }),
          { status: 500, headers: CORS_HEADERS }
        );
      }
    }

    // Endpoint: POST /toggle
    if (url.pathname === "/toggle" && method === "POST") {
      try {
        const body = await request.json();
        const newStatus = (body.status || "").toUpperCase();

        if (newStatus !== "RUNNING" && newStatus !== "STOPPED") {
          return new Response(
            JSON.stringify({ error: "Invalid status. Must be 'RUNNING' or 'STOPPED'." }),
            { status: 400, headers: CORS_HEADERS }
          );
        }

        if (env.BOT_KV) {
          await env.BOT_KV.put("bot_status", newStatus);
        }

        return new Response(
          JSON.stringify({
            message: "Bot status updated successfully",
            status: newStatus,
            updatedAt: new Date().toISOString(),
          }),
          { status: 200, headers: CORS_HEADERS }
        );
      } catch (err) {
        return new Response(
          JSON.stringify({ error: "Failed to update KV status", details: err.message }),
          { status: 500, headers: CORS_HEADERS }
        );
      }
    }

    // Fallback 404 Route
    return new Response(
      JSON.stringify({ error: "Endpoint not found. Available endpoints: GET /status, POST /toggle" }),
      { status: 404, headers: CORS_HEADERS }
    );
  },
};

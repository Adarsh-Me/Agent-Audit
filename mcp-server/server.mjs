#!/usr/bin/env node
/**
 * AgentAudit MCP server (stdio) — lets any MCP-capable AI agent query an audit
 * and complete the checkout proof. Pure Node, zero deps.
 *
 * Tools:
 *   audit_status    { run_id }              → run status/counters/cost
 *   get_report      { run_id }             → full metrics payload (scores + CIs)
 *   create_payment_link { run_id, sku }    → Razorpay test-mode link (idempotent)
 *
 * Env: AGENTAUDIT_API (default http://localhost:8000)
 */
import readline from "node:readline";

const API = process.env.AGENTAUDIT_API || "http://localhost:8000";
const VERSION = "1.0.0";

const TOOLS = [
  {
    name: "audit_status",
    description: "Get AgentAudit run status: trials done/total, cost, state.",
    inputSchema: {
      type: "object",
      properties: { run_id: { type: "string" } },
      required: ["run_id"],
    },
  },
  {
    name: "get_report",
    description:
      "Full audit report: AgentReady score with CI, HHI, position bias, framing, coverage F_task with CI, invisible SKUs.",
    inputSchema: {
      type: "object",
      properties: { run_id: { type: "string" } },
      required: ["run_id"],
    },
  },
  {
    name: "create_payment_link",
    description:
      "Create a Razorpay TEST-MODE payment link for a product from an audited catalog (idempotent per run+sku).",
    inputSchema: {
      type: "object",
      properties: { run_id: { type: "string" }, sku: { type: "string" } },
      required: ["run_id", "sku"],
    },
  },
];

async function callApi(path, options) {
  const res = await fetch(`${API}${path}`, options);
  const text = await res.text();
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    body = { raw: text.slice(0, 500) };
  }
  return { status: res.status, body };
}

async function toolCall(name, args) {
  if (name === "audit_status") {
    const r = await callApi(`/api/audit/${args.run_id}`);
    return r.body;
  }
  if (name === "get_report") {
    const r = await callApi(`/api/report/${args.run_id}`);
    return r.body;
  }
  if (name === "create_payment_link") {
    const r = await callApi("/api/payments/link", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: args.run_id, sku: args.sku }),
    });
    return r.body;
  }
  throw new Error(`unknown tool: ${name}`);
}

function send(msg) {
  process.stdout.write(JSON.stringify(msg) + "\n");
}

const rl = readline.createInterface({ input: process.stdin, terminal: false });

rl.on("line", async (line) => {
  const trimmed = line.trim();
  if (!trimmed) return;
  let msg;
  try {
    msg = JSON.parse(trimmed);
  } catch {
    return;
  }
  const { id, method, params } = msg;
  try {
    if (method === "initialize") {
      send({
        jsonrpc: "2.0", id,
        result: {
          protocolVersion: params?.protocolVersion || "2024-11-05",
          capabilities: { tools: {} },
          serverInfo: { name: "agentaudit-mcp", version: VERSION },
        },
      });
    } else if (method === "tools/list") {
      send({ jsonrpc: "2.0", id, result: { tools: TOOLS } });
    } else if (method === "tools/call") {
      const data = await toolCall(params.name, params.arguments || {});
      send({
        jsonrpc: "2.0", id,
        result: {
          content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
        },
      });
    } else if (method === "ping") {
      send({ jsonrpc: "2.0", id, result: {} });
    } else if (id !== undefined) {
      send({ jsonrpc: "2.0", id, error: { code: -32601, message: `no handler: ${method}` } });
    }
  } catch (err) {
    send({
      jsonrpc: "2.0", id,
      error: { code: -32000, message: String(err && err.message ? err.message : err) },
    });
  }
});

rl.on("close", () => process.exit(0));

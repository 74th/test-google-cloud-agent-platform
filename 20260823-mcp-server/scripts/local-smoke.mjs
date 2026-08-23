import assert from "node:assert/strict";
import { spawn } from "node:child_process";

const port = process.env.SMOKE_PORT ?? "18080";
const externalBase = process.env.SMOKE_URL;
const child = externalBase
  ? undefined
  : spawn(process.execPath, ["src/server.js"], {
      env: { ...process.env, PORT: port },
      stdio: ["ignore", "pipe", "inherit"],
    });
const base = externalBase ?? `http://127.0.0.1:${port}`;

try {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      if ((await fetch(`${base}/healthz`)).ok) break;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  const call = async (id, method, params = {}) => {
    const response = await fetch(`${base}/mcp`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json, text/event-stream" },
      body: JSON.stringify({ jsonrpc: "2.0", id, method, params }),
    });
    assert.equal(response.ok, true, `${method} failed with HTTP ${response.status}`);
    return response.json();
  };
  const initialized = await call(1, "initialize", {
    protocolVersion: "2025-06-18",
    capabilities: {},
    clientInfo: { name: "local-smoke", version: "0.1.0" },
  });
  assert.equal(initialized.result.serverInfo.name, "mcp-server-20260823-mcp-server");
  const listed = await call(2, "tools/list");
  assert.equal(listed.result.tools[0].name, "validate_echo");
  const executed = await call(3, "tools/call", { name: "validate_echo", arguments: { message: "smoke" } });
  assert.match(executed.result.content[0].text, /20260823-mcp-server/);
  const invalid = await call(4, "tools/call", { name: "validate_echo", arguments: {} });
  assert.equal(invalid.result.isError, true);
  console.log("Local MCP smoke test passed: initialize, tools/list, valid call, invalid input.");
} finally {
  child?.kill("SIGTERM");
}

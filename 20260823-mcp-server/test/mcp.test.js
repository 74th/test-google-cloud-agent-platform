import { describe, expect, it } from "vitest";
import { createHttpServer } from "../src/server.js";

async function request(server, id, method, params = {}) {
  const address = server.address();
  const response = await fetch(`http://127.0.0.1:${address.port}/mcp`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json, text/event-stream" },
    body: JSON.stringify({ jsonrpc: "2.0", id, method, params }),
  });
  return { response, body: await response.json() };
}

async function requestWithHeaders(server, id, method, headers, params = {}) {
  const address = server.address();
  const response = await fetch(`http://127.0.0.1:${address.port}/mcp`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json, text/event-stream", ...headers },
    body: JSON.stringify({ jsonrpc: "2.0", id, method, params }),
  });
  return { response, body: await response.json() };
}

describe("stateless MCP HTTP server", () => {
  it("supports initialization and tools/list", async () => {
    const server = await createHttpServer();
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    try {
      const initialized = await request(server, 1, "initialize", {
        protocolVersion: "2025-06-18",
        capabilities: {},
        clientInfo: { name: "vitest", version: "0.1.0" },
      });
      expect(initialized.response.status).toBe(200);
      expect(initialized.body.result.serverInfo.name).toBe("mcp-server-20260823-mcp-server");
      const listed = await request(server, 2, "tools/list");
      expect(listed.body.result.tools[0].name).toBe("validate_echo");
      expect(listed.body.result.tools[0].inputSchema.required).toEqual(["message"]);
    } finally {
      await new Promise((resolve) => server.close(resolve));
    }
  });

  it("executes the deterministic Tool and rejects invalid input", async () => {
    const server = await createHttpServer();
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    try {
      const executed = await request(server, 1, "tools/call", {
        name: "validate_echo",
        arguments: { message: "hello" },
      });
      expect(executed.body.result.isError).not.toBe(true);
      expect(executed.body.result.structuredContent).toEqual({
        experiment: "20260823-mcp-server",
        message: "hello",
        ok: true,
      });
      const invalid = await request(server, 2, "tools/call", {
        name: "validate_echo",
        arguments: {},
      });
      expect(invalid.body.result.isError).toBe(true);
    } finally {
      await new Promise((resolve) => server.close(resolve));
    }
  });

  it("propagates sanitized correlation and hosting markers without changing Tool schema", async () => {
    const server = await createHttpServer();
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    try {
      const listed = await request(server, 1, "tools/list");
      expect(listed.body.result.tools[0].inputSchema.required).toEqual(["message"]);
      const executed = await requestWithHeaders(server, 2, "tools/call", {
        "x-mcp-correlation-id": "mcp-correlation-1",
        "x-mcp-hosting-target": "cloud-run",
      }, { name: "validate_echo", arguments: { message: "correlated" } });
      expect(executed.body.result.structuredContent).toMatchObject({
        correlationId: "mcp-correlation-1",
        hostingTarget: "cloud-run",
      });
    } finally {
      await new Promise((resolve) => server.close(resolve));
    }
  });
});

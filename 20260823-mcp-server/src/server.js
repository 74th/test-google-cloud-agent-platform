import http from "node:http";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { executeValidationTool, TOOL_DESCRIPTION, TOOL_NAME, toolInputSchema } from "./tool-definition.js";

export function createMcpServer() {
  const server = new McpServer({ name: "mcp-server-20260823-mcp-server", version: "0.1.0" });
  server.registerTool(
    TOOL_NAME,
    {
      description: TOOL_DESCRIPTION,
      inputSchema: toolInputSchema,
    },
    async ({ message }) => ({
      content: [{ type: "text", text: JSON.stringify(executeValidationTool({ message })) }],
      structuredContent: executeValidationTool({ message }),
    }),
  );
  return server;
}

async function readJsonBody(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  if (chunks.length === 0) return undefined;
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

export async function createHttpServer() {
  return http.createServer(async (request, response) => {
    if (request.url === "/healthz") {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ ok: true }));
      return;
    }
    if (request.url !== "/mcp" || request.method !== "POST") {
      response.writeHead(404, { "content-type": "application/json" });
      response.end(JSON.stringify({ error: "not_found" }));
      return;
    }
    try {
      const body = await readJsonBody(request);
      // Stateless mode deliberately creates a fresh protocol transport for
      // every request. No session or request correctness depends on process
      // local state, which allows the same image to scale horizontally.
      const mcpServer = createMcpServer();
      const transport = new StreamableHTTPServerTransport({
        sessionIdGenerator: undefined,
        enableJsonResponse: true,
      });
      await mcpServer.connect(transport);
      await transport.handleRequest(request, response, body);
    } catch (error) {
      if (!response.headersSent) response.writeHead(400, { "content-type": "application/json" });
      if (!response.writableEnded) response.end(JSON.stringify({ error: "invalid_json" }));
    }
  });
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const port = Number.parseInt(process.env.PORT ?? "8080", 10);
  const server = await createHttpServer();
  server.listen(port, "0.0.0.0", () => {
    console.log(`mcp-server-20260823-mcp-server listening on 0.0.0.0:${port}`);
  });
}

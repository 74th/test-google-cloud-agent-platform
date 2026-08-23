import { z } from "zod";

export const TOOL_NAME = "validate_echo";
export const TOOL_DESCRIPTION =
  "Return a deterministic validation response for the 20260823-mcp-server experiment.";

export const toolInputSchema = {
  message: z.string().min(1).max(256).describe("Text to include in the validation response."),
};

export const toolSpec = {
  name: TOOL_NAME,
  description: TOOL_DESCRIPTION,
  inputSchema: {
    $schema: "http://json-schema.org/draft-07/schema#",
    type: "object",
    properties: {
      message: {
        type: "string",
        description: "Text to include in the validation response.",
        minLength: 1,
        maxLength: 256,
      },
    },
    required: ["message"],
  },
  execution: { taskSupport: "forbidden" },
};

export const toolListSpec = { tools: [toolSpec] };

export function executeValidationTool({ message }) {
  return {
    experiment: "20260823-mcp-server",
    message,
    ok: true,
  };
}

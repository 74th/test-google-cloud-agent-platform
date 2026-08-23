import assert from "node:assert/strict";
import { toolListSpec } from "../src/tool-definition.js";
import fs from "node:fs/promises";

const expected = JSON.parse(await fs.readFile(new URL("../toolspec.json", import.meta.url), "utf8"));
assert.deepEqual(toolListSpec, expected, "versioned registry Tool specification differs from runtime definition");

if (process.argv[2]) {
  const response = await fetch(process.argv[2], {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json, text/event-stream" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list", params: {} }),
  });
  assert.equal(response.ok, true, `runtime tools/list returned HTTP ${response.status}`);
  const body = await response.json();
  assert.deepEqual(body.result, expected, "runtime tools/list differs from toolspec.json");
}

console.log("Tool specification is consistent with the runtime definition.");

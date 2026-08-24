import { describe, expect, it } from "vitest";
import fs from "node:fs";

const terraform = Object.fromEntries(
  fs.readdirSync("terraform").filter((name) => name.endsWith(".tf")).map((name) => [name, fs.readFileSync(`terraform/${name}`, "utf8")]),
);

describe("Terraform guardrails", () => {
  it("uses experiment labels and immutable Cloud Run images", () => {
    expect(terraform["variables.tf"]).toContain("20260823-mcp-server");
    expect(terraform["cloud_run.tf"]).toMatch(/min_instance_count\s*=\s*0/);
    expect(terraform["cloud_run.tf"]).toMatch(/max_instance_count\s*=\s*3/);
    expect(terraform["cloud_run.tf"]).toContain("@sha256:");
    expect(terraform["cloud_run.tf"]).not.toContain("allUsers");
    expect(terraform["iam.tf"]).not.toContain("default-compute");
  });

  it("keeps GKE Standard and disabled by default", () => {
    expect(terraform["variables.tf"]).toMatch(/enable_gke[\s\S]*default\s*=\s*false/);
    expect(terraform["gke.tf"]).not.toContain("enable_autopilot = true");
    expect(terraform["gke.tf"]).toContain("google_compute_network");
    expect(terraform["gke.tf"]).toContain("workload_identity_config");
    expect(fs.readFileSync("k8s/mcp.yaml.tmpl", "utf8")).toContain("type: ClusterIP");
    expect(fs.readFileSync("k8s/mcp.yaml.tmpl", "utf8")).toContain("__IMAGE_DIGEST__");
  });

  it("declares isolated governed Agent Runtime resources", () => {
    expect(terraform["agent_runtime.tf"]).toContain('identity_type   = "AGENT_IDENTITY"');
    expect(terraform["agent_runtime.tf"]).toContain("agent_to_anywhere_config");
    expect(terraform["variables.tf"]).toContain("agent_gateway_id");
    expect(terraform["locals.tf"]).toContain("agent_gateway_id");
    expect(terraform["iam.tf"]).toContain("google_artifact_registry_repository_iam_member");
    expect(terraform["registry.tf"]).toContain("google_iap_agent_registry_mcp_server_iam_member");
    expect(terraform["iam.tf"]).toContain("roles/agentregistry.viewer");
    expect(terraform["iam.tf"]).toContain("serviceAccountOpenIdTokenCreator");
    expect(terraform["agent_runtime.tf"]).toContain("@sha256:");
    expect(Object.values(terraform).join("\n")).not.toContain("allUsers");
    expect(Object.values(terraform).join("\n")).not.toContain("ANTHROPIC_API_KEY");
  });

  it("fails closed for the GKE front-door prerequisites", () => {
    expect(terraform["variables.tf"]).toContain("gke_mcp_hostname");
    expect(terraform["registry.tf"]).toContain("GKE Registry registration requires");
    expect(fs.readFileSync("k8s/mcp.yaml.tmpl", "utf8")).toContain("type: ClusterIP");
    expect(fs.readFileSync("k8s/mcp.yaml.tmpl", "utf8")).not.toContain("type: LoadBalancer");
  });
});

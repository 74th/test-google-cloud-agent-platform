import { describe, expect, it } from "vitest";
import { execFileSync } from "node:child_process";
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
    expect(terraform["gke_ilb.tf"]).toContain('address_type = "INTERNAL"');
    expect(terraform["gke_ilb.tf"]).toContain('purpose       = "REGIONAL_MANAGED_PROXY"');
    expect(terraform["gke_ilb.tf"]).toContain('role          = "ACTIVE"');
    expect(terraform["gke_ilb.tf"]).toContain('visibility  = "private"');
    expect(fs.readFileSync("k8s/gke-internal-https.yaml.tmpl", "utf8")).toContain("gce-internal");
    expect(fs.readFileSync("k8s/gke-internal-https.yaml.tmpl", "utf8")).toContain('ingress.allow-http: "false"');
    expect(fs.readFileSync("k8s/gke-internal-https.yaml.tmpl", "utf8")).toContain("mcp-20260823-mcp-server");
  });

  it("rejects common, default, unrelated, and destroy plan actions", () => {
    for (const fixture of ["scope-add-common.json", "scope-change-default.json", "scope-replace-unrelated.json", "scope-destroy-attachment.json"]) {
      expect(() => execFileSync("python3", ["scripts/check_scope.py", `test/fixtures/${fixture}`], { stdio: "pipe" })).toThrow();
    }
  });

  it("accepts a consumer-only plan", () => {
    expect(execFileSync("python3", ["scripts/check_scope.py", "test/fixtures/scope-consumer-only.json"], { encoding: "utf8" })).toContain("PASS");
    expect(execFileSync("python3", ["scripts/check_scope.py", "test/fixtures/scope-gke-common-vpc.json"], { encoding: "utf8" })).toContain("PASS");
  });

  it("has a fail-closed shared Gateway preflight", () => {
    const run = (live) => execFileSync("python3", ["scripts/gateway_preflight.py", "--owner-json", "test/fixtures/gateway-owner-valid.json", "--live-json", `test/fixtures/${live}`], { stdio: "pipe" });
    expect(run("gateway-live-valid.json").toString()).toContain('"status": "PASS"');
    for (const fixture of ["gateway-live-project-mismatch.json", "gateway-live-attribute-mismatch.json", "gateway-live-missing.json", "gateway-live-non-active.json"]) {
      expect(() => run(fixture)).toThrow();
    }
    expect(() => execFileSync("python3", ["scripts/gateway_preflight.py", "--owner-json", "test/fixtures/gateway-owner-retired.json", "--live-json", "test/fixtures/gateway-live-valid.json"], { stdio: "pipe" })).toThrow();
  });

  it("uses consumer-owned collision-resistant control-plane registrations", () => {
    expect(terraform["registry.tf"]).toContain('service_id   = "${var.name_prefix}-agentregistry"');
    expect(terraform["registry.tf"]).toContain('service_id   = "${var.name_prefix}-aiplatform"');
    expect(terraform["registry.tf"]).toContain('service_id   = "${var.name_prefix}-aiplatform-global"');
    expect(terraform["registry.tf"]).toContain('service_id   = "${var.name_prefix}-iamcredentials"');
    expect(terraform["registry.tf"]).not.toContain("20260822 managed");
    expect(terraform["variables.tf"]).toContain("cloud_run_registry_service_id");
    expect(terraform["variables.tf"]).toContain("gke_registry_service_id");
  });

  it("keeps egress and endpoint authorization resource-scoped", () => {
    const registry = terraform["registry.tf"];
    expect((registry.match(/roles\/iap\.egressor/g) || []).length).toBe(6);
    expect(registry).not.toMatch(/google_project_iam_member[\s\S]{0,240}roles\/iap\.egressor/);
    expect(terraform["iam.tf"]).toContain('role    = "roles/aiplatform.user"');
    expect(terraform["cloud_run.tf"]).toContain('role     = "roles/run.invoker"');
    expect(terraform["iam.tf"]).toContain('role       = "roles/artifactregistry.reader"');
    expect(Object.values(terraform).join("\n")).not.toContain("allUsers");
  });

  it("fails closed for Gateway CA retrieval and checks immutable trust images", () => {
    const build = "scripts/build_push_agent_runtime.sh";
    expect(fs.readFileSync(build, "utf8")).toContain('AGENT_GATEWAY_ID');
    expect(fs.readFileSync(build, "utf8")).toContain('[[ -z "$gateway_cert" ]]');
    expect(fs.readFileSync(build, "utf8")).toContain("openssl x509 -noout");
    expect(fs.readFileSync("agent_runtime/Dockerfile", "utf8")).toContain("--mount=type=secret,id=agent-gateway-ca");
    expect(fs.readFileSync("agent_runtime/Dockerfile", "utf8")).toContain("test -s /run/secrets/agent-gateway-ca");
    expect(fs.readFileSync(build, "utf8")).toContain("--secret id=agent-gateway-ca,env=AGENT_GATEWAY_ROOT_CERTIFICATES");
    expect(fs.readFileSync(build, "utf8")).not.toContain("--build-arg");
    expect(fs.readFileSync("scripts/check_agent_runtime_image.sh", "utf8")).toContain("@sha256:[0-9a-f]{64}");
    expect(() => execFileSync("bash", [build], { stdio: "pipe", env: { ...process.env, AGENT_GATEWAY_ID: "" } })).toThrow();
    for (const fixture of ["gcloud-empty", "gcloud-invalid-ca"]) {
      expect(() => execFileSync("bash", [build], {
        stdio: "pipe",
        env: { ...process.env,
          GCLOUD_BIN: `${process.cwd()}/test/fixtures/${fixture}/gcloud`,
          AGENT_GATEWAY_ID: "projects/nnyn-dev/locations/us-central1/agentGateways/common-egress" },
      })).toThrow();
    }
  });
});

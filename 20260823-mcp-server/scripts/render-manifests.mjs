import fs from "node:fs/promises";

const image = process.env.IMAGE_DIGEST;
const workloadServiceAccount = process.env.GKE_WORKLOAD_SERVICE_ACCOUNT;
if (!image || !/@sha256:[0-9a-f]{64}$/.test(image)) {
  throw new Error("IMAGE_DIGEST must be an immutable image reference ending in @sha256:<64 hex digits>");
}
if (!workloadServiceAccount || !workloadServiceAccount.endsWith(".iam.gserviceaccount.com")) {
  throw new Error("GKE_WORKLOAD_SERVICE_ACCOUNT must be a Google service account email");
}
const template = await fs.readFile(new URL("../k8s/mcp.yaml.tmpl", import.meta.url), "utf8");
process.stdout.write(
  template
    .replaceAll("__IMAGE_DIGEST__", image)
    .replaceAll("__GKE_WORKLOAD_SERVICE_ACCOUNT__", workloadServiceAccount),
);

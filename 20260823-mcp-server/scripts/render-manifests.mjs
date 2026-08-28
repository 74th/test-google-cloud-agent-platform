import fs from "node:fs/promises";

const image = process.env.IMAGE_DIGEST;
const workloadServiceAccount = process.env.GKE_WORKLOAD_SERVICE_ACCOUNT;
const serviceClusterIp = process.env.GKE_SERVICE_CLUSTER_IP;
if (!image || !/@sha256:[0-9a-f]{64}$/.test(image)) {
  throw new Error("IMAGE_DIGEST must be an immutable image reference ending in @sha256:<64 hex digits>");
}
if (!workloadServiceAccount || !workloadServiceAccount.endsWith(".iam.gserviceaccount.com")) {
  throw new Error("GKE_WORKLOAD_SERVICE_ACCOUNT must be a Google service account email");
}
if (!serviceClusterIp || !/^10\.242\.[0-9]+\.[0-9]+$/.test(serviceClusterIp)) {
  throw new Error("GKE_SERVICE_CLUSTER_IP must be an address in the dedicated service range");
}
if (serviceClusterIp === "10.242.0.1" || serviceClusterIp === "10.242.0.10") {
  throw new Error("GKE_SERVICE_CLUSTER_IP conflicts with a reserved Kubernetes system Service");
}
const template = await fs.readFile(new URL("../k8s/mcp.yaml.tmpl", import.meta.url), "utf8");
process.stdout.write(
  template
    .replaceAll("__IMAGE_DIGEST__", image)
    .replaceAll("__GKE_WORKLOAD_SERVICE_ACCOUNT__", workloadServiceAccount)
    .replaceAll("__GKE_SERVICE_CLUSTER_IP__", serviceClusterIp),
);

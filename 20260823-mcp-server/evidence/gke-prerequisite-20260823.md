# GKE authenticated front-door prerequisite evidence

Date: 2026-08-23  
Status: BLOCKED / no fallback created

Read-only checks found no Cloud DNS managed zone in `nnyn-dev`. The only
existing Compute managed certificate is for `temp20200801.74th.tech` and has
`FAILED_NOT_VISIBLE`; it is out of scope and is not reused. Certificate
Manager is not enabled in the project. DNS lookup for `74th.tech` did not
provide an authoritative zone usable by this project.

The implementation therefore requires `gke_mcp_hostname` and
`gke_auth_audience` when `enable_gke=true`, and does not create an anonymous
listener, plain-HTTP external listener, or public bypass around the existing
`ClusterIP` service.

# Support inquiry: Agent Engine query job fails with an Agent Gateway association (minimal, standalone repro)

**Date:** 2026-09-12 UTC
**Product area:** Vertex AI Agent Engine (custom container / BYOC), Agent Gateway, Agent Registry
**Severity:** Development / validation blocker; no production impact
**Relation to prior report:** This independently reproduces
`20260802-BYOC/support/google-query-job-agent-gateway-inquiry-20260829.md`
(filed 2026-08-29 against project `nnyn-dev`'s shared `common-egress`
Gateway) from a brand-new, single-purpose project with no shared state, to
rule out anything specific to that project's configuration history.

## Request

We need to run a long-running Agent Engine query job (`run_query_job`) on a
BYOC Runtime that is associated with an Agent-to-Anywhere Agent Gateway. The
query job's Cloud Storage input never reaches our application container.
Please confirm whether this configuration is supported and, if so, the
supported way to let query-job GCS traffic through an Agent
Gateway-associated Runtime.

## Environment

| Item | Value |
| --- | --- |
| Project | `dev-74th-20260912` (project number `854555400134`) -- created solely for this repro |
| Region | `us-central1` |
| Runtime (Gateway-associated) | `projects/854555400134/locations/us-central1/reasoningEngines/246973951098486784` |
| Runtime (no Gateway, baseline) | `projects/854555400134/locations/us-central1/reasoningEngines/8002172509430480896` |
| Both Runtimes | identical container image digest, identical `class_methods`, `identity_type=AGENT_IDENTITY` |
| Gateway | `projects/dev-74th-20260912/locations/us-central1/agentGateways/byoc20260912-egress` |
| Gateway mode | Google-managed `AGENT_TO_ANYWHERE` |
| Gateway network attachment | `byoc20260912-agent-gateway-attachment` (dedicated `/28`, dedicated VPC) |
| Agent Registry | `//agentregistry.googleapis.com/projects/dev-74th-20260912/locations/us-central1`, one Service allow-listing only `https://github.com` |
| GCS bucket | `dev-74th-20260912-byoc-queryjobs` (query-job input/output only) |
| Terraform / provider | Terraform `1.13.1`, `hashicorp/google` `7.46.1`, `hashicorp/google-nightly` `2026.4.8-7.27.0` |

The entire environment (VPC, Gateway, Registry, Runtimes) is owned by this
one project and was built from scratch on 2026-09-12; it has no history and
no dependency on any other project or prior experiment.

## What works

The Gateway-associated Runtime's synchronous contract also works correctly
(see [The same Gateway works correctly for ordinary application
traffic](#the-same-gateway-works-correctly-for-ordinary-application-traffic)
below). As the control for the `run_query_job` comparison, the
**identically-configured, non-Gateway Runtime's `run_query_job`** was
verified end to end on 2026-09-12:

1. GCS input object written and downloaded (`gcs_input`: success).
2. Application container (`job-container`) received `POST /`
   (`http_delivery`: success, two deliveries observed including a platform
   retry).
3. Processing completed (`query_completed` matched to the request's
   verification marker).
4. GCS output object written (`gcs_output`: success,
   `content_type=application/x-ndjson`, `size=15`).

Evidence: `results/query-job-no-gateway-2.jsonl`,
`results/evaluation-case1-no-gateway.json`.

## Observed failure

Same container image, same `class_methods`, same GCS bucket, only
difference: the Runtime's `deployment_spec.agent_gateway_config` points at
this project's own Agent Gateway.

| Item | Value |
| --- | --- |
| Job | `projects/854555400134/locations/us-central1/operations/6033194252077367296` |
| Input object | `gs://dev-74th-20260912-byoc-queryjobs/query-jobs/gateway-20260912T051707Z_input.json` |
| Expected output object | `gs://dev-74th-20260912-byoc-queryjobs/query-jobs/gateway-20260912T051707Z.json` |

Observed results:

1. The input object was written by the SDK and is independently readable by
   our own credentials (`gcs_input` preflight succeeds).
2. In the query-job execution window, `proxy-container` (a platform-internal
   component; we do not assume it is customer-configurable) logs the
   following complete Python exception chain failing to download that same
   input object over a plain HTTPS connection to `storage.googleapis.com`.
   This is the full, unedited traceback reconstructed from Cloud Logging in
   original write order (sorted by `timestamp`, then `insertId`; individual
   frame lines arrived as separate log entries), reproduced verbatim so the
   `proxy-container` owner can act on it directly:

   ```
   Traceback (most recent call last):
     File "/usr/local/lib/python3.14/site-packages/urllib3/connectionpool.py", line 464, in _make_request
       self._validate_conn(conn)
       ~~~~~~~~~~~~~~~~~~~^^^^^^
     File "/usr/local/lib/python3.14/site-packages/urllib3/connectionpool.py", line 1106, in _validate_conn
       conn.connect()
       ~~~~~~~~~~~~^^
     File "/usr/local/lib/python3.14/site-packages/urllib3/connection.py", line 796, in connect
       sock_and_verified = _ssl_wrap_socket_and_match_hostname(
           sock=sock,
       ...<14 lines>...
           assert_fingerprint=self.assert_fingerprint,
       )
     File "/usr/local/lib/python3.14/site-packages/urllib3/connection.py", line 975, in _ssl_wrap_socket_and_match_hostname
       ssl_sock = ssl_wrap_socket(
           sock=sock,
       ...<8 lines>...
           tls_in_tls=tls_in_tls,
       )
     File "/usr/local/lib/python3.14/site-packages/urllib3/util/ssl_.py", line 433, in ssl_wrap_socket
       ssl_sock = _ssl_wrap_socket_impl(sock, context, tls_in_tls, server_hostname)
     File "/usr/local/lib/python3.14/site-packages/urllib3/util/ssl_.py", line 477, in _ssl_wrap_socket_impl
       return ssl_context.wrap_socket(sock, server_hostname=server_hostname)
              ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
     File "/usr/local/lib/python3.14/ssl.py", line 455, in wrap_socket
       return self.sslsocket_class._create(
              ~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
           sock=sock,
           ^^^^^^^^^^
       ...<5 lines>...
           session=session
           ^^^^^^^^^^^^^^^
       )
       ^
     File "/usr/local/lib/python3.14/ssl.py", line 1076, in _create
       self.do_handshake()
       ~~~~~~~~~~~~~~~~~^^
     File "/usr/local/lib/python3.14/ssl.py", line 1372, in do_handshake
       self._sslobj.do_handshake()
       ~~~~~~~~~~~~~~~~~~~~~~~~~^^
   ssl.SSLEOFError: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1082)
   During handling of the above exception, another exception occurred:
   Traceback (most recent call last):
     File "/usr/local/lib/python3.14/site-packages/urllib3/connectionpool.py", line 788, in urlopen
       response = self._make_request(
           conn,
       ...<10 lines>...
           **response_kw,
       )
     File "/usr/local/lib/python3.14/site-packages/urllib3/connectionpool.py", line 488, in _make_request
       raise new_e
   urllib3.exceptions.SSLError: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1082)
   The above exception was the direct cause of the following exception:
   Traceback (most recent call last):
     File "/usr/local/lib/python3.14/site-packages/requests/adapters.py", line 696, in send
       resp = conn.urlopen(
           method=request.method,
       ...<9 lines>...
           chunked=chunked,
       )
     File "/usr/local/lib/python3.14/site-packages/urllib3/connectionpool.py", line 842, in urlopen
       retries = retries.increment(
           method, url, error=new_e, _pool=self, _stacktrace=sys.exc_info()[2]
       )
     File "/usr/local/lib/python3.14/site-packages/urllib3/util/retry.py", line 543, in increment
       raise MaxRetryError(_pool, url, reason) from reason  # type: ignore[arg-type]
       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
   urllib3.exceptions.MaxRetryError: HTTPSConnectionPool(host='storage.googleapis.com', port=443): Max retries exceeded with url: /download/storage/v1/b/dev-74th-20260912-byoc-queryjobs/o/query-jobs%2Fgateway-20260912T051707Z_input.json?alt=media (Caused by SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1082)')))
   During handling of the above exception, another exception occurred:
   Traceback (most recent call last):
     File "/usr/local/lib/python3.14/site-packages/google/api_core/retry/retry_unary.py", line 148, in retry_target
       result = target()
     File "/usr/local/lib/python3.14/site-packages/google/cloud/storage/_media/requests/download.py", line 253, in retriable_request
       result = transport.request(method, url, **request_kwargs)
     File "/usr/local/lib/python3.14/site-packages/google/auth/transport/requests.py", line 629, in request
       response = super(AuthorizedSession, self).request(
           method,
       ...<4 lines>...
           **kwargs
       )
     File "/usr/local/lib/python3.14/site-packages/requests/sessions.py", line 651, in request
       resp = self.send(prep, **send_kwargs)
     File "/usr/local/lib/python3.14/site-packages/requests/sessions.py", line 784, in send
       r = adapter.send(request, **kwargs)
     File "/usr/local/lib/python3.14/site-packages/requests/adapters.py", line 727, in send
       raise SSLError(e, request=request)
   requests.exceptions.SSLError: HTTPSConnectionPool(host='storage.googleapis.com', port=443): Max retries exceeded with url: /download/storage/v1/b/dev-74th-20260912-byoc-queryjobs/o/query-jobs%2Fgateway-20260912T051707Z_input.json?alt=media (Caused by SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1082)')))
   The above exception was the direct cause of the following exception:
   Traceback (most recent call last):
     File "/app/client.py", line 380, in <module>
       main()
       ~~~~^^
     File "/app/client.py", line 357, in main
       query_content: str = _download_from_gcs(
                            ~~~~~~~~~~~~~~~~~~^
           storage_client, input_gcs_uri, kms_key_name=kms_key_name
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
       )
       ^
     File "/app/client.py", line 284, in _download_from_gcs
       return blob.download_as_text()
              ~~~~~~~~~~~~~~~~~~~~~^^
     File "/usr/local/lib/python3.14/site-packages/google/cloud/storage/blob.py", line 1787, in download_as_text
       data = self.download_as_bytes(
           client=client,
       ...<11 lines>...
           single_shot_download=single_shot_download,
       )
     File "/usr/local/lib/python3.14/site-packages/google/cloud/storage/blob.py", line 1552, in download_as_bytes
       self._prep_and_do_download(
       ~~~~~~~~~~~~~~~~~~~~~~~~~~^
           string_buffer,
           ^^^^^^^^^^^^^^
       ...<13 lines>...
           single_shot_download=single_shot_download,
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
       )
       ^
     File "/usr/local/lib/python3.14/site-packages/google/cloud/storage/blob.py", line 4718, in _prep_and_do_download
       self._do_download(
       ~~~~~~~~~~~~~~~~~^
           transport,
           ^^^^^^^^^^
       ...<9 lines>...
           single_shot_download=single_shot_download,
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
       )
       ^
     File "/usr/local/lib/python3.14/site-packages/google/cloud/storage/blob.py", line 1094, in _do_download
       response = download.consume(transport, timeout=timeout)
     File "/usr/local/lib/python3.14/site-packages/google/cloud/storage/_media/requests/download.py", line 280, in consume
       return _request_helpers.wait_and_retry(retriable_request, self._retry_strategy)
              ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
     File "/usr/local/lib/python3.14/site-packages/google/cloud/storage/_media/requests/_request_helpers.py", line 107, in wait_and_retry
       return func()
     File "/usr/local/lib/python3.14/site-packages/google/api_core/retry/retry_unary.py", line 295, in retry_wrapped_func
       return retry_target(
           target,
       ...<3 lines>...
           on_error=on_error,
       )
     File "/usr/local/lib/python3.14/site-packages/google/api_core/retry/retry_unary.py", line 157, in retry_target
       next_sleep = _retry_error_helper(
           exc,
       ...<6 lines>...
           timeout,
       )
     File "/usr/local/lib/python3.14/site-packages/google/api_core/retry/retry_base.py", line 230, in _retry_error_helper
       raise final_exc from source_exc
   google.api_core.exceptions.RetryError: Timeout of 120.0s exceeded, last exception: HTTPSConnectionPool(host='storage.googleapis.com', port=443): Max retries exceeded with url: /download/storage/v1/b/dev-74th-20260912-byoc-queryjobs/o/query-jobs%2Fgateway-20260912T051707Z_input.json?alt=media (Caused by SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1082)')))
   ```
3. `job-container` (our application) never logs a `POST /` for this attempt
   at all -- confirmed by a Cloud Logging query bounded to the attempt's
   time window and this Runtime's resource ID (see
   `scripts/query_job.py::collect_log_evidence`).
4. No GCS output object was ever written.
5. The job operation had not reached a terminal state within our 7-minute
   monitoring window. A later `GET` on the operation confirms it eventually
   terminated in failure:

   ```json
   {
     "name": "projects/854555400134/locations/us-central1/operations/6033194252077367296",
     "done": true,
     "error": {
       "code": 13,
       "message": "Task reasoning-engine-246973951098486784-job-msm2h-task0 failed with exit code: 1 and message: The container exited with an error."
     }
   }
   ```

   This exactly matches the exit-code-13 failure symptom recorded in the
   2026-08-29 report against `nnyn-dev`. The baseline (no-Gateway) job's
   operation, fetched the same way, terminated successfully with
   `outputGcsUri` set.

Full raw log entries (including the complete traceback) are attached as
`results/case3-proxy-container-traceback.json`; the structured evaluation is
`results/evaluation-case3-gateway.json`; the operation terminal states above
are `results/additional-verification-20260912/operation-gateway-6033194252077367296.json`
and `results/additional-verification-20260912/operation-no-gateway-5351346409763241984.json`.

### Relationship to the 2026-08-29 report

This is the same class of failure as the earlier report against `nnyn-dev`,
reproduced independently:

| | 2026-08-29 report (`nnyn-dev`) | This report (`dev-74th-20260912`) |
| --- | --- | --- |
| Failing host | `storage.mtls.googleapis.com:443` | `storage.googleapis.com:443` |
| Low-level error | `SSLCertVerificationError: CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain` | `SSLEOFError: UNEXPECTED_EOF_WHILE_READING` |
| Failing component | `proxy-container` | `proxy-container` |
| Application container reached | No | No |
| Baseline (no Gateway) | Succeeded | Succeeded |

The differing low-level TLS symptom (certificate verification failure vs. an
unexpected connection close) across two independent projects suggests the
interception/inspection this Gateway association introduces on the
query-job's own GCS delivery path fails in more than one way, rather than
hitting one fixed, deterministic error.

### GCS destination authorization does not explain the failure

We tested whether the failure is simply that `storage.googleapis.com` /
`storage.mtls.googleapis.com` were never allow-listed as Agent Registry
Services: we registered both and granted the Gateway-associated Runtime's
identity `roles/iap.egressor` on both endpoints, then repeated the
`run_query_job` attempt. **The failure was identical, and Agent Gateway's
own access log recorded zero entries for this Gateway (any hostname) during
either the before- or after-change attempt** -- in contrast to our ordinary
`query`/WebFetch traffic in the same project, which the Gateway does log
with an explicit `authzPolicyInfo.result`. We could not find any IAP or
Gateway log evidence that the query-job's connection was ever evaluated by
this Gateway's policy at all. Full detail:
`support/additional-verification-report-20260912.md`.

## Questions for Google

1. Is Agent Engine BYOC `run_query_job` supported at all when the Runtime
   has an `AGENT_TO_ANYWHERE` Agent Gateway association?
2. Does the query-job Cloud Storage input/output path execute through the
   Agent Gateway, including the component that appears in our logs as
   `proxy-container`? If so, why does allow-listing the destination in
   Agent Registry (with a matching IAP grant) produce no Gateway/IAP access
   log entry at all for this traffic, unlike ordinary application egress
   from the same Runtime?
3. If Gateway TLS inspection applies to this Google-managed, platform-internal
   path, what is the supported way for that platform component to trust or
   bypass the Gateway's certificate handling for its own GCS calls?
4. If this combination is not currently supported, what is the recommended
   architecture for a workload that needs both long-running query jobs and
   governed egress on the same Runtime?

## Evidence available on request (this project)

All evidence is sanitized and excludes tokens, request bodies, and
certificate private keys.

- `results/query-job-no-gateway-2.jsonl` -- baseline success trace (no Gateway).
- `results/evaluation-case1-no-gateway.json` -- baseline structured evaluation.
- `results/query-job-gateway.jsonl` -- failing attempt trace (Gateway-associated).
- `results/evaluation-case3-gateway.json` -- failing attempt structured evaluation.
- `results/case3-proxy-container-full-traceback.txt` -- the traceback quoted
  above, as plain text.
- `results/case3-proxy-container-traceback.json` -- full raw Cloud Logging
  entries for `proxy-container`/`job-container` during the failing attempt
  (timestamps, insertIds, labels), from which the traceback above was
  reconstructed.
- `terraform/` -- the complete, minimal Terraform configuration that
  reproduces this environment from an empty project (no external module
  dependencies).
- `support/additional-verification-report-20260912.md` and
  `results/additional-verification-20260912/` -- the GCS destination
  authorization test described above, including the empty Gateway-log
  query result and the operation terminal states.

## The same Gateway works correctly for ordinary application traffic

To confirm this Gateway is otherwise functioning correctly (i.e. the
failure above is specific to the query-job path, not a broken Gateway
configuration), the same Gateway-associated Runtime answered an ordinary
synchronous `query` call that fetches a URL directly from the application
container (no model involved -- see `byoc_runtime/adapter.py`):

- `https://github.com/74th` (registered in Agent Registry) -- fetched
  successfully, HTTP 200.
- `https://www.tohoho-web.com/index.htm` (not registered) -- HTTP 403.

The Gateway's own access log confirms both requests were TLS-intercepted and
evaluated by IAP authorization, with opposite outcomes:

| Field | `github.com` | `www.tohoho-web.com` |
| --- | --- | --- |
| `authzPolicyInfo.result` | `ALLOWED` | `DENIED` |
| `agentGatewayInfo.agentRegistryResource` | matched our registered endpoint | absent |
| `enforcedGatewaySecurityPolicy.requestWasTlsIntercepted` | `true` | `true` |

Evidence: `results/sync-query-gateway.txt`,
`results/default-deny-check.txt`, `results/gateway-default-deny-logs.json`.

This isolates the defect to the query-job GCS delivery path specifically:
the same Gateway, same Runtime, same Agent Registry configuration correctly
allow/deny ordinary application egress, but cannot deliver the platform's
own query-job input.

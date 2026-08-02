"""Start, monitor, and collect evidence for a long-running Agent Platform query job."""
from __future__ import annotations
import argparse, json, time, uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as output: output.write(json.dumps(value, default=str, ensure_ascii=False) + "\n")

def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("--project", required=True); p.add_argument("--location", required=True); p.add_argument("--agent-resource", required=True); p.add_argument("--output-gcs-uri", required=True); p.add_argument("--timeout-seconds", type=int, default=900); p.add_argument("--interval-seconds", type=int, default=30); p.add_argument("--result", type=Path, default=Path("results/query-job.jsonl")); args=p.parse_args()
    import agentplatform
    marker=f"query-job-{uuid.uuid4()}"; started=datetime.now(UTC); client=agentplatform.Client(project=args.project, location=args.location)
    response=client.agent_engines.run_query_job(name=args.agent_resource, config={"query": json.dumps({"input":{"verification_id":marker}}), "output_gcs_uri":args.output_gcs_uri})
    job_name=getattr(response, "job_name", None) or getattr(response, "name", None) or getattr(response, "operation_name", None)
    if not job_name: raise RuntimeError("run_query_job response did not include a job name")
    write(args.result, {"event":"started","marker":marker,"job_name":job_name,"started_at":started.isoformat(),"output_gcs_uri":args.output_gcs_uri})
    deadline=time.monotonic()+args.timeout_seconds
    timed_out = False
    while time.monotonic() < deadline:
        status=client.agent_engines.check_query_job(name=job_name, config={"retrieve_result":True})
        write(args.result, {"event":"status","marker":marker,"job_name":job_name,"checked_at":datetime.now(UTC).isoformat(),"status":status})
        if str(getattr(status,"state", "")).upper() in {"SUCCEEDED","FAILED","CANCELLED"}: break
        time.sleep(args.interval_seconds)
    else:
        timed_out = True
        write(args.result, {"event":"deadline_exceeded","marker":marker,"job_name":job_name})
    # Logging and GCS evidence are intentionally collected separately so missing permissions are evidence, not silent success.
    from google.cloud import logging as cloud_logging
    try:
        entries=list(cloud_logging.Client(project=args.project).list_entries(filter_=f'timestamp >= "{(started-timedelta(minutes=1)).isoformat()}" AND textPayload:"{marker}"', page_size=100))
        write(args.result, {"event":"log_evidence","marker":marker,"entries": [str(e) for e in entries]})
        result = "到達確認" if entries else ("判定不能" if timed_out else "未到達")
        reason = "コンテナ受信ログのマーカー検索結果" if not timed_out else "監視期限内にジョブが完了しなかったため"
        write(args.result, {"event":"reachability","marker":marker,"result":result,"reason":reason})
    except Exception as exc: write(args.result, {"event":"reachability","marker":marker,"result":"判定不能","reason":type(exc).__name__})
if __name__ == "__main__": main()

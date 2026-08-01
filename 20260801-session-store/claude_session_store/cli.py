from __future__ import annotations

import argparse
import json

from .claude import AgentSdkRunner
from .config import Settings
from .models import VerificationResult
from .service import resume, start
from .session_store import GoogleSessionStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Claude Agent SDK Session Store 検証")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("start")
    resume_parser = commands.add_parser("resume")
    resume_parser.add_argument("session_name", help="start が出力した完全な Session Store リソース名")
    args = parser.parse_args()
    try:
        settings = Settings.from_env()
        store, claude = GoogleSessionStore(settings), AgentSdkRunner(settings)
        result = start(store, claude) if args.command == "start" else resume(store, claude, args.session_name)
    except Exception as error:
        result = VerificationResult(); result.fail("configuration", error)
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

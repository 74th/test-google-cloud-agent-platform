#!/usr/bin/env python3
"""Run the fixed BigQuery public-data smoke test."""

from __future__ import annotations

import json
import os

from google.cloud import bigquery


QUERY = """
SELECT
  refresh_date,
  rank,
  term
FROM
  `bigquery-public-data.google_trends.international_top_rising_terms`
WHERE
  refresh_date = "2026-08-09"
  AND country_name = "Japan"
GROUP BY
  refresh_date,
  rank,
  term
ORDER BY
  refresh_date DESC,
  rank
LIMIT 100
"""


def main() -> int:
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise SystemExit("GOOGLE_CLOUD_PROJECT must be set")

    client = bigquery.Client(project=project_id)
    rows = list(client.query(QUERY).result())
    if not rows:
        print("NO_ROWS: query completed successfully but returned 0 rows")
        return 0

    print(f"ROWS: {len(rows)}")
    for row in rows:
        print(json.dumps(dict(row.items()), default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

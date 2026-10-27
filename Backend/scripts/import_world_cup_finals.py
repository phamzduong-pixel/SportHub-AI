"""Normalize the pinned OpenFootball World Cup files into the small finals pilot."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "knowledge" / "sports" / "world_cup"
SOURCE_DIR = DATA_DIR / "source"
EXPECTED = {
    1998: ("France", "Brazil", [0, 3], None),
    2002: ("Brazil", "Germany", [0, 2], None),
    2006: ("Italy", "France", [1, 1], [5, 3]),
    2010: ("Spain", "Netherlands", [0, 1], None),
    2014: ("Germany", "Argentina", [1, 0], None),
    2018: ("France", "Croatia", [4, 2], None),
    2022: ("Argentina", "France", [3, 3], [4, 2]),
}
REPOSITORY = "openfootball/worldcup.json"
REVISION = "865ae87ebe5044e808a3e6cfc7fd89a63beb368e"
SCHEMA_VERSION = "1.0.0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pair(value, *, field: str, year: int) -> list[int]:
    if not isinstance(value, list) or len(value) != 2 or any(not isinstance(item, int) for item in value):
        raise ValueError(f"Invalid {field} score pair in {year}.")
    return value


def build_records() -> tuple[list[dict], list[dict]]:
    records = []
    source_files = []
    for year, expected in EXPECTED.items():
        path = SOURCE_DIR / str(year) / "worldcup.json"
        raw = path.read_bytes()
        tournament = json.loads(raw.decode("utf-8"))
        matches = tournament.get("matches")
        if not isinstance(matches, list):
            raise ValueError(f"Missing matches list in {path}.")
        finals = [(index, match) for index, match in enumerate(matches, 1) if match.get("round", "").casefold() == "final"]
        if len(finals) != 1:
            raise ValueError(f"Expected exactly one final in {year}; found {len(finals)}.")
        source_index, final = finals[0]
        score = final.get("score")
        if not isinstance(score, dict):
            raise ValueError(f"Invalid score format in {year} final.")
        score_90 = pair(score.get("ft"), field="ft", year=year)
        went_to_extra_time = "et" in score
        after_extra_time = pair(score.get("et", score_90), field="et", year=year)
        penalty_score = pair(score["p"], field="p", year=year) if "p" in score else None
        team1, team2 = final.get("team1"), final.get("team2")
        deciding_score = penalty_score or after_extra_time
        if deciding_score[0] == deciding_score[1]:
            raise ValueError(f"Final has no unique winner in {year}.")
        champion, runner_up = (team1, team2) if deciding_score[0] > deciding_score[1] else (team2, team1)
        if (champion, runner_up, after_extra_time, penalty_score) != expected:
            raise ValueError(f"Independent result cross-check failed for {year}: {(champion, runner_up, after_extra_time, penalty_score)}.")
        source_path = f"{year}/worldcup.json"
        source_url = f"https://github.com/{REPOSITORY}/blob/{REVISION}/{source_path}"
        records.append({
            "year": year,
            "competition": "FIFA World Cup",
            "stage": "Final",
            "team1": team1,
            "team2": team2,
            "score_90": score_90,
            "score_after_extra_time": after_extra_time,
            "went_to_extra_time": went_to_extra_time,
            "penalty_score": penalty_score,
            "champion": champion,
            "runner_up": runner_up,
            "provenance": {
                "repository": REPOSITORY,
                "revision": REVISION,
                "path": source_path,
                "record_index": source_index,
                "source_url": source_url,
            },
        })
        source_files.append({
            "path": f"source/{source_path}",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "match_count": len(matches),
            "final_count": len(finals),
        })

    if len({record["year"] for record in records}) != len(records):
        raise ValueError("Duplicate World Cup final records found.")
    return records, source_files


def write_pilot() -> None:
    records, source_files = build_records()
    finals_path = DATA_DIR / "finals.json"
    finals_path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    external_checks = [
        {"year": year, "champion": expected[0], "runner_up": expected[1], "score_after_extra_time": expected[2], "penalty_score": expected[3]}
        for year, expected in EXPECTED.items()
    ]
    manifest = {
        "dataset": "SportHub Natural Mode FIFA World Cup finals pilot",
        "schema_version": SCHEMA_VERSION,
        "source": {
            "repository": REPOSITORY,
            "url": f"https://github.com/{REPOSITORY}",
            "revision": REVISION,
            "license": "CC0-1.0 / public domain per repository README and LICENSE.md",
            "attribution": "No attribution required by CC0; provenance retained and attribution recommended.",
            "license_url": f"https://github.com/{REPOSITORY}/blob/{REVISION}/LICENSE.md",
        },
        "collected_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope_years": list(EXPECTED),
        "files": source_files + [{"path": "finals.json", "sha256": sha256(finals_path), "bytes": finals_path.stat().st_size}],
        "record_count": len(records),
        "validation": {
            "source_json_parses": True,
            "one_final_per_year": True,
            "duplicates_or_conflicts": 0,
            "score_and_winner_invariants": True,
            "independent_cross_check": {
                "source": "RSSSF World Cup 1930-2026 finals table",
                "url": "https://www.rsssf.org/tablesw/worldcup.html",
                "license": "UNKNOWN; used for verification only and not copied into dataset",
                "results": external_checks,
            },
        },
        "approval_status": "approved_for_pilot_by_user_request",
    }
    manifest_path = DATA_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {len(records)} finals to {finals_path}")
    print(f"Wrote manifest {manifest_path}")


if __name__ == "__main__":
    write_pilot()

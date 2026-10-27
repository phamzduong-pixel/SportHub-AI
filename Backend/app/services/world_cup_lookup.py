"""Offline deterministic lookup for the approved FIFA World Cup finals pilot."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


SOURCE_REPOSITORY = "openfootball/worldcup.json"
SOURCE_COMMIT = "865ae87ebe5044e808a3e6cfc7fd89a63beb368e"
SUPPORTED_YEARS = (1998, 2002, 2006, 2010, 2014, 2018, 2022)
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "knowledge" / "sports" / "world_cup"
FINALS_PATH = DATA_DIR / "finals.json"

WORLD_CUP_ALIASES = (
    "world cup", "worldcup", "fifa world cup", "cup the gioi", "world championship",
)
RESULT_TERMS = (
    "vo dich", "quan quan", "nha vo dich", "champion", "winner", "won", "win", "ai thang", "thang ai",
    "chung ket", "final", "ket qua", "ty so", "score", "runner up", "a quan",
)
FOLLOW_UP_TERMS = ("con nam", "nam nao", "the nam", "va nam", "con ky", "ky do", "thong tin do")
TEAM_ALIASES = {
    "phap": "France",
    "france": "France",
    "duc": "Germany",
    "germany": "Germany",
    "italy": "Italy",
    "y": "Italy",
    "tay ban nha": "Spain",
    "spain": "Spain",
    "ha lan": "Netherlands",
    "netherlands": "Netherlands",
    "argentina": "Argentina",
    "brazil": "Brazil",
    "croatia": "Croatia",
}


class WorldCupDatasetError(ValueError):
    """Raised when local pilot data is missing, duplicated, or inconsistent."""


@dataclass(frozen=True)
class WorldCupLookupResult:
    status: str
    records: tuple[dict[str, Any], ...] = ()
    years: tuple[int, ...] = ()
    missing_years: tuple[int, ...] = ()


def normalize_text(value: str | None) -> str:
    decomposed = unicodedata.normalize("NFD", (value or "").casefold())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn").replace("đ", "d")


def canonicalize_team(name: str) -> str | None:
    return TEAM_ALIASES.get(normalize_text(name))


def validate_records(records: list[dict[str, Any]], expected_years: tuple[int, ...] = SUPPORTED_YEARS) -> dict[int, dict[str, Any]]:
    """Validate record uniqueness and score/winner invariants; fail closed on conflict."""
    indexed: dict[int, dict[str, Any]] = {}
    for record in records:
        try:
            year = int(record["year"])
            finalists = {record["team1"], record["team2"]}
            regulation = record["score_90"]
            after_extra_time = record["score_after_extra_time"]
            penalties = record.get("penalty_score")
            champion = record["champion"]
            runner_up = record["runner_up"]
        except (KeyError, TypeError, ValueError) as exc:
            raise WorldCupDatasetError(f"Malformed World Cup final record: {exc}") from exc

        if year in indexed:
            kind = "conflicting" if indexed[year] != record else "duplicate"
            raise WorldCupDatasetError(f"{kind.capitalize()} World Cup final records for {year}.")
        if year not in expected_years:
            raise WorldCupDatasetError(f"Unexpected World Cup year {year}.")
        if champion not in finalists or runner_up not in finalists or champion == runner_up:
            raise WorldCupDatasetError(f"Invalid finalists or outcome for {year}.")
        if not isinstance(regulation, list) or len(regulation) != 2 or not isinstance(after_extra_time, list) or len(after_extra_time) != 2:
            raise WorldCupDatasetError(f"Invalid score pair for {year}.")
        if penalties is not None and (not isinstance(penalties, list) or len(penalties) != 2):
            raise WorldCupDatasetError(f"Invalid penalty score for {year}.")

        deciding_score = penalties if penalties is not None else after_extra_time
        winner = record["team1"] if deciding_score[0] > deciding_score[1] else record["team2"]
        if deciding_score[0] == deciding_score[1] or winner != champion:
            raise WorldCupDatasetError(f"Winner does not match the final score for {year}.")
        indexed[year] = record

    if set(indexed) != set(expected_years):
        missing = sorted(set(expected_years) - set(indexed))
        extra = sorted(set(indexed) - set(expected_years))
        raise WorldCupDatasetError(f"World Cup year coverage mismatch; missing={missing}, extra={extra}.")
    return indexed


@lru_cache(maxsize=1)
def load_world_cup_finals() -> dict[int, dict[str, Any]]:
    try:
        records = json.loads(FINALS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorldCupDatasetError(f"World Cup pilot data could not be loaded: {exc}") from exc
    if not isinstance(records, list):
        raise WorldCupDatasetError("World Cup finals data must be a JSON list.")
    return validate_records(records)


def _is_world_cup_query(query: str, competition: str | None, context: dict[str, Any] | None) -> bool:
    normalized = normalize_text(query)
    competition_text = normalize_text(competition or "")
    previous_competition = normalize_text((context or {}).get("competition") or "")
    markers = tuple(normalize_text(marker) for marker in WORLD_CUP_ALIASES)
    return any(marker in normalized for marker in markers) or any(
        "world cup" in value or "worldcup" in value or "cup the gioi" in value
        for value in (competition_text, previous_competition)
    )


def _has_result_intent(query: str, context: dict[str, Any] | None) -> bool:
    normalized = normalize_text(query)
    if any(normalize_text(term) in normalized for term in RESULT_TERMS):
        return True
    return bool(
        (context or {}).get("competition")
        and re.search(r"\b(?:con|va|theo|so sanh)\b", normalized)
        and re.search(r"\b(?:19|20)\d{2}\b", normalized)
    )


def _requested_years(query: str, route_year: str | int | None, context: dict[str, Any] | None) -> tuple[int, ...] | None:
    normalized = normalize_text(query)
    years = [int(value) for value in re.findall(r"\b(?:19|20)\d{2}\b", normalized)]
    if len(years) >= 2 and re.search(r"\b(?:den|toi|through|to)\b|[-–—]", normalized):
        start, end = years[0], years[1]
        if start > end:
            start, end = end, start
        return tuple(year for year in range(start, end + 1) if (year - 1998) % 4 == 0)
    if years:
        return (years[0],)
    if route_year is not None:
        try:
            return (int(route_year),)
        except (TypeError, ValueError):
            pass
    previous_year = (context or {}).get("year") or (context or {}).get("competition_year")
    if previous_year is not None:
        try:
            return (int(previous_year),)
        except (TypeError, ValueError):
            pass
    return None


def lookup_world_cup_query(
    query: str,
    *,
    competition: str | None = None,
    route_year: str | int | None = None,
    context: dict[str, Any] | None = None,
) -> WorldCupLookupResult | None:
    """Return a deterministic result only for World Cup champion/final questions."""
    if not _is_world_cup_query(query, competition, context) or not _has_result_intent(query, context):
        return None
    years = _requested_years(query, route_year, context)
    if years is None:
        return WorldCupLookupResult(status="needs_year")
    dataset = load_world_cup_finals()
    records = tuple(dataset[year] for year in years if year in dataset)
    missing_years = tuple(year for year in years if year not in dataset)
    if missing_years:
        return WorldCupLookupResult(status="missing_data", records=records, years=years, missing_years=missing_years)
    return WorldCupLookupResult(status="found", records=records, years=years)


def format_world_cup_answer(result: WorldCupLookupResult) -> str:
    if result.status == "needs_year":
        return "Bạn muốn hỏi kỳ FIFA World Cup năm nào? Kho dữ liệu pilot có các kỳ 1998, 2002, 2006, 2010, 2014, 2018 và 2022."
    if result.status == "missing_data":
        years = ", ".join(str(year) for year in result.missing_years)
        partial = ""
        available_years = tuple(year for year in result.years if year not in result.missing_years)
        if result.records and available_years:
            partial = format_world_cup_answer(WorldCupLookupResult(
                status="found", records=result.records, years=available_years,
            )) + "\n\n"
        return partial + f"SportHub AI chưa có dữ liệu World Cup đã kiểm chứng cho năm {years}; mình không thể kết luận hoặc tra cứu mạng trong phiên này."
    if not result.records:
        return "Kho dữ liệu pilot không có kỳ World Cup nào trong khoảng năm bạn hỏi."
    answers = []
    for record in result.records:
        champion = record["champion"]
        runner_up = record["runner_up"]
        score_90 = record["score_90"]
        after_extra_time = record["score_after_extra_time"]
        line = f"**{record['year']}**: {champion} vô địch, {runner_up} á quân; chung kết {record['team1']} {after_extra_time[0]}–{after_extra_time[1]} {record['team2']}"
        if record.get("went_to_extra_time"):
            line += f" sau hiệp phụ (90 phút: {score_90[0]}–{score_90[1]})"
        if record.get("penalty_score"):
            penalties = record["penalty_score"]
            line += f"; luân lưu {penalties[0]}–{penalties[1]}"
        answers.append(line + ".")
    cited_years = result.years
    citations = []
    for year in cited_years:
        relative_path = f"{year}/worldcup.json"
        source_url = f"https://github.com/{SOURCE_REPOSITORY}/blob/{SOURCE_COMMIT}/{relative_path}"
        citations.append(f"[{SOURCE_REPOSITORY} {year}]({source_url})")
    return "\n".join(answers) + "\n\nNguồn: " + "; ".join(citations) + "."

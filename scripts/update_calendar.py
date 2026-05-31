#!/usr/bin/env python3
"""Fetch FIFA World Cup 2026 fixtures and generate an Apple Calendar friendly ICS."""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


FIFA_API_URL = (
    "https://api.fifa.com/api/v3/calendar/matches"
    "?from=2026-06-01T00%3A00%3A00Z"
    "&to=2026-07-31T23%3A59%3A59Z"
    "&language=en"
    "&count=500"
    "&idCompetition=17"
)

OUTPUT_PATH = Path("docs/worldcup-2026.ics")
CACHE_PATH = Path("data/fifa-worldcup-2026.json")
EVENT_DURATION = timedelta(hours=2)

REAL_STADIUM_LOCATIONS = {
    "Atlanta Stadium": "Mercedes-Benz Stadium, Atlanta, GA",
    "BC Place Vancouver": "BC Place, Vancouver, BC",
    "Boston Stadium": "Gillette Stadium, Foxborough, MA",
    "Dallas Stadium": "AT&T Stadium, Arlington, TX",
    "Guadalajara Stadium": "Estadio Akron, Zapopan, Jalisco",
    "Houston Stadium": "NRG Stadium, Houston, TX",
    "Kansas City Stadium": "GEHA Field at Arrowhead Stadium, Kansas City, MO",
    "Los Angeles Stadium": "SoFi Stadium, Inglewood, CA",
    "Mexico City Stadium": "Estadio Azteca, Mexico City",
    "Miami Stadium": "Hard Rock Stadium, Miami Gardens, FL",
    "Monterrey Stadium": "Estadio BBVA, Guadalupe, Nuevo Leon",
    "New York/New Jersey Stadium": "MetLife Stadium, East Rutherford, NJ",
    "Philadelphia Stadium": "Lincoln Financial Field, Philadelphia, PA",
    "San Francisco Bay Area Stadium": "Levi's Stadium, Santa Clara, CA",
    "Seattle Stadium": "Lumen Field, Seattle, WA",
    "Toronto Stadium": "BMO Field, Toronto, ON",
}


def localized(value: Any, fallback: str = "") -> str:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("Description"):
                return str(item["Description"])
        return fallback
    if isinstance(value, str):
        return value
    return fallback


def parse_utc(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    return parsed.astimezone(timezone.utc)


def format_ics_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def escape_ics_text(value: str) -> str:
    value = value.replace("\\", "\\\\")
    value = value.replace(";", r"\;")
    value = value.replace(",", r"\,")
    value = value.replace("\r\n", r"\n").replace("\n", r"\n")
    return value


def fold_ics_line(line: str) -> str:
    """Fold a content line at 75 octets, preserving UTF-8 boundaries."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line

    parts: list[str] = []
    current = ""
    current_len = 0
    for char in line:
        char_len = len(char.encode("utf-8"))
        limit = 75 if not parts else 74
        if current and current_len + char_len > limit:
            parts.append(current)
            current = char
            current_len = char_len
        else:
            current += char
            current_len += char_len
    if current:
        parts.append(current)

    return "\r\n ".join(parts)


def content_line(name: str, value: str) -> str:
    return fold_ics_line(f"{name}:{escape_ics_text(value)}")


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "worldcup-calendar/1.0 (+https://github.com/Jason-lewis-526/Worldcup-Calendar)",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def load_fixture_data() -> dict[str, Any]:
    try:
        data = fetch_json(FIFA_API_URL)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        if CACHE_PATH.exists():
            print(f"FIFA fetch failed, using cached data: {exc}", file=sys.stderr)
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        raise

    matches = data.get("Results", [])
    if not isinstance(matches, list) or len(matches) < 100:
        raise RuntimeError(f"Unexpected FIFA response: found {len(matches) if isinstance(matches, list) else 'no'} matches")

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def team_label(match: dict[str, Any], side: str) -> str:
    team = match.get(side)
    if isinstance(team, dict):
        return team.get("ShortClubName") or localized(team.get("TeamName")) or team.get("Abbreviation") or "TBD"

    placeholder_key = "PlaceHolderA" if side == "Home" else "PlaceHolderB"
    placeholder = match.get(placeholder_key)
    if placeholder:
        return format_placeholder(str(placeholder))

    return "TBD"


def format_placeholder(value: str) -> str:
    winner = re.fullmatch(r"W(\d+)", value)
    if winner:
        return f"Winner M{winner.group(1)}"

    runner_up = re.fullmatch(r"RU(\d+)", value)
    if runner_up:
        return f"Runner-up M{runner_up.group(1)}"

    return value


def event_summary(match: dict[str, Any]) -> str:
    return f"{team_label(match, 'Home')} vs {team_label(match, 'Away')}"


def event_location(match: dict[str, Any]) -> str:
    stadium = match.get("Stadium")
    if not isinstance(stadium, dict):
        return ""

    stadium_name = localized(stadium.get("Name"))
    if stadium_name in REAL_STADIUM_LOCATIONS:
        return REAL_STADIUM_LOCATIONS[stadium_name]

    city = localized(stadium.get("CityName"))
    if stadium_name and city:
        return f"{stadium_name}, {city}"
    return stadium_name or city


def event_sequence(match: dict[str, Any]) -> str:
    updated = match.get("LastPeriodUpdate")
    if isinstance(updated, str) and updated:
        digits = re.sub(r"\D", "", updated)
        return str(int(digits[:9] or "0"))
    return str(int(match.get("MatchStatus") or 0))


def build_event(match: dict[str, Any], generated_at: datetime) -> list[str]:
    start = parse_utc(match["Date"])
    end = start + EVENT_DURATION
    match_id = str(match["IdMatch"])

    lines = [
        "BEGIN:VEVENT",
        content_line("UID", f"fifa-worldcup-2026-match-{match_id}@worldcup-calendar"),
        f"DTSTAMP:{format_ics_datetime(generated_at)}",
        f"DTSTART:{format_ics_datetime(start)}",
        f"DTEND:{format_ics_datetime(end)}",
        content_line("SUMMARY", event_summary(match)),
        content_line("LOCATION", event_location(match)),
        content_line("SEQUENCE", event_sequence(match)),
        "TRANSP:OPAQUE",
        "STATUS:CONFIRMED",
        "END:VEVENT",
    ]
    return lines


def build_calendar(matches: list[dict[str, Any]]) -> str:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0)
    sorted_matches = sorted(matches, key=lambda item: (item.get("Date", ""), item.get("MatchNumber", 0)))

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Jason-lewis-526//World Cup 2026 Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:World Cup 2026",
        "X-WR-TIMEZONE:UTC",
        "REFRESH-INTERVAL;VALUE=DURATION:PT15M",
        "X-PUBLISHED-TTL:PT15M",
    ]

    for match in sorted_matches:
        if match.get("Date") and match.get("IdMatch"):
            lines.extend(build_event(match, generated_at))

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main() -> None:
    data = load_fixture_data()
    matches = data["Results"]
    calendar = build_calendar(matches)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as output:
        output.write(calendar)
    print(f"Wrote {OUTPUT_PATH} with {len(matches)} matches")


if __name__ == "__main__":
    main()

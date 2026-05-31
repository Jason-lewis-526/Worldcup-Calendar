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


FIFA_API_BASE_URL = (
    "https://api.fifa.com/api/v3/calendar/matches"
    "?from=2026-06-01T00%3A00%3A00Z"
    "&to=2026-07-31T23%3A59%3A59Z"
    "&count=500"
    "&idCompetition=17"
)

EVENT_DURATION = timedelta(hours=2)

EN_STADIUM_LOCATIONS = {
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

ZH_STADIUM_LOCATIONS = {
    "Atlanta Stadium": "梅赛德斯-奔驰体育场，亚特兰大，GA",
    "BC Place Vancouver": "BC Place，温哥华，BC",
    "Boston Stadium": "吉列体育场，福克斯堡，MA",
    "Dallas Stadium": "AT&T 体育场，阿灵顿，TX",
    "Guadalajara Stadium": "阿克伦体育场，萨波潘，哈利斯科",
    "Houston Stadium": "NRG 体育场，休斯顿，TX",
    "Kansas City Stadium": "箭头体育场，堪萨斯城，MO",
    "Los Angeles Stadium": "SoFi 体育场，英格尔伍德，CA",
    "Mexico City Stadium": "阿兹特克体育场，墨西哥城",
    "Miami Stadium": "硬石体育场，迈阿密花园，FL",
    "Monterrey Stadium": "BBVA 体育场，瓜达卢佩，新莱昂",
    "New York/New Jersey Stadium": "大都会人寿体育场，东卢瑟福，NJ",
    "Philadelphia Stadium": "林肯金融球场，费城，PA",
    "San Francisco Bay Area Stadium": "李维斯体育场，圣克拉拉，CA",
    "Seattle Stadium": "流明球场，西雅图，WA",
    "Toronto Stadium": "BMO 球场，多伦多，ON",
}

CALENDARS = [
    {
        "language": "en",
        "output_path": Path("docs/worldcup-2026.ics"),
        "cache_path": Path("data/fifa-worldcup-2026.json"),
        "calendar_name": "World Cup 2026",
        "prodid": "-//Jason-lewis-526//World Cup 2026 Calendar//EN",
        "prefer_localized_team_name": False,
        "stadium_locations": EN_STADIUM_LOCATIONS,
    },
    {
        "language": "zh",
        "output_path": Path("docs/worldcup-2026-zh.ics"),
        "cache_path": Path("data/fifa-worldcup-2026-zh.json"),
        "calendar_name": "2026 世界杯",
        "prodid": "-//Jason-lewis-526//World Cup 2026 Calendar//ZH",
        "prefer_localized_team_name": True,
        "stadium_locations": ZH_STADIUM_LOCATIONS,
    },
]


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


def fifa_api_url(language: str) -> str:
    return f"{FIFA_API_BASE_URL}&language={language}"


def load_fixture_data(config: dict[str, Any]) -> dict[str, Any]:
    cache_path = config["cache_path"]
    try:
        data = fetch_json(fifa_api_url(config["language"]))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        if cache_path.exists():
            print(f"FIFA fetch failed, using cached data: {exc}", file=sys.stderr)
            return json.loads(cache_path.read_text(encoding="utf-8"))
        raise

    matches = data.get("Results", [])
    if not isinstance(matches, list) or len(matches) < 100:
        raise RuntimeError(f"Unexpected FIFA response: found {len(matches) if isinstance(matches, list) else 'no'} matches")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def team_label(match: dict[str, Any], side: str, config: dict[str, Any]) -> str:
    team = match.get(side)
    if isinstance(team, dict):
        localized_name = localized(team.get("TeamName"))
        if config["prefer_localized_team_name"] and localized_name:
            return localized_name
        return team.get("ShortClubName") or localized_name or team.get("Abbreviation") or "TBD"

    placeholder_key = "PlaceHolderA" if side == "Home" else "PlaceHolderB"
    placeholder = match.get(placeholder_key)
    if placeholder:
        return format_placeholder(str(placeholder), config["language"])

    return "待定" if config["language"] == "zh" else "TBD"


def format_placeholder(value: str, language: str) -> str:
    winner = re.fullmatch(r"W(\d+)", value)
    if winner:
        if language == "zh":
            return f"第{winner.group(1)}场胜者"
        return f"Winner M{winner.group(1)}"

    runner_up = re.fullmatch(r"RU(\d+)", value)
    if runner_up:
        if language == "zh":
            return f"第{runner_up.group(1)}场负者"
        return f"Runner-up M{runner_up.group(1)}"

    group_position = re.fullmatch(r"([123])([A-L]+)", value)
    if language == "zh" and group_position:
        position = group_position.group(1)
        groups = "/".join(group_position.group(2))
        return f"{groups}组第{position}名"

    return value


def event_summary(match: dict[str, Any], config: dict[str, Any]) -> str:
    return f"{team_label(match, 'Home', config)} vs {team_label(match, 'Away', config)}"


def event_location(match: dict[str, Any], config: dict[str, Any]) -> str:
    stadium = match.get("Stadium")
    if not isinstance(stadium, dict):
        return ""

    stadium_name = localized(stadium.get("Name"))
    stadium_locations = config["stadium_locations"]
    if stadium_name in stadium_locations:
        return stadium_locations[stadium_name]

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


def build_event(match: dict[str, Any], generated_at: datetime, config: dict[str, Any]) -> list[str]:
    start = parse_utc(match["Date"])
    end = start + EVENT_DURATION
    match_id = str(match["IdMatch"])

    lines = [
        "BEGIN:VEVENT",
        content_line("UID", f"fifa-worldcup-2026-match-{match_id}@worldcup-calendar"),
        f"DTSTAMP:{format_ics_datetime(generated_at)}",
        f"DTSTART:{format_ics_datetime(start)}",
        f"DTEND:{format_ics_datetime(end)}",
        content_line("SUMMARY", event_summary(match, config)),
        content_line("LOCATION", event_location(match, config)),
        content_line("SEQUENCE", event_sequence(match)),
        "TRANSP:OPAQUE",
        "STATUS:CONFIRMED",
        "END:VEVENT",
    ]
    return lines


def build_calendar(matches: list[dict[str, Any]], config: dict[str, Any]) -> str:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0)
    sorted_matches = sorted(matches, key=lambda item: (item.get("Date", ""), item.get("MatchNumber", 0)))

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{config['prodid']}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        content_line("X-WR-CALNAME", config["calendar_name"]),
        "X-WR-TIMEZONE:UTC",
        "REFRESH-INTERVAL;VALUE=DURATION:PT15M",
        "X-PUBLISHED-TTL:PT15M",
    ]

    for match in sorted_matches:
        if match.get("Date") and match.get("IdMatch"):
            lines.extend(build_event(match, generated_at, config))

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main() -> None:
    for config in CALENDARS:
        data = load_fixture_data(config)
        matches = data["Results"]
        calendar = build_calendar(matches, config)
        output_path = config["output_path"]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as output:
            output.write(calendar)
        print(f"Wrote {output_path} with {len(matches)} matches")


if __name__ == "__main__":
    main()

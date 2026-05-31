# World Cup 2026 Calendar

Auto-updated Apple Calendar feeds for the FIFA World Cup 2026.

English subscription URL:

```text
https://raw.githubusercontent.com/Jason-lewis-526/Worldcup-Calendar/main/docs/worldcup-2026.ics
```

English Apple Calendar shortcut:

```text
webcal://raw.githubusercontent.com/Jason-lewis-526/Worldcup-Calendar/main/docs/worldcup-2026.ics
```

Chinese subscription URL:

```text
https://raw.githubusercontent.com/Jason-lewis-526/Worldcup-Calendar/main/docs/worldcup-2026-zh.ics
```

Chinese Apple Calendar shortcut:

```text
webcal://raw.githubusercontent.com/Jason-lewis-526/Worldcup-Calendar/main/docs/worldcup-2026-zh.ics
```

The generated calendar keeps each event simple:

```text
Mexico vs South Africa
Kickoff time shown in the subscriber's local timezone
Estadio Azteca, Mexico City
```

Chinese feed example:

```text
墨西哥 vs 南非
Kickoff time shown in the subscriber's local timezone
阿兹特克体育场，墨西哥城
```

## How It Updates

- `scripts/update_calendar.py` fetches FIFA's public match calendar API for the 2026 World Cup.
- The script generates `docs/worldcup-2026.ics` and `docs/worldcup-2026-zh.ics`.
- GitHub Actions runs every 15 minutes and commits changes when FIFA data changes.
- Match event `UID` values use FIFA match IDs, so knockout fixtures update in place when teams are confirmed.

Apple Calendar decides how often to refresh subscribed calendars, so updates are not guaranteed to appear instantly on every device.

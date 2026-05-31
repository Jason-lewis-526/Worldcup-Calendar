# World Cup 2026 Calendar

Auto-updated Apple Calendar feed for the FIFA World Cup 2026.

Subscription URL:

```text
https://jason-lewis-526.github.io/Worldcup-Calendar/worldcup-2026.ics
```

Apple Calendar shortcut:

```text
webcal://jason-lewis-526.github.io/Worldcup-Calendar/worldcup-2026.ics
```

The generated calendar keeps each event simple:

```text
Mexico vs South Africa
Kickoff time shown in the subscriber's local timezone
Estadio Azteca, Mexico City
```

## How It Updates

- `scripts/update_calendar.py` fetches FIFA's public match calendar API for the 2026 World Cup.
- The script generates `docs/worldcup-2026.ics`.
- GitHub Actions runs every 15 minutes and commits changes when FIFA data changes.
- Match event `UID` values use FIFA match IDs, so knockout fixtures update in place when teams are confirmed.

Apple Calendar decides how often to refresh subscribed calendars, so updates are not guaranteed to appear instantly on every device.

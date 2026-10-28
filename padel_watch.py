#!/usr/bin/env python3
"""Peakz Padel Paderborn – Storno-Wächter.

Prüft die Verfügbarkeit der 2-vs-2-Plätze an den kommenden Samstagen/Sonntagen
und schickt eine Push-Nachricht (ntfy), sobald ein Slot frei wird, der beim
letzten Lauf noch belegt war (= Stornierung).

Nur Python-Standardbibliothek. Konfiguration über Umgebungsvariablen.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# --- Konfiguration ----------------------------------------------------------
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
WEEKENDS_AHEAD = int(os.environ.get("WEEKENDS_AHEAD", "2"))   # wie viele Wochenenden
DURATIONS = {int(x) for x in os.environ.get("DURATIONS", "90").split(",") if x.strip()}
EARLIEST = os.environ.get("EARLIEST", "00:00")                # z. B. "10:00"
LATEST = os.environ.get("LATEST", "23:59")                    # letzte Startzeit
STATE_FILE = Path(os.environ.get("STATE_FILE", "state.json"))
TEST_PUSH = os.environ.get("TEST_PUSH", "").lower() in ("1", "true", "yes")

# Peakz Padel Paderborn – An den Lothewiesen (aus der Buchungsseite ausgelesen)
API = "https://api.foys.io/court-booking/public/api/v1/locations/search"
LOCATION_ID = "1346d3f3-c514-419a-b849-62a748cf0d25"
RESERVATION_TYPE_ID = 157
COURT_TYPE_ID = 87  # Double Indoor (2 vs 2)
HEADERS = {
    "Accept": "application/json",
    "X-FederationID": "d27e57c1-fdd0-4e52-8a2d-93f3197e2752",
    "X-OrganisationId": "18903614-c9b9-42c7-341d-08dcb7b2d3b8",
    "User-Agent": "padel-storno-waechter/1.0",
}
BOOKING_URL = (
    "https://www.peakzpadel.de/buchen/court-booking/reservation"
    "?daypart=---&date={date}&location=An%20den%20Lothewiesen&courtTypeIds=87"
)
TZ = ZoneInfo("Europe/Berlin")
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def weekend_dates(today: date, n: int) -> list[date]:
    """Sa/So der nächsten n Wochenenden (inkl. heute, falls Wochenende)."""
    days_to_sat = (5 - today.weekday()) % 7
    sat = today + timedelta(days=days_to_sat)
    if today.weekday() == 6:  # Sonntag: heute zählt noch, Samstag ist vorbei
        sat = today - timedelta(days=1)
    out: list[date] = []
    for i in range(n):
        s = sat + timedelta(weeks=i)
        out += [d for d in (s, s + timedelta(days=1)) if d >= today]
    return out


def fetch_day(d: date) -> list[dict]:
    params = [
        ("reservationTypeId", RESERVATION_TYPE_ID),
        ("locationId", LOCATION_ID),
        *[("playingTimes[]", t) for t in (60, 90, 120)],
        ("date", f"{d.isoformat()}T00:00"),
    ]
    url = f"{API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def slots_for_day(data: list[dict], now: datetime) -> dict[str, bool]:
    """{"<court>|<start>|<dauer>": isAvailable} für passende 2-vs-2-Slots."""
    result: dict[str, bool] = {}
    for loc in data:
        for court in loc.get("inventoryItemsTimeSlots", []):
            if (court.get("inventoryItemType") or {}).get("id") != COURT_TYPE_ID:
                continue
            for ts in court.get("timeSlots", []):
                if ts.get("duration") not in DURATIONS:
                    continue
                start = datetime.fromisoformat(ts["startTime"]).replace(tzinfo=TZ)
                if start <= now:
                    continue
                hhmm = start.strftime("%H:%M")
                if not (EARLIEST <= hhmm <= LATEST):
                    continue
                key = f"{court['name']}|{ts['startTime']}|{ts['duration']}"
                result[key] = bool(ts.get("isAvailable"))
    return result


def push(title: str, message: str, click: str | None = None) -> None:
    if not NTFY_TOPIC:
        print("NTFY_TOPIC fehlt – Push übersprungen:\n", title, "\n", message)
        return
    body = {"topic": NTFY_TOPIC, "title": title, "message": message, "priority": 4}
    if click:
        body["click"] = click
        body["actions"] = [{"action": "view", "label": "Jetzt buchen", "url": click}]
    req = urllib.request.Request(
        NTFY_SERVER, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=30).read()


def fmt_day(d: date) -> str:
    return f"{WEEKDAYS[d.weekday()]} {d.strftime('%d.%m.')}"


def main() -> int:
    now = datetime.now(TZ)
    if TEST_PUSH:
        push("Padel-Wächter: Test", "Push kommt an – der Wächter ist eingerichtet.",
             BOOKING_URL.format(date=now.date().isoformat()))

    old: dict[str, dict[str, bool]] = {}
    if STATE_FILE.exists():
        old = json.loads(STATE_FILE.read_text())

    new: dict[str, dict[str, bool]] = {}
    errors = 0
    for d in weekend_dates(now.date(), WEEKENDS_AHEAD):
        key = d.isoformat()
        try:
            cur = slots_for_day(fetch_day(d), now)
        except Exception as e:  # API kurz weg → alten Stand behalten, nichts melden
            print(f"Fehler bei {key}: {e}", file=sys.stderr)
            errors += 1
            if key in old:
                new[key] = old[key]
            continue
        new[key] = cur
        prev = old.get(key)
        if prev is None:  # Tag zum ersten Mal gesehen → nur Stand merken
            print(f"{key}: Basis gespeichert ({sum(cur.values())} frei / {len(cur)})")
            continue

        freed = sorted(k for k, avail in cur.items() if avail and prev.get(k) is False)
        print(f"{key}: {sum(cur.values())} frei / {len(cur)}, neu frei: {len(freed)}")
        if not freed:
            continue

        by_court: dict[str, list[str]] = {}
        for k in freed:
            court, start, dur = k.split("|")
            by_court.setdefault(court, []).append(f"{start[11:16]} ({dur}′)")
        lines = [f"{c}: {', '.join(t)}" for c, t in sorted(by_court.items())]
        push(f"🎾 Padel frei: {fmt_day(d)}", "\n".join(lines), BOOKING_URL.format(date=key))

    STATE_FILE.write_text(json.dumps(new, indent=0, sort_keys=True))
    return 1 if errors and errors == len(weekend_dates(now.date(), WEEKENDS_AHEAD)) else 0


if __name__ == "__main__":
    sys.exit(main())

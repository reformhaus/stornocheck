# Padel Storno-Wächter (Peakz Paderborn)

Prüft alle ~5 Minuten die 2-vs-2-Plätze an den nächsten zwei Wochenenden und schickt
einen Push aufs iPhone, wenn ein 90-Min.-Slot frei wird, der vorher belegt war.

## Einrichtung (ca. 10 Min.)

1. **ntfy-App** auf dem iPhone installieren (App Store: „ntfy“). In der App auf **+**
   tippen und ein eigenes, schwer zu ratendes Topic abonnieren, z. B.
   `padel-julian-7k3x9q`. (Topics sind öffentlich – wer den Namen kennt, kann mitlesen.)
2. **GitHub-Repo anlegen**, am besten **öffentlich** (dann sind die Actions-Minuten
   unbegrenzt kostenlos; bei privaten Repos reichen die 2.000 Freiminuten nicht für einen
   5-Min.-Takt). Den Inhalt dieses Ordners hochladen – inkl. `.github/workflows/`.
3. Im Repo: **Settings → Secrets and variables → Actions → New repository secret**
   Name `NTFY_TOPIC`, Wert = dein Topic aus Schritt 1.
4. **Actions → Padel Storno-Wächter → Run workflow** (Test-Push angehakt) starten.
   Es sollte ein Test-Push ankommen. Danach läuft der Wächter automatisch.

## Anpassen

In `.github/workflows/padel-watch.yml`:

| Variable         | Standard | Bedeutung                                  |
|------------------|----------|--------------------------------------------|
| `WEEKENDS_AHEAD` | `2`      | Wie viele Wochenenden überwacht werden (max. sinnvoll: 4, Buchungsfenster 28 Tage) |
| `DURATIONS`      | `90`     | Spieldauern, z. B. `60,90,120`             |
| `EARLIEST`       | `00:00`  | Früheste Startzeit                         |
| `LATEST`         | `23:59`  | Späteste Startzeit                         |

## Gut zu wissen

- Der erste Lauf merkt sich nur den Stand – Pushes kommen erst ab Lauf 2.
- Pro Tag und Lauf gibt es höchstens einen Push; er listet alle neu freien Startzeiten
  und öffnet beim Tippen direkt die Buchungsseite für den Tag.
- Ein storniertes Spiel macht oft mehrere 90-Min.-Startzeiten frei (überlappende Slots).
- GitHub startet geplante Läufe teils mit einigen Minuten Verzögerung.
- Der Stand liegt in `state.json` und wird bei Änderungen committet – dadurch bleibt das
  Repo „aktiv“ und GitHub schaltet den Zeitplan nicht nach 60 Tagen ab.
- Genutzt wird die öffentliche Verfügbarkeits-API der Buchungsseite (kein Login).
  Ändert Peakz etwas daran, kann das Skript brechen.

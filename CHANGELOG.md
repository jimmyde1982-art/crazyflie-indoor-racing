# Änderungen

Hier steht, was sich zwischen den Versionen geändert hat.

## Unveröffentlicht

### Neu
- Automatische Tests auf GitHub (Linux und Windows) bei jedem Push und Pull Request
- `CONTRIBUTING.md` mit Anleitung zum Mitmachen
- Vorlagen für Issues (Fehler, Idee) und Pull Requests
- `requirements-dev.txt` für die Prüfwerkzeuge (pytest, ruff, mypy)
- README: Badges und Inhaltsverzeichnis

### Geändert
- `ruff check` ist in der GitHub-Prüfung jetzt verbindlich (vorher nur Hinweis)
- pytest, ruff und mypy sind in `requirements-dev.txt` auf feste Versionen
  festgelegt, damit ein Werkzeug-Update die Prüfung nicht ohne Codeänderung
  rot färbt

### Behoben
- `30_fliegen.py`: Importe sortiert, zwei Vergleiche umgedreht und die
  Schleifenvariable `l` in `logger` umbenannt (ruff-Meldungen)
- Typ-Angaben für `_zeilen`, `decke_puffer`, `verlauf` und `nullpunkt`
  ergänzt – mypy läuft damit ohne Meldung durch

## 2026-09 – Erste Version

- `race_indoor.py`, `30_fliegen.py`, `xbox_fly3.py`, `strecken.py`
- `flow_ranger_recorder.py`, `flow_ranger_heimflug.py`, `flug_auswerten.py`
- Tests für Bremsen, Funk, Heimweg, Strecken, Nachflug und Flugauswertung

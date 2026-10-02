# Mitmachen

Schön, dass du mithelfen willst! Das Projekt ist ein Hobby – jede Idee, jeder Fehlerbericht und jede Verbesserung hilft.

## Fehler melden oder Ideen vorschlagen

Öffne ein [Issue](../../issues/new/choose). Es gibt Vorlagen für **Fehler** und **Ideen**. Hilfreich sind:

- welches Skript und welcher Aufruf (z. B. `python 30_fliegen.py sport rec`)
- Firmware-Version der Crazyflie und welche Decks drauf sind
- die Flugaufzeichnung (`.txt`/`.csv`), wenn es eine gibt

## Code ändern

1. Oben rechts auf **Fork** klicken – damit hast du deine eigene Kopie.
2. Klonen und einrichten:

   ```bash
   git clone https://github.com/DEIN-NAME/crazyflie-indoor-racing.git
   cd crazyflie-indoor-racing
   pip install -r requirements.txt -r requirements-dev.txt
   ```

3. Eine Änderung nach der anderen machen. Lieber kleine Schritte als ein großer Umbau.
4. Prüfen:

   ```bash
   pytest        # Tests – müssen grün sein
   ruff check .  # Stil- und Fehlerprüfung
   mypy .        # Typprüfung
   ```

5. Wenn möglich: **echt fliegen** und kurz aufschreiben, wie es lief.
6. Einen **Pull Request** stellen und beschreiben, was du geändert hast und warum.

Bei jedem Pull Request laufen die Tests automatisch (grüner Haken = alles gut).

## Ein paar Regeln

- **Kein `black`** auf die Flugskripte loslassen – die von Hand ausgerichteten Konstanten-Blöcke unter `KONFIGURATION` sollen so bleiben.
- Grenzwerte (Abstände, Akku-Spannung usw.) bitte immer kommentieren, am besten mit dem Messwert, aus dem sie stammen.
- Schutzfunktionen (Wände, Decke, Akku, Not-Aus) nicht abschwächen, ohne das im Pull Request zu begründen.
- Kommentare und Texte gerne auf Deutsch.

## Sicherheit

Teste neue Änderungen mit Propellerschutz, niedriger Starthöhe und Abstand zu Menschen und Tieren.

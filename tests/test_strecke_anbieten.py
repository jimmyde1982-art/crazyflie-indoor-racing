"""Tests für die Frage nach dem Flug: "Strecke behalten?"

Es fliegt nichts. Geprüft wird nur, was strecke_anbieten() aus einer
fertigen Aufnahme und einer getippten Antwort macht. Alles läuft in
Wegwerf-Ordnern (tmp_path), die echten Flugdaten werden nie angefasst.
"""

import os

import pytest
from test_strecken import aufnahme_schreiben

import flow_ranger_heimflug as fh


@pytest.fixture
def ordner(tmp_path, monkeypatch):
    """Lenkt das Flugskript auf einen leeren Wegwerf-Ordner um."""
    monkeypatch.setattr(fh, 'HIER', str(tmp_path))
    return tmp_path


def tippen(monkeypatch, *antworten):
    """Ersetzt input() durch eine feste Folge von Antworten."""
    rest = list(antworten)
    monkeypatch.setattr('builtins.input', lambda *_: rest.pop(0))
    return rest


def hinflug_legen(ordner, stempel='2026-09-20_154141', takte=40, **kw):
    """Legt eine Aufnahme unter dem Namen ab, den das Flugskript sucht."""
    return aufnahme_schreiben(
        ordner / ('heim_hin_%s.csv' % stempel), takte=takte, **kw)


def test_modus_3_fragt_nicht(ordner, monkeypatch):
    """Menü 3 fliegt nur zurück und zeichnet keinen Hinweg auf -- da
    gibt es nichts zu benennen."""
    hinflug_legen(ordner)
    tippen(monkeypatch)                    # jedes input() wäre ein Fehler
    fh.strecke_anbieten('2026-09-20_154141', '3')
    assert not os.path.isdir(ordner / 'strecken')


def test_ohne_aufnahme_keine_frage(ordner, monkeypatch):
    """Kam es nie zum Flug, gibt es auch keine CSV. Dann still bleiben."""
    tippen(monkeypatch)
    fh.strecke_anbieten('2026-09-20_154141', '1')
    assert not os.path.isdir(ordner / 'strecken')


def test_fehlstart_wird_nicht_angeboten(ordner, monkeypatch):
    """Unter einer Sekunde war das kein Flug. Eine halbe Sekunde
    Aufnahme (10 Takte) soll keine Frage auslösen."""
    hinflug_legen(ordner, takte=10)
    tippen(monkeypatch)
    fh.strecke_anbieten('2026-09-20_154141', '1')
    assert not os.path.isdir(ordner / 'strecken')


def test_leerer_name_speichert_nicht(ordner, monkeypatch):
    """Enter ohne Namen heißt: nicht behalten."""
    quelle = hinflug_legen(ordner)
    tippen(monkeypatch, '')
    fh.strecke_anbieten('2026-09-20_154141', '1')
    assert not os.path.exists(ordner / 'strecken' / 'kueche.json')
    assert os.path.isfile(quelle)          # die Aufnahme bleibt liegen


def test_name_legt_die_strecke_ab(ordner, monkeypatch):
    """Der Normalfall: ein Name, und sie liegt in strecken/."""
    hinflug_legen(ordner)
    tippen(monkeypatch, 'Küche')
    fh.strecke_anbieten('2026-09-20_154141', '1')
    assert os.path.isfile(ordner / 'strecken' / 'kueche.csv')
    assert os.path.isfile(ordner / 'strecken' / 'kueche.json')


def test_die_aufnahme_bleibt_liegen(ordner, monkeypatch):
    """Gespeichert wird eine Kopie. Das Original rührt niemand an --
    Dateien werden in diesem Projekt nicht verschoben oder gelöscht."""
    quelle = hinflug_legen(ordner)
    vorher = open(quelle, encoding='utf-8').read()
    tippen(monkeypatch, 'kueche')
    fh.strecke_anbieten('2026-09-20_154141', '1')
    assert os.path.isfile(quelle)
    assert open(quelle, encoding='utf-8').read() == vorher


def test_nachflug_wird_auch_angeboten(ordner, monkeypatch):
    """Menü 2 schreibt heim_nach_*.csv. Auch der Weg ist eine Strecke."""
    aufnahme_schreiben(ordner / 'heim_nach_2026-09-20_154141.csv',
                       takte=40, phase='nach')
    tippen(monkeypatch, 'runde')
    fh.strecke_anbieten('2026-09-20_154141', '2')
    assert os.path.isfile(ordner / 'strecken' / 'runde.csv')


def test_unbrauchbarer_name_speichert_nicht(ordner, monkeypatch):
    """Aus lauter Sonderzeichen wird kein Dateiname. Dann lieber nichts
    speichern, als eine Datei mit kaputtem Namen anzulegen."""
    hinflug_legen(ordner)
    tippen(monkeypatch, '///')
    fh.strecke_anbieten('2026-09-20_154141', '1')
    ziel = ordner / 'strecken'
    assert not ziel.is_dir() or not list(ziel.glob('*.json'))


def test_belegter_name_fragt_nach(ordner, monkeypatch):
    """Ein vorhandener Name wird nie stillschweigend überschrieben."""
    hinflug_legen(ordner, takte=40, vx=0.40)
    tippen(monkeypatch, 'kueche')
    fh.strecke_anbieten('2026-09-20_154141', '1')
    alt = open(ordner / 'strecken' / 'kueche.csv', encoding='utf-8').read()

    # Zweiter Flug, gleicher Name, aber "nein" auf die Rückfrage
    hinflug_legen(ordner, stempel='2026-09-20_161500', takte=80, vx=0.20)
    tippen(monkeypatch, 'kueche', 'n')
    fh.strecke_anbieten('2026-09-20_161500', '1')
    neu = open(ordner / 'strecken' / 'kueche.csv', encoding='utf-8').read()
    assert neu == alt


def test_belegter_name_wird_auf_wunsch_ersetzt(ordner, monkeypatch):
    """Sagst du ausdrücklich ja, wird die alte Strecke ersetzt."""
    hinflug_legen(ordner, takte=40, vx=0.40)
    tippen(monkeypatch, 'kueche')
    fh.strecke_anbieten('2026-09-20_154141', '1')
    alt = open(ordner / 'strecken' / 'kueche.csv', encoding='utf-8').read()

    hinflug_legen(ordner, stempel='2026-09-20_161500', takte=80, vx=0.20)
    tippen(monkeypatch, 'kueche', 'j')
    fh.strecke_anbieten('2026-09-20_161500', '1')
    neu = open(ordner / 'strecken' / 'kueche.csv', encoding='utf-8').read()
    assert neu != alt
    assert len(neu.splitlines()) == 81      # Kopf plus 80 Takte


def test_strg_c_bei_der_frage_speichert_nicht(ordner, monkeypatch):
    """Strg+C an der Namensabfrage darf das Programm nicht beenden --
    der Flugbericht soll danach noch geschrieben werden."""
    hinflug_legen(ordner)

    def abbruch(*_):
        raise KeyboardInterrupt

    monkeypatch.setattr('builtins.input', abbruch)
    fh.strecke_anbieten('2026-09-20_154141', '1')   # darf nicht werfen
    assert not os.path.exists(ordner / 'strecken' / 'kueche.json')


def test_kaputte_aufnahme_wirft_nicht(ordner, monkeypatch):
    """Eine unlesbare CSV darf den Programmschluss nicht sprengen."""
    (ordner / 'heim_hin_2026-09-20_154141.csv').write_text(
        'das ist keine Aufnahme\n', encoding='utf-8')
    tippen(monkeypatch)
    fh.strecke_anbieten('2026-09-20_154141', '1')   # darf nicht werfen

"""Tests für die Strecken-Menüs 4 und 6 des Flugskripts.

Es fliegt nichts und es wird nichts gefunkt. Geprüft wird nur, was die
Menüfunktionen aus einem Ordner voller benannter Strecken und einer
getippten Antwort machen. Alles läuft in Wegwerf-Ordnern (tmp_path).
"""

import os

import pytest
from test_strecken import aufnahme_schreiben

import flow_ranger_heimflug as fh
import strecken


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


def strecke_legen(ordner, name, takte=40, vx=0.40):
    """Legt eine benannte Strecke an, so wie Menü 1 sie ablegen würde."""
    quelle = ordner / ('roh_%s.csv' % name)
    aufnahme_schreiben(quelle, takte=takte, vx=vx)
    return strecken.speichern(str(quelle), name, str(ordner))


# ------------------------------------------------------------- Nummern

@pytest.mark.parametrize('text, erwartet', [
    ('1', [0]),
    ('3', [2]),
    ('1,2,1', [0, 1, 0]),
    ('1 2 3', [0, 1, 2]),
    ('1, 2', [0, 1]),
    ('2,2,2,2', [1, 1, 1, 1]),
])
def test_nummern_werden_gelesen(text, erwartet):
    assert fh._nummern(text, 3) == erwartet


@pytest.mark.parametrize('text', ['0', '4', '-1', '', '  ', 'x', '1,9'])
def test_unbrauchbare_nummern_fliegen_raus(text):
    """Eine Nummer ausserhalb der Liste darf nicht durchrutschen --
    sonst stünde am Ende ein Weg, den niemand gewählt hat."""
    with pytest.raises(ValueError):
        fh._nummern(text, 3)


# --------------------------------------------------------------- Liste

def test_liste_ohne_strecken_bleibt_leer(ordner, capsys):
    assert fh.strecken_liste('Test:') == []
    assert 'Noch keine benannte Strecke' in capsys.readouterr().out


def test_liste_zeigt_jede_strecke(ordner, capsys):
    strecke_legen(ordner, 'kueche')
    strecke_legen(ordner, 'flur')
    liste = fh.strecken_liste('Test:')
    ausgabe = capsys.readouterr().out
    assert [s.name for s in liste] == ['flur', 'kueche']
    assert '[1] flur' in ausgabe and '[2] kueche' in ausgabe


def test_liste_ohne_modul_sagt_bescheid(ordner, monkeypatch, capsys):
    """Fehlt strecken.py neben dem Flugskript, soll das Menü nicht
    abstürzen, sondern es sagen."""
    monkeypatch.setattr(fh, 'strecken', None)
    assert fh.strecken_liste('Test:') == []
    assert 'strecken.py fehlt' in capsys.readouterr().out


def test_strecke_laden_gibt_bilder(ordner):
    s = strecke_legen(ordner, 'kueche', takte=40)
    bilder = fh.strecke_laden(s)
    assert len(bilder) == 40
    assert fh.letzte_lage(bilder) is not None


# --------------------------------------------------------------- Wählen

def test_waehlen_ohne_strecken_gibt_none(ordner, monkeypatch):
    tippen(monkeypatch)                    # jedes input() wäre ein Fehler
    assert fh.strecke_waehlen() is None


def test_waehlen_einer_strecke(ordner, monkeypatch, capsys):
    strecke_legen(ordner, 'kueche', takte=40)
    tippen(monkeypatch, '1', '', 'j')
    gewaehlt = fh.strecke_waehlen()
    assert gewaehlt is not None
    name, weg = gewaehlt
    assert name == 'kueche'
    assert len(weg) == 40
    assert 'ACHTUNG' not in capsys.readouterr().out


def test_enter_nimmt_die_erste(ordner, monkeypatch):
    """Zweimal Enter ist der kürzeste Weg: erste Strecke, einmal."""
    strecke_legen(ordner, 'kueche')
    strecke_legen(ordner, 'flur')
    tippen(monkeypatch, '', '', 'j')
    gewaehlt = fh.strecke_waehlen()
    assert gewaehlt is not None and gewaehlt[0] == 'flur'


def test_zwei_strecken_werden_gekettet(ordner, monkeypatch):
    """Der zweite Teil hängt hinten an, der Weg wird doppelt so lang."""
    strecke_legen(ordner, 'kueche', takte=40)
    strecke_legen(ordner, 'flur', takte=40)
    tippen(monkeypatch, '1,2', '', 'j')
    gewaehlt = fh.strecke_waehlen()
    assert gewaehlt is not None
    name, weg = gewaehlt
    assert name == 'flur + kueche'
    assert len(weg) == 80
    ende = fh.letzte_lage(weg)
    assert ende is not None
    assert 1.5 < ende[0] < 1.6          # zweimal 0.78 m geradeaus


def test_mehrfach_verlaengert_den_weg(ordner, monkeypatch):
    strecke_legen(ordner, 'kueche', takte=40)
    tippen(monkeypatch, '1', '3', 'j')
    gewaehlt = fh.strecke_waehlen()
    assert gewaehlt is not None
    assert gewaehlt[0] == 'kueche + kueche + kueche'
    assert len(gewaehlt[1]) == 120


def test_viele_teile_bekommen_einen_kurznamen(ordner, monkeypatch):
    """Ab fünf Teilen wird der Name sonst länger als die Zeile."""
    strecke_legen(ordner, 'kueche')
    tippen(monkeypatch, '1', '5', 'j')
    gewaehlt = fh.strecke_waehlen()
    assert gewaehlt is not None
    assert gewaehlt[0] == 'kueche ... kueche (5 Teile)'


def test_ungueltige_nummer_bricht_ab(ordner, monkeypatch, capsys):
    strecke_legen(ordner, 'kueche')
    tippen(monkeypatch, '7')
    assert fh.strecke_waehlen() is None
    assert 'Ungültige Wahl' in capsys.readouterr().out


@pytest.mark.parametrize('anzahl', ['0', '21', 'viele', '-2'])
def test_unbrauchbare_anzahl_bricht_ab(ordner, monkeypatch, capsys, anzahl):
    """20 Mal ist schon mehr, als der Akku hergibt. Alles darüber ist
    ein Vertipper und darf nicht zum Flug führen."""
    strecke_legen(ordner, 'kueche')
    tippen(monkeypatch, '1', anzahl)
    assert fh.strecke_waehlen() is None
    assert 'keine Anzahl' in capsys.readouterr().out


def test_nein_heisst_nicht_fliegen(ordner, monkeypatch, capsys):
    strecke_legen(ordner, 'kueche')
    tippen(monkeypatch, '1', '', 'n')
    assert fh.strecke_waehlen() is None
    assert 'Abgebrochen' in capsys.readouterr().out


def test_gekettet_warnt_vor_dem_raum(ordner, monkeypatch, capsys):
    """Einmal 8 m ist schon lang, aber genau so geflogen worden. Zweimal
    hintereinander reicht 16 m weit -- davor muss gewarnt werden."""
    strecke_legen(ordner, 'lang', takte=400)
    tippen(monkeypatch, '1', '2', 'j')
    assert fh.strecke_waehlen() is not None
    assert 'ACHTUNG' in capsys.readouterr().out


def test_eine_lange_strecke_warnt_nicht(ordner, monkeypatch, capsys):
    """Sie ist genau so geflogen worden, also passt sie in den Raum --
    auch wenn die Positionsschätzung mehr Meter behauptet."""
    strecke_legen(ordner, 'lang', takte=400)
    tippen(monkeypatch, '1', '', 'j')
    assert fh.strecke_waehlen() is not None
    assert 'ACHTUNG' not in capsys.readouterr().out


# ------------------------------------------------------------ Verwalten

def test_verwalten_ohne_strecken_kehrt_zurueck(ordner, monkeypatch):
    tippen(monkeypatch)
    assert fh.strecken_verwalten() == 0


def test_verwalten_ohne_modul_meldet_fehler(ordner, monkeypatch, capsys):
    monkeypatch.setattr(fh, 'strecken', None)
    tippen(monkeypatch)
    assert fh.strecken_verwalten() == 1
    assert 'strecken.py fehlt' in capsys.readouterr().out


def test_enter_geht_zurueck(ordner, monkeypatch):
    strecke_legen(ordner, 'kueche')
    tippen(monkeypatch, '')
    assert fh.strecken_verwalten() == 0


def test_umbenennen(ordner, monkeypatch, capsys):
    strecke_legen(ordner, 'kueche')
    tippen(monkeypatch, 'u', '1', 'Küche hinten', '')
    assert fh.strecken_verwalten() == 0
    assert 'kueche_hinten' in capsys.readouterr().out
    assert [s.name for s in strecken.alle(str(ordner))] == ['kueche_hinten']


def test_umbenennen_ohne_wahl_aendert_nichts(ordner, monkeypatch):
    strecke_legen(ordner, 'kueche')
    tippen(monkeypatch, 'u', '', '')
    assert fh.strecken_verwalten() == 0
    assert [s.name for s in strecken.alle(str(ordner))] == ['kueche']


def test_umbenennen_auf_vergebenen_namen_meldet_es(ordner, monkeypatch,
                                                   capsys):
    strecke_legen(ordner, 'kueche')
    strecke_legen(ordner, 'flur')
    tippen(monkeypatch, 'u', '2', 'flur', '')
    assert fh.strecken_verwalten() == 0
    assert 'Es gibt schon' in capsys.readouterr().out
    assert len(strecken.alle(str(ordner))) == 2


def test_aussortieren_loescht_nicht(ordner, monkeypatch):
    """Weggelegt, nicht weg: die Datei muss noch da sein."""
    strecke_legen(ordner, 'kueche')
    tippen(monkeypatch, 'a', '1', 'j', '')
    assert fh.strecken_verwalten() == 0
    assert strecken.alle(str(ordner)) == []
    beiseite = os.path.join(str(ordner), strecken.ORDNER, 'ausrangiert')
    assert os.listdir(beiseite)


def test_aussortieren_braucht_ein_ja(ordner, monkeypatch):
    strecke_legen(ordner, 'kueche')
    tippen(monkeypatch, 'a', '1', 'n', '')
    assert fh.strecken_verwalten() == 0
    assert [s.name for s in strecken.alle(str(ordner))] == ['kueche']

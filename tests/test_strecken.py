"""Tests für strecken.py -- Strecken benennen, lesen, verwalten.

Alles läuft auf Wegwerf-Ordnern (tmp_path), die echten Flugdaten werden
nie angefasst. Ein Test rechnet zusätzlich gegen die echte Aufnahme vom
20.09.2026, sofern sie da ist.
"""

import json
import os

import pytest

from strecken import (
    Kennzahlen,
    StreckenFehler,
    alle,
    aussortieren,
    kennzahlen_rechnen,
    lesen,
    name_pruefen,
    speichern,
    umbenennen,
    zeile,
)

SPALTEN = ('t_s;phase;vx_ms;vy_ms;gier_grad_s;z_soll_m;z_ist_m;'
           'z_gesendet_m;x_m;y_m;gier_ist_grad;vbat_v;vorne_m;hinten_m;'
           'links_m;rechts_m;oben_m;unten_m;gebremst;moebel_m;'
           'neben_weg_m;rest_m;shutter;squal;max_raw')


def aufnahme_schreiben(pfad, takte=40, vx=0.40, gier=0.0, z=0.50,
                       squal=120, shutter=800, phase='hin'):
    """Baut eine Aufnahme, die aussieht wie eine echte: geradeaus mit
    vx m/s, jede Zeile 50 ms."""
    zeilen = [SPALTEN]
    x = 0.0
    for i in range(takte):
        zeilen.append(
            '%.2f;%s;%.3f;0.000;%.1f;%.2f;%.2f;%.2f;%.4f;0.0000;0.0;3.90;'
            '2.00;2.00;2.00;2.00;1.50;%.2f;0;0.00;0.00;0.00;%d;%d;100'
            % (i * 0.05, phase, vx, gier, z, z, z, x, z, shutter, squal))
        x += vx * 0.05
    pfad.write_text('\n'.join(zeilen) + '\n', encoding='utf-8')
    return str(pfad)


# ---------------------------------------------------------------- Namen

@pytest.mark.parametrize('roh, erwartet', [
    ('Küche', 'kueche'),
    ('  Wohnzimmer  ', 'wohnzimmer'),
    ('Flur zur Tür', 'flur_zur_tuer'),
    ('Runde 2', 'runde_2'),
    ('groß/klein', 'gross_klein'),
    ('a-b_c', 'a-b_c'),
])
def test_name_wird_zu_einem_dateinamen(roh, erwartet):
    """Umlaute und Leerzeichen werden ersetzt, damit der Dateiname auf
    jedem System funktioniert."""
    assert name_pruefen(roh) == erwartet


@pytest.mark.parametrize('roh', ['', '   ', '///', '...', '???'])
def test_unbrauchbarer_name_wird_abgelehnt(roh):
    with pytest.raises(StreckenFehler):
        name_pruefen(roh)


def test_zu_langer_name_wird_abgelehnt():
    with pytest.raises(StreckenFehler):
        name_pruefen('x' * 41)


# ----------------------------------------------------------- Kennzahlen

def test_kennzahlen_einer_geraden_strecke(tmp_path):
    """40 Takte mit 0,40 m/s geradeaus: 2 s Dauer, 0,78 m Weg, kein
    Umweg, nichts gedreht, kein Schweben."""
    p = aufnahme_schreiben(tmp_path / 'a.csv', takte=40, vx=0.40)
    k = kennzahlen_rechnen(p)
    assert k.takte == 40
    assert k.dauer_s == pytest.approx(2.0)
    assert k.weg_m == pytest.approx(0.40 * 0.05 * 39, abs=1e-6)
    assert k.umweg == pytest.approx(1.0, abs=0.01)
    assert k.gedreht_grad == pytest.approx(0.0)
    assert k.schweben_anteil == pytest.approx(0.0)
    assert k.tempo_max == pytest.approx(0.40)


def test_schweben_wird_gezaehlt(tmp_path):
    """Steht sie nur da, ist der Schwebeanteil 100 Prozent -- und der
    Umweg 0, weil es keine Luftlinie gibt."""
    p = aufnahme_schreiben(tmp_path / 'b.csv', takte=30, vx=0.0)
    k = kennzahlen_rechnen(p)
    assert k.schweben_anteil == pytest.approx(1.0)
    assert k.weg_m == pytest.approx(0.0)
    assert k.umweg == 0.0


def test_drehung_wird_aufsummiert(tmp_path):
    """20 Grad/s über 40 Takte (2 s) sind 40 Grad."""
    p = aufnahme_schreiben(tmp_path / 'c.csv', takte=40, gier=20.0)
    assert kennzahlen_rechnen(p).gedreht_grad == pytest.approx(40.0)


def test_andere_phasen_zaehlen_nicht(tmp_path):
    """Nur die Zeilen der Phase 'hin' gehören zum Hinflug."""
    p = aufnahme_schreiben(tmp_path / 'd.csv', takte=25, phase='rueck')
    with pytest.raises(StreckenFehler):
        kennzahlen_rechnen(p, phase='hin')
    assert kennzahlen_rechnen(p, phase='rueck').takte == 25


def test_abheben_gilt_nicht_als_zu_tief(tmp_path):
    """Jeder Flug beginnt am Boden. Die ersten und letzten 2 Sekunden
    dürfen die Höhenwarnung nicht auslösen -- sonst meldet sich auch der
    saubere Flug vom 20.09. 15:15, der durchgehend auf 0,30 m war."""
    zeilen = [SPALTEN]
    for i in range(400):
        if i < 30:
            z = 0.05 + i * 0.01          # Abheben
        elif i > 369:
            z = 0.35 - (i - 369) * 0.01  # Landen
        else:
            z = 0.50                     # im Flug, unauffällig
        zeilen.append(
            '%.2f;hin;0.300;0.000;0.0;%.2f;%.2f;%.2f;%.4f;0.0000;0.0;3.90;'
            '2.00;2.00;2.00;2.00;1.50;%.2f;0;0.00;0.00;0.00;800;120;100'
            % (i * 0.05, z, z, z, i * 0.015, z))
    p = tmp_path / 'e.csv'
    p.write_text('\n'.join(zeilen) + '\n', encoding='utf-8')
    k = kennzahlen_rechnen(str(p))
    assert k.hoehe_min == pytest.approx(0.50, abs=0.01)
    assert not any('herunter' in w for w in k.warnungen())


def test_zu_tief_im_flug_wird_trotzdem_gemeldet(tmp_path):
    """Sackt sie mittendrin ab, muss die Warnung kommen."""
    zeilen = [SPALTEN]
    for i in range(400):
        z = 0.12 if 150 <= i < 200 else 0.50
        zeilen.append(
            '%.2f;hin;0.300;0.000;0.0;%.2f;%.2f;%.2f;%.4f;0.0000;0.0;3.90;'
            '2.00;2.00;2.00;2.00;1.50;%.2f;0;0.00;0.00;0.00;800;120;100'
            % (i * 0.05, z, z, z, i * 0.015, z))
    p = tmp_path / 'f.csv'
    p.write_text('\n'.join(zeilen) + '\n', encoding='utf-8')
    k = kennzahlen_rechnen(str(p))
    assert k.hoehe_min == pytest.approx(0.12, abs=0.01)
    assert any('herunter' in w for w in k.warnungen())


def test_warnungen_bei_viel_drehung_und_blindem_sensor():
    """Die Grenzen stammen aus den Flügen vom 20.09.2026."""
    k = Kennzahlen(takte=100, dauer_s=5.0, weg_m=20.0, luftlinie_m=5.0,
                   umweg=4.0, gedreht_grad=1508.0, schweben_anteil=0.49,
                   tempo_max=0.51, hoehe_min=0.15, hoehe_max=1.13,
                   hoehe_mittel=0.57, squal_min=26, shutter_min=41)
    text = ' '.join(k.warnungen())
    assert 'gedreht' in text
    assert 'Umweg' in text
    assert 'Schweben' in text
    assert 'blind' in text
    assert 'Anschlag' in text


def test_sauberer_flug_bekommt_keine_warnung():
    k = Kennzahlen(takte=100, dauer_s=5.0, weg_m=5.2, luftlinie_m=5.0,
                   umweg=1.04, gedreht_grad=0.0, schweben_anteil=0.05,
                   tempo_max=0.45, hoehe_min=0.45, hoehe_max=0.60,
                   hoehe_mittel=0.52, squal_min=92, shutter_min=155)
    assert k.warnungen() == []


# -------------------------------------------------- Speichern und Lesen

def test_speichern_legt_beide_dateien_an(tmp_path):
    q = aufnahme_schreiben(tmp_path / 'heim_hin_2026-09-20_154141.csv')
    s = speichern(q, 'Küche', str(tmp_path))
    assert s.name == 'kueche'
    assert s.geflogen == '2026-09-20_154141'
    assert s.herkunft == 'heim_hin_2026-09-20_154141.csv'
    ordner = tmp_path / 'strecken'
    assert (ordner / 'kueche.csv').is_file()
    assert (ordner / 'kueche.json').is_file()


def test_original_bleibt_liegen(tmp_path):
    """Die Aufnahme wird kopiert, nicht verschoben."""
    q = aufnahme_schreiben(tmp_path / 'heim_hin_2026-09-20_154141.csv')
    speichern(q, 'kueche', str(tmp_path))
    assert os.path.isfile(q)


def test_gespeicherte_strecke_kommt_unveraendert_zurueck(tmp_path):
    q = aufnahme_schreiben(tmp_path / 'heim_hin_2026-09-20_154141.csv')
    hin = speichern(q, 'kueche', str(tmp_path), bemerkung='durch die Tür')
    zurueck = lesen('kueche', str(tmp_path))
    assert zurueck.name == hin.name
    assert zurueck.bemerkung == 'durch die Tür'
    assert zurueck.kennzahlen == hin.kennzahlen
    assert os.path.isfile(zurueck.csv_datei)


def test_gleicher_name_wird_nicht_versehentlich_ueberschrieben(tmp_path):
    q = aufnahme_schreiben(tmp_path / 'heim_hin_2026-09-20_154141.csv')
    speichern(q, 'kueche', str(tmp_path))
    with pytest.raises(StreckenFehler):
        speichern(q, 'kueche', str(tmp_path))
    speichern(q, 'kueche', str(tmp_path), ueberschreiben=True)


def test_unbekannte_strecke_meldet_sich_deutlich(tmp_path):
    with pytest.raises(StreckenFehler, match='gibt es nicht'):
        lesen('gibtsnicht', str(tmp_path))


def test_fehlende_aufnahme_wird_gemeldet(tmp_path):
    """Die json allein nützt nichts -- ohne csv kann sie nicht fliegen."""
    q = aufnahme_schreiben(tmp_path / 'heim_hin_2026-09-20_154141.csv')
    speichern(q, 'kueche', str(tmp_path))
    os.remove(tmp_path / 'strecken' / 'kueche.csv')
    with pytest.raises(StreckenFehler, match='fehlt die Aufnahme'):
        lesen('kueche', str(tmp_path))


def test_aufnahme_die_es_nicht_gibt(tmp_path):
    with pytest.raises(StreckenFehler):
        speichern(str(tmp_path / 'weg.csv'), 'kueche', str(tmp_path))


# ---------------------------------------------------------- Die Verwaltung

def test_alle_listet_neueste_zuerst(tmp_path):
    q = aufnahme_schreiben(tmp_path / 'heim_hin_2026-09-20_154141.csv')
    for name, stempel in (('alt', '2026-09-01_100000'),
                          ('mittel', '2026-09-10_100000'),
                          ('neu', '2026-09-20_100000')):
        s = speichern(q, name, str(tmp_path))
        pfad = tmp_path / 'strecken' / (s.name + '.json')
        kopf = json.loads(pfad.read_text(encoding='utf-8'))
        kopf['gespeichert'] = stempel
        pfad.write_text(json.dumps(kopf), encoding='utf-8')
    assert [s.name for s in alle(str(tmp_path))] == ['neu', 'mittel', 'alt']


def test_kaputte_datei_wirft_die_liste_nicht_um(tmp_path):
    """Eine unlesbare json wird übersprungen, der Rest bleibt sichtbar."""
    q = aufnahme_schreiben(tmp_path / 'heim_hin_2026-09-20_154141.csv')
    speichern(q, 'gut', str(tmp_path))
    (tmp_path / 'strecken' / 'kaputt.json').write_text('{kein json',
                                                       encoding='utf-8')
    assert [s.name for s in alle(str(tmp_path))] == ['gut']


def test_leerer_ordner_gibt_leere_liste(tmp_path):
    assert alle(str(tmp_path)) == []


def test_umbenennen_nimmt_beide_dateien_mit(tmp_path):
    q = aufnahme_schreiben(tmp_path / 'heim_hin_2026-09-20_154141.csv')
    speichern(q, 'kueche', str(tmp_path))
    s = umbenennen('kueche', 'Küche hinten', str(tmp_path))
    assert s.name == 'kueche_hinten'
    ordner = tmp_path / 'strecken'
    assert (ordner / 'kueche_hinten.csv').is_file()
    assert (ordner / 'kueche_hinten.json').is_file()
    assert not (ordner / 'kueche.csv').exists()
    assert lesen('kueche_hinten', str(tmp_path)).name == 'kueche_hinten'


def test_umbenennen_auf_belegten_namen_wird_abgelehnt(tmp_path):
    q = aufnahme_schreiben(tmp_path / 'heim_hin_2026-09-20_154141.csv')
    speichern(q, 'eins', str(tmp_path))
    speichern(q, 'zwei', str(tmp_path))
    with pytest.raises(StreckenFehler, match='gibt schon'):
        umbenennen('eins', 'zwei', str(tmp_path))
    assert lesen('eins', str(tmp_path)).name == 'eins'


def test_aussortieren_loescht_nichts(tmp_path):
    """Was einmal geflogen ist, bleibt erhalten -- es wandert nur in den
    Unterordner ausrangiert/."""
    q = aufnahme_schreiben(tmp_path / 'heim_hin_2026-09-20_154141.csv')
    speichern(q, 'kueche', str(tmp_path))
    lager = aussortieren('kueche', str(tmp_path))
    with pytest.raises(StreckenFehler):
        lesen('kueche', str(tmp_path))
    übrig = os.listdir(lager)
    assert sum(1 for f in übrig if f.endswith('.csv')) == 1
    assert sum(1 for f in übrig if f.endswith('.json')) == 1


def test_zeile_nennt_den_namen(tmp_path):
    q = aufnahme_schreiben(tmp_path / 'heim_hin_2026-09-20_154141.csv')
    s = speichern(q, 'kueche', str(tmp_path))
    assert 'kueche' in zeile(s)


# ------------------------------------------- Gegen die echten Flugdaten

# Optional: echte Aufnahme in tests/daten/ legen, dann laeuft dieser Test mit.
ECHT = os.path.join(os.path.dirname(__file__), 'daten',
                    'heim_hin_2026-09-20_154141.csv')


@pytest.mark.skipif(not os.path.isfile(ECHT), reason='Flugdaten nicht da')
def test_echte_aufnahme_von_flug_6():
    """Die Aufnahme vom 20.09. 15:41 -- die Zahlen sind aus der
    Auswertung des Fluges bekannt und müssen wieder herauskommen."""
    k = kennzahlen_rechnen(ECHT)
    assert k.takte == 1752
    assert k.weg_m == pytest.approx(21.98, abs=0.05)
    assert k.luftlinie_m == pytest.approx(5.06, abs=0.05)
    assert k.umweg == pytest.approx(4.3, abs=0.1)
    assert k.gedreht_grad == pytest.approx(1508, abs=5)
    assert k.tempo_max == pytest.approx(0.51, abs=0.01)
    assert k.warnungen()        # dieser Flug muss Warnungen auslösen

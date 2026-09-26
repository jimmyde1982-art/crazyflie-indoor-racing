"""Tests für die Flugauswertung.

Es fliegt nichts und es wird nichts gefunkt. Geprüft wird nur, was das
Skript aus einer CSV-Datei herausliest und welches Urteil dabei
herauskommt. Alles läuft in Wegwerf-Ordnern (tmp_path).
"""

import pytest

import flug_auswerten as fa

SPALTEN = ['t_s', 'phase', 'vx_ms', 'vy_ms', 'gier_grad_s', 'z_soll_m',
           'z_ist_m', 'z_gesendet_m', 'x_m', 'y_m', 'gier_ist_grad',
           'vbat_v', 'vorne_m', 'hinten_m', 'links_m', 'rechts_m',
           'oben_m', 'unten_m', 'gebremst', 'moebel_m', 'neben_weg_m',
           'rest_m', 'shutter', 'squal', 'max_raw']


def flug_schreiben(pfad, takte=100, vx=0.40, gier=0.0, z=0.40,
                   squal=120, shutter=2500):
    """Legt eine Aufnahme an, wie das Flugskript sie schreiben würde."""
    zeilen = [';'.join(SPALTEN)]
    for i in range(takte):
        werte = {
            't_s': '%.2f' % (i * fa.TAKT),
            'phase': 'hin',
            'vx_ms': '%.3f' % vx,
            'vy_ms': '0.000',
            'gier_grad_s': '%.1f' % gier,
            'z_soll_m': '%.3f' % z,
            'z_ist_m': '%.3f' % z,
            'z_gesendet_m': '%.3f' % z,
            'x_m': '%.3f' % (i * vx * fa.TAKT),
            'y_m': '0.000',
            'gier_ist_grad': '%.1f' % (i * gier * fa.TAKT),
            'vbat_v': '%.2f' % (4.00 - i * 0.001),
            'gebremst': '0',
            'moebel_m': '0.000',
            'neben_weg_m': '0.000',
            'rest_m': '0.000',
            'shutter': str(shutter),
            'squal': str(squal),
            'max_raw': '200',
        }
        zeilen.append(';'.join(werte.get(s, '') for s in SPALTEN))
    pfad.write_text('\n'.join(zeilen) + '\n', encoding='utf-8')
    return pfad


def lande_schreiben(pfad, x=0.05, y=0.05, gier=3.0):
    pfad.write_text('x_m;y_m;gier_grad\n%.3f;%.3f;%.2f\n' % (x, y, gier),
                    encoding='utf-8')
    return pfad


@pytest.fixture
def ordner(tmp_path):
    return tmp_path


# ------------------------------------------------------------ Kennzahlen

def test_leere_aufnahme_stuerzt_nicht_ab():
    """Eine Datei mit Kopfzeile und sonst nichts darf keinen Fehler
    werfen -- das passiert bei jedem Fehlstart."""
    k = fa.kennzahlen([])
    assert k.takte == 0
    assert k.dauer_s == 0.0
    assert k.dreh_grad == 0.0


def test_gerader_flug_hat_keine_drehung(ordner):
    flug_schreiben(ordner / 'a.csv', takte=100, vx=0.40, gier=0.0)
    k = fa.kennzahlen(fa._zeilen(str(ordner / 'a.csv')))
    assert k.takte == 100
    assert k.dreh_grad == pytest.approx(0.0, abs=0.1)
    # 100 Takte * 0.05 s * 0.40 m/s = 2.0 m
    assert k.strecke_m == pytest.approx(2.0, abs=0.05)


def test_drehung_wird_aufsummiert(ordner):
    """90 Grad pro Sekunde über 4 Sekunden sind 360 Grad."""
    flug_schreiben(ordner / 'a.csv', takte=80, vx=0.0, gier=90.0)
    k = fa.kennzahlen(fa._zeilen(str(ordner / 'a.csv')))
    assert k.dreh_grad == pytest.approx(360.0, abs=10.0)


def test_drehung_zaehlt_als_betrag(ordner):
    """Hin und zurück gedreht ist trotzdem zweimal gedreht -- der Drift
    hebt sich nicht auf, er addiert sich."""
    flug_schreiben(ordner / 'a.csv', takte=40, gier=-90.0)
    k = fa.kennzahlen(fa._zeilen(str(ordner / 'a.csv')))
    assert k.dreh_grad > 0.0


def test_leere_felder_werden_uebersprungen():
    """Multiranger-Spalten sind leer, sobald nichts in Reichweite ist."""
    assert fa._zahl('') is None
    assert fa._zahl(None) is None
    assert fa._zahl('kaputt') is None
    assert fa._zahl('1.5') == 1.5


def test_dunkle_takte_werden_gezaehlt(ordner):
    flug_schreiben(ordner / 'a.csv', takte=50,
                   shutter=fa.SHUTTER_ANSCHLAG)
    k = fa.kennzahlen(fa._zeilen(str(ordner / 'a.csv')))
    assert k.dunkle_takte == 50


def test_blinde_takte_werden_gezaehlt(ordner):
    flug_schreiben(ordner / 'a.csv', takte=30, squal=0)
    k = fa.kennzahlen(fa._zeilen(str(ordner / 'a.csv')))
    assert k.blinde_takte == 30
    assert k.schwache_takte == 30


# -------------------------------------------------------------- Schätzung

def test_ohne_drehung_bleibt_der_sockel():
    gemessen, forum = fa.drift_schaetzen(0.0)
    assert gemessen == pytest.approx(fa.GRUND_CM)
    assert forum == pytest.approx(fa.GRUND_CM)


def test_mehr_drehung_heisst_mehr_drift():
    """Das ist der ganze Punkt der Schätzung."""
    wenig, _ = fa.drift_schaetzen(90.0)
    viel, _ = fa.drift_schaetzen(1080.0)
    assert viel > wenig > fa.GRUND_CM


def test_forum_regel_ist_pessimistischer():
    """Die Faustregel aus dem Forum soll die Obergrenze sein, sonst
    wäre sie als Warnung wertlos."""
    gemessen, forum = fa.drift_schaetzen(720.0)
    assert forum > gemessen


def test_die_bekannte_messung_wird_getroffen():
    """723 Grad wurden mit 30 cm nachgemessen. Daran ist die Gerade
    angelegt, das muss sie reproduzieren."""
    gemessen, _ = fa.drift_schaetzen(723.0)
    assert gemessen == pytest.approx(30.0, abs=1.0)


# ------------------------------------------------------------ Flug lesen

def test_flug_ohne_dateien_bleibt_leer(ordner):
    flug = fa.flug_lesen(str(ordner), '2026-01-01_120000')
    assert flug.hin is None
    assert flug.rueck is None
    assert flug.rest_cm is None
    assert not flug.geflogen


def test_flug_mit_allen_dateien(ordner):
    stempel = '2026-01-01_120000'
    flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel), takte=200)
    flug_schreiben(ordner / ('heim_rueck_%s.csv' % stempel), takte=180)
    lande_schreiben(ordner / ('heim_lande_%s.csv' % stempel),
                    x=0.03, y=0.04)
    flug = fa.flug_lesen(str(ordner), stempel)
    assert flug.hin is not None and flug.hin.takte == 200
    assert flug.rueck is not None and flug.rueck.takte == 180
    assert flug.rest_cm == pytest.approx(5.0, abs=0.1)   # 3-4-5-Dreieck
    assert flug.geflogen


def test_fehlstart_gilt_nicht_als_flug(ordner):
    """Ein Fehlstart hinterlässt eine Datei mit ein paar Zeilen. Der
    darf nicht in der Bestenliste auftauchen."""
    stempel = '2026-01-01_120000'
    flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel), takte=20,
                   squal=0)
    flug = fa.flug_lesen(str(ordner), stempel)
    assert not flug.geflogen


def test_fluege_werden_gefunden(ordner):
    for stempel in ('2026-01-01_120000', '2026-01-01_130000'):
        flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel))
    gefunden = fa.fluege_finden(str(ordner))
    assert gefunden == ['2026-01-01_120000', '2026-01-01_130000']


def test_leerer_ordner_gibt_leere_liste(ordner):
    assert fa.fluege_finden(str(ordner)) == []


# --------------------------------------------------------------- Urteil

def test_sauberer_flug_ist_gut(ordner):
    stempel = '2026-01-01_120000'
    flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel),
                   takte=400, gier=0.0, z=0.40, squal=120, shutter=2500)
    lande_schreiben(ordner / ('heim_lande_%s.csv' % stempel), gier=3.0)
    u = fa.bewerten(fa.flug_lesen(str(ordner), stempel))
    assert u.note == 'gut'


def test_viel_drehen_wird_bemaengelt(ordner):
    stempel = '2026-01-01_120000'
    # 60 Grad/s über 30 s sind 1800 Grad
    flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel),
                   takte=600, gier=60.0)
    u = fa.bewerten(fa.flug_lesen(str(ordner), stempel))
    assert u.note == 'schlecht'
    assert any('gedreht' in g for g in u.gruende)
    assert any('drehen' in r for r in u.rat)


def test_hoch_fliegen_wird_bemaengelt(ordner):
    stempel = '2026-01-01_120000'
    flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel),
                   takte=400, z=1.30)
    u = fa.bewerten(fa.flug_lesen(str(ordner), stempel))
    assert u.note == 'brauchbar'
    assert any('hoch' in g for g in u.gruende)


def test_dunkelheit_wird_bemaengelt(ordner):
    stempel = '2026-01-01_120000'
    flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel),
                   takte=400, shutter=fa.SHUTTER_ANSCHLAG)
    u = fa.bewerten(fa.flug_lesen(str(ordner), stempel))
    assert any('dunkel' in g for g in u.gruende)


def test_drehfreudiger_rueckflug_faellt_auf(ordner):
    """Der Rückflug soll denselben Weg zurück. Dreht er viel mehr als
    der Hinflug, sucht er unterwegs -- und verliert dabei Genauigkeit."""
    stempel = '2026-01-01_120000'
    flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel),
                   takte=400, gier=0.0)
    flug_schreiben(ordner / ('heim_rueck_%s.csv' % stempel),
                   takte=400, gier=60.0)          # 1200 Grad
    lande_schreiben(ordner / ('heim_lande_%s.csv' % stempel))
    u = fa.bewerten(fa.flug_lesen(str(ordner), stempel))
    assert any('Rückflug' in g and 'gedreht' in g for g in u.gruende)


def test_gleicher_rueckflug_faellt_nicht_auf(ordner):
    """Dreht der Rückflug so viel wie der Hinflug plus Wende, ist das
    in Ordnung und darf nicht gemeldet werden."""
    stempel = '2026-01-01_120000'
    flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel),
                   takte=400, gier=30.0)          # 600 Grad
    flug_schreiben(ordner / ('heim_rueck_%s.csv' % stempel),
                   takte=400, gier=33.0)          # 660 Grad
    lande_schreiben(ordner / ('heim_lande_%s.csv' % stempel))
    u = fa.bewerten(fa.flug_lesen(str(ordner), stempel))
    assert not any('Rückflug' in g for g in u.gruende)


def test_umweg_im_rueckflug_faellt_auf(ordner):
    stempel = '2026-01-01_120000'
    flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel),
                   takte=400, vx=0.40)            # 8 m
    flug_schreiben(ordner / ('heim_rueck_%s.csv' % stempel),
                   takte=400, vx=0.60)            # 12 m, also 50 % mehr
    lande_schreiben(ordner / ('heim_lande_%s.csv' % stempel))
    u = fa.bewerten(fa.flug_lesen(str(ordner), stempel))
    assert any('mehr Weg' in g for g in u.gruende)


def test_verdrehte_landung_ist_schlecht(ordner):
    """178 Grad verdreht heißt: die Schätzung ist weggelaufen. So ein
    Flug darf nicht als Strecke aufgehoben werden."""
    stempel = '2026-01-01_120000'
    flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel), takte=400)
    lande_schreiben(ordner / ('heim_lande_%s.csv' % stempel),
                    x=2.0, y=2.0, gier=178.0)
    u = fa.bewerten(fa.flug_lesen(str(ordner), stempel))
    assert u.note == 'schlecht'
    assert any('verdreht' in g for g in u.gruende)
    assert any('nicht als Strecke' in r for r in u.rat)


def test_blinder_fehlstart_wird_erklaert(ordner):
    stempel = '2026-01-01_120000'
    flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel), takte=20,
                   squal=0)
    u = fa.bewerten(fa.flug_lesen(str(ordner), stempel))
    assert u.note == 'schlecht'
    assert any('Bodenkamera' in g for g in u.gruende)
    assert any('Licht' in r for r in u.rat)


# -------------------------------------------------------------- Bericht

def test_bericht_nennt_die_schaetzung(ordner):
    stempel = '2026-01-01_120000'
    flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel),
                   takte=400, gier=30.0)
    lande_schreiben(ordner / ('heim_lande_%s.csv' % stempel),
                    x=0.05, y=0.05)
    text = '\n'.join(fa.bericht(fa.flug_lesen(str(ordner), stempel)))
    assert 'behauptet' in text
    assert 'Geschätzt' in text


def test_bericht_meldet_zusammenbruch(ordner):
    """Meldet die Drohne selbst mehr als die Faustregel hergibt, darf
    das Skript keine beruhigende Schätzung danebenstellen."""
    stempel = '2026-01-01_120000'
    flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel),
                   takte=400, gier=0.0)
    lande_schreiben(ordner / ('heim_lande_%s.csv' % stempel),
                    x=2.0, y=2.0, gier=178.0)
    text = '\n'.join(fa.bericht(fa.flug_lesen(str(ordner), stempel)))
    assert 'zusammengebrochen' in text
    assert 'Geschätzt sind es eher' not in text


def test_kurz_zeile_passt_in_eine_zeile(ordner):
    stempel = '2026-01-01_120000'
    flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel), takte=400)
    lande_schreiben(ordner / ('heim_lande_%s.csv' % stempel))
    zeile = fa.kurz_zeile(fa.flug_lesen(str(ordner), stempel))
    assert '\n' not in zeile
    assert stempel in zeile


def test_bestenliste_braucht_zwei_fluege(ordner):
    stempel = '2026-01-01_120000'
    flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel), takte=400)
    lande_schreiben(ordner / ('heim_lande_%s.csv' % stempel))
    assert fa.bestenliste([fa.flug_lesen(str(ordner), stempel)]) == []


def test_bestenliste_sortiert_nach_drehung(ordner):
    fluege = []
    for nr, gier in ((1, 0.0), (2, 60.0)):
        stempel = '2026-01-01_12000%d' % nr
        flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel),
                       takte=400, gier=gier)
        lande_schreiben(ordner / ('heim_lande_%s.csv' % stempel))
        fluege.append(fa.flug_lesen(str(ordner), stempel))
    text = '\n'.join(fa.bestenliste(fluege))
    assert '2026-01-01_120001' in text        # der ohne Drehung gewinnt
    assert 'Am wenigsten gedreht' in text


# ----------------------------------------------------------------- Main

def test_main_ohne_fluege_meldet_es(ordner, capsys):
    assert fa.main([str(ordner)]) == 1
    assert 'kein Heimflug' in capsys.readouterr().out


def test_main_mit_falschem_ordner_meldet_es(capsys):
    assert fa.main(['C:/gibt/es/nicht']) == 1
    assert 'gibt es nicht' in capsys.readouterr().out


def test_main_laeuft_durch(ordner, capsys):
    stempel = '2026-01-01_120000'
    flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel), takte=400)
    lande_schreiben(ordner / ('heim_lande_%s.csv' % stempel))
    assert fa.main([str(ordner)]) == 0
    assert 'Urteil' in capsys.readouterr().out


def test_kurz_ist_kein_ordnername(ordner, capsys):
    """"python flug_auswerten.py kurz" darf nicht nach einem Ordner
    namens kurz suchen."""
    stempel = '2026-01-01_120000'
    flug_schreiben(ordner / ('heim_hin_%s.csv' % stempel), takte=400)
    lande_schreiben(ordner / ('heim_lande_%s.csv' % stempel))
    assert fa.main([str(ordner), 'kurz']) == 0
    ausgabe = capsys.readouterr().out
    assert 'Urteil' not in ausgabe        # Kurzfassung, kein Bericht
    assert stempel in ausgabe

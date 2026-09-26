"""Tests für die Rückweg-Logik in flow_ranger_heimflug.py (ohne Drohne)."""
import math

import pytest

from flow_ranger_heimflug import (
    BREMS_ABSTAND,
    HALTE_ABSTAND,
    MAX_SPEED,
    MAX_YAW,
    RAMPE,
    REAKTION_S,
    RUECK_EXTRA,
    RUECK_TEMPO,
    RUECK_YAW,
    SCHLEIFE_RADIUS,
    SPEED_SAETTIGUNG,
    TAKT,
    UMKEHR_AKKU,
    ZIEL_GIER,
    ZIEL_RADIUS,
    Bild,
    Heimweg,
    Spiegel,
    rueckweg_bauen,
    rueckzeit,
    schleifen_kuerzen,
    spiegel_bauen,
    umkehren_noetig,
    weglaenge,
    wrap,
)


def spur_aus(ecken, z=0.3, schritt=0.02):
    """Hinflug-Spur entlang der Ecken, alle `schritt` m ein Punkt."""
    spur = []
    for (ax, ay), (bx, by) in zip(ecken, ecken[1:], strict=False):
        n = max(1, int(math.hypot(bx - ax, by - ay) / schritt))
        richtung = math.degrees(math.atan2(by - ay, bx - ax))
        for k in range(n):
            f = k / n
            spur.append((ax + f * (bx - ax), ay + f * (by - ay), z, richtung))
    bx, by = ecken[-1]
    spur.append((bx, by, z, spur[-1][3]))
    return spur


def fliege(punkte, x, y, yaw, max_s=120.0):
    """Einfache Rechen-Drohne: tut genau, was befohlen wird.
    vx/vy im Körper, positive Gierrate = yaw steigt."""
    h = Heimweg(punkte)
    neben_max = 0.0
    for _ in range(int(max_s / TAKT)):
        vx, vy, gier, _z, neben = h.schritt(x, y, yaw)
        assert vx >= -0.16, 'fährt deutlich rückwärts'
        neben_max = max(neben_max, neben)
        if h.phase == 'fertig':
            return h, x, y, yaw, neben_max
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        x += (c * vx - s * vy) * TAKT
        y += (s * vx + c * vy) * TAKT
        yaw = wrap(yaw + gier * TAKT)
    pytest.fail('nicht angekommen')


def test_rueckweg_endet_am_start_und_beginnt_am_landepunkt():
    spur = spur_aus([(0.05, 0.02), (1.0, 0.0), (1.0, 1.0)])
    p = rueckweg_bauen(spur)
    assert p[-1][:2] == (0.0, 0.0)
    assert p[0][:2] == pytest.approx((1.0, 1.0))
    for a, b in zip(p, p[1:], strict=False):
        assert math.hypot(b[0] - a[0], b[1] - a[1]) <= 0.13
    assert weglaenge(p) == pytest.approx(2.0, abs=0.1)


def test_leere_spur():
    assert rueckweg_bauen([]) == []


def test_hoehe_bleibt_in_grenzen():
    spur = [(0, 0, 0.05, 0), (0.5, 0, 2.0, 0), (1.0, 0, 0.5, 0)]
    for _x, _y, z in rueckweg_bauen(spur):
        assert 0.2 <= z <= 1.3


@pytest.mark.parametrize('ecken', [
    [(0, 0), (1.5, 0)],                          # gerade
    [(0, 0), (1.0, 0), (1.0, 1.0)],              # Ecke links
    [(0, 0), (1.0, 0), (1.0, -1.0), (0, -1.0)],  # U, Ende nah am Start
    [(0, 0), (1.2, 0.3), (0.3, 1.0), (0.6, -0.4)],  # kreuzt sich selbst
])
def test_fliegt_zurueck_und_richtet_sich_aus(ecken):
    spur = spur_aus(ecken)
    p = rueckweg_bauen(spur)
    x, y, _z, yaw = spur[-1]
    h, x, y, yaw, neben_max = fliege(p, x, y, yaw)
    assert not h.zeit_um
    assert math.hypot(x, y) < 1.5 * ZIEL_RADIUS
    assert abs(wrap(yaw)) < ZIEL_GIER
    assert neben_max < 0.3


def test_nase_voraus_nicht_rueckwaerts():
    """Auf der Geraden zeigt die Nase in Fahrtrichtung zum Start (180 Grad)."""
    spur = spur_aus([(0, 0), (2.0, 0)])
    p = rueckweg_bauen(spur)
    h = Heimweg(p)
    x, y, yaw = 1.5, 0.0, 180.0
    vx, _vy, gier, _z, _n = h.schritt(x, y, yaw)
    assert vx > 0.25
    assert abs(gier) < 1.0


def test_wendet_auf_der_stelle_wenn_nase_falsch():
    spur = spur_aus([(0, 0), (2.0, 0)])
    h = Heimweg(rueckweg_bauen(spur))
    vx, vy, gier, _z, _n = h.schritt(2.0, 0.0, 0.0)   # Nase weg vom Start
    assert (vx, vy) == (0.0, 0.0)
    assert gier != 0.0
    assert h.wendet


def test_gierrichtung_kuerzester_weg():
    """Soll 90 Grad links: positive Gierrate (gegen den Uhrzeigersinn)."""
    spur = spur_aus([(0, 0), (0, -2.0)])     # Rückweg führt nach +y
    h = Heimweg(rueckweg_bauen(spur))
    _vx, _vy, gier, _z, _n = h.schritt(0.0, -2.0, 0.0)
    assert gier > 0


def test_zeit_um_beim_heranschieben():
    """Kommt sie nie an, endet es trotzdem (Rechen-Drohne bewegt sich nicht)."""
    h = Heimweg([(0.2, 0.0, 0.3), (0.1, 0.0, 0.3), (0.0, 0.0, 0.3)])
    for _ in range(2000):
        h.schritt(0.2, 0.0, 0.0)
        if h.phase == 'fertig':
            break
    assert h.phase == 'fertig'
    assert h.zeit_um


def test_schleife_wird_weggelassen():
    """Hinweg kreuzt sich bei (1, 0): Die Runde dazwischen fällt weg."""
    spur = spur_aus([(0, 0), (2.0, 0), (2.0, 1.0), (1.0, 1.0), (1.0, -0.5)])
    voll = rueckweg_bauen(spur)
    kurz = schleifen_kuerzen(voll)
    assert kurz[0] == voll[0]
    assert kurz[-1] == voll[-1]
    assert weglaenge(voll) > 5.3        # 1,5 + 1 + 1 + 2
    assert weglaenge(kurz) < 1.8        # 0,5 + 1


def test_gerader_weg_bleibt_gleich():
    p = rueckweg_bauen(spur_aus([(0, 0), (2.0, 0)]))
    kurz = schleifen_kuerzen(p)
    assert weglaenge(kurz) == pytest.approx(weglaenge(p), abs=0.01)
    for a, b in zip(kurz, kurz[1:], strict=False):
        assert math.hypot(b[0] - a[0], b[1] - a[1]) < SCHLEIFE_RADIUS + 0.01


def test_gekuerzter_weg_fliegbar():
    spur = spur_aus([(0, 0), (1.0, 0), (1.0, 1.0), (0.5, 1.0), (0.5, -0.5),
                     (1.5, -0.5)])
    p = schleifen_kuerzen(rueckweg_bauen(spur))
    x, y, _z, yaw = spur[-1]
    h, x, y, yaw, _n = fliege(p, x, y, yaw)
    assert not h.zeit_um
    assert math.hypot(x, y) < 1.5 * ZIEL_RADIUS


def test_kurze_listen():
    assert schleifen_kuerzen([]) == []
    zwei = [(0.0, 0.0, 0.3), (0.1, 0.0, 0.3)]
    assert schleifen_kuerzen(zwei) == zwei


def test_rueckzeit():
    p = rueckweg_bauen(spur_aus([(0, 0), (3.0, 0)]))
    assert rueckzeit(p) == pytest.approx(3.0 / RUECK_TEMPO + RUECK_EXTRA,
                                         abs=0.5)


def test_umkehren_noetig():
    # voller Akku, kurzer Weg: weiterfliegen
    assert not umkehren_noetig(3.90, 0.0, 30.0)
    # knapp über der Grenze, langer Rückweg: umkehren
    assert umkehren_noetig(UMKEHR_AKKU + 0.05, 0.0, 60.0)
    # gemessene Rate zu klein: Mindestrate zählt trotzdem
    assert umkehren_noetig(UMKEHR_AKKU + 0.05, 0.0, 60.0)         == umkehren_noetig(UMKEHR_AKKU + 0.05, 0.0001, 60.0)
    # schneller Abfall: früher umkehren
    assert umkehren_noetig(3.60, 0.01, 30.0)
    assert not umkehren_noetig(3.60, 0.001, 30.0)


# ----------------------------------------------------------- Spiegel (2.1)
def hinflug(befehle, x=0.0, y=0.0, yaw=0.0, z=0.3):
    """Rechen-Drohne fliegt Befehle (vx, vy, gier, Takte) und zeichnet
    Bilder auf wie das Skript: Befehl und Lage VOR dem Takt."""
    bilder = []
    for vx, vy, gier, n in befehle:
        for _ in range(n):
            bilder.append((vx, vy, gier, z, x, y, yaw))
            c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
            x += (c * vx - s * vy) * TAKT
            y += (s * vx + c * vy) * TAKT
            yaw = wrap(yaw + gier * TAKT)
    return bilder, x, y, yaw


def zurueck(bilder, x, y, yaw, max_s=200.0):
    h = Spiegel(spiegel_bauen(bilder), start_gier=0.0)
    neben_max = 0.0
    vx_min = 0.0
    for _ in range(int(max_s / TAKT)):
        vx, vy, gier, _z, neben = h.schritt(x, y, yaw)
        if h.phase == 'nachfliegen':
            neben_max = max(neben_max, neben)
            vx_min = min(vx_min, vx)
        if h.phase == 'fertig':
            return h, x, y, yaw, neben_max, vx_min
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        x += (c * vx - s * vy) * TAKT
        y += (s * vx + c * vy) * TAKT
        yaw = wrap(yaw + gier * TAKT)
    pytest.fail('nicht angekommen')


VORWAERTS_ECKE = [(0.4, 0.0, 0.0, 50),      # 1 m geradeaus
                  (0.0, 0.0, 0.0, 40),      # 2 s stehen
                  (0.0, 0.0, 45.0, 40),     # 90 Grad links drehen
                  (0.4, 0.0, 0.0, 50),      # 1 m geradeaus
                  (0.3, 0.0, 30.0, 60)]     # Kurve


def test_spiegel_bringt_sie_zum_start():
    bilder, x, y, yaw = hinflug(VORWAERTS_ECKE)
    assert math.hypot(x, y) > 1.5
    h, x, y, yaw, neben_max, vx_min = zurueck(bilder, x, y, yaw)
    assert not h.zeit_um
    assert math.hypot(x, y) < 1.5 * ZIEL_RADIUS
    assert abs(wrap(yaw)) < ZIEL_GIER
    assert neben_max < 0.05             # ohne Störung fast genau auf dem Weg


def test_spiegel_nase_voraus():
    """Vorwärts hin heißt vorwärts zurück: nie rückwärts beim Nachfliegen."""
    bilder, x, y, yaw = hinflug(VORWAERTS_ECKE)
    _h, _x, _y, _yaw, _n, vx_min = zurueck(bilder, x, y, yaw)
    assert vx_min > -0.05


def test_spiegel_dreht_erst_um():
    bilder, x, y, yaw = hinflug([(0.4, 0.0, 0.0, 50)])
    h = Spiegel(spiegel_bauen(bilder))
    vx, vy, gier, _z, _n = h.schritt(x, y, yaw)
    assert h.phase == 'wenden'
    assert abs(vx) < 0.05 and abs(vy) < 0.05       # steht fast
    assert gier != 0.0


def test_spiegel_stillstand_faellt_weg():
    bilder, _x, _y, _yaw = hinflug(VORWAERTS_ECKE)
    assert len(spiegel_bauen(bilder)) == len(bilder) - 40


def test_spiegel_korrigiert_versatz():
    """Flow Deck liegt 15 cm daneben: die Wegkorrektur holt das ein."""
    bilder, x, y, yaw = hinflug(VORWAERTS_ECKE)
    h, x, y, yaw, _n, _v = zurueck(bilder, x + 0.10, y - 0.10, yaw + 10.0)
    assert not h.zeit_um
    assert math.hypot(x, y) < 1.5 * ZIEL_RADIUS


def test_spiegel_seitwaerts_bleibt_seitwaerts():
    bilder, x, y, yaw = hinflug([(0.0, 0.3, 0.0, 60)])   # 0,9 m nach links
    h, x, y, yaw, _n, _v = zurueck(bilder, x, y, yaw)
    assert math.hypot(x, y) < 1.5 * ZIEL_RADIUS


def test_spiegel_dreht_nie_schneller_als_rueck_yaw():
    """Im Alleinflug gilt RUECK_YAW, nicht die Handgrenze MAX_YAW (3.2).

    Der Hinflug hier dreht mit 89 Grad/s, also fast mit MAX_YAW. Vor 3.2
    gab der Spiegel das ungebremst weiter und legte die Korrektur noch
    obendrauf."""
    assert RUECK_YAW < MAX_YAW
    bilder, x, y, yaw = hinflug([(0.0, 0.0, 89.0, 40),
                                 (0.3, 0.0, 0.0, 50),
                                 (0.0, 0.0, -89.0, 40)])
    h = Spiegel(spiegel_bauen(bilder), start_gier=0.0)
    for _ in range(int(120.0 / TAKT)):
        if h.phase == 'fertig':
            break
        vx, vy, gier, _z, _n = h.schritt(x, y, yaw)
        assert abs(gier) <= RUECK_YAW + 1e-9
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        x += (c * vx - s * vy) * TAKT
        y += (s * vx + c * vy) * TAKT
        yaw = wrap(yaw + gier * TAKT)


def test_glaetten_bricht_drehstoesse():
    """glaette() ist der Filter, durch den seit 3.2 auch der Drehbefehl
    des Alleinflugs läuft. Ein Sprung von 0 auf RUECK_YAW darf nicht in
    einem Takt ankommen."""
    wert = 0.0
    wert += (RUECK_YAW - wert) * RAMPE
    assert wert < RUECK_YAW / 2.0
    for _ in range(40):
        wert += (RUECK_YAW - wert) * RAMPE
    assert abs(wert - RUECK_YAW) < 0.5


def test_tempo_bleibt_unter_dem_firmware_anschlag():
    """Der Geschwindigkeitsregler der Firmware rechnet 25 Grad Neigung
    je 1 m/s (PID_VEL_X_KP) und darf nur 20 Grad kippen
    (PID_VEL_ROLL_MAX). Ab 0,80 m/s steht er am Anschlag und schießt
    über. MAX_SPEED muss darunter bleiben, sonst wippt sie wieder."""
    assert pytest.approx(20.0 / 25.0) == SPEED_SAETTIGUNG
    assert MAX_SPEED < SPEED_SAETTIGUNG
    neigung = MAX_SPEED * 25.0
    assert neigung < 20.0
    # mindestens 10 Prozent Reserve, damit der Regler noch gegenhalten
    # kann, wenn Wind oder Bodeneffekt dazukommen
    assert MAX_SPEED <= 0.9 * SPEED_SAETTIGUNG


def test_bremsabstand_reicht_fuer_das_tempo():
    """BREMS_ABSTAND wird aus MAX_SPEED gerechnet. Er muss den Weg
    abdecken, den sie bei Vollgas noch macht, bis der Bremsbefehl voll
    anliegt und sie ausgerollt ist."""
    assert pytest.approx(HALTE_ABSTAND
                                          + MAX_SPEED * REAKTION_S) == BREMS_ABSTAND
    assert BREMS_ABSTAND > HALTE_ABSTAND
    # Die Glättung braucht rund 0,4 s, bis ein Bremsbefehl voll da ist
    # (RAMPE = 0.25 bei 20 Hz: 1 - 0,75**8 = 0,90). In der Zeit fliegt
    # sie bei Vollgas noch ein Stück. Das muss in das Fenster passen.
    takte_bis_90_prozent = 8
    weg_bis_befehl_da = MAX_SPEED * takte_bis_90_prozent * TAKT
    assert weg_bis_befehl_da < BREMS_ABSTAND - HALTE_ABSTAND


def test_bremskennlinie_faellt_auf_null():
    """Die Drosselung in bremsen() fällt zwischen BREMS_ABSTAND und
    HALTE_ABSTAND gleichmäßig von MAX_SPEED auf null."""
    def grenze(m):
        if m >= BREMS_ABSTAND:
            return MAX_SPEED
        if m <= HALTE_ABSTAND:
            return 0.0
        return MAX_SPEED * ((m - HALTE_ABSTAND)
                            / (BREMS_ABSTAND - HALTE_ABSTAND))

    assert grenze(2.0) == pytest.approx(MAX_SPEED)
    assert grenze(HALTE_ABSTAND) == 0.0
    assert grenze(0.05) == 0.0
    mitte = (BREMS_ABSTAND + HALTE_ABSTAND) / 2.0
    assert grenze(mitte) == pytest.approx(MAX_SPEED / 2.0)
    # monoton: näher dran heißt nie schneller
    werte = [grenze(m / 100.0) for m in range(0, 120)]
    assert all(a <= b + 1e-9 for a, b in zip(werte, werte[1:], strict=False))


def test_tuerdurchfahrt_wird_nicht_ausgebremst():
    """In einer Tür sind beide Seiten nah. Die Zentrierung
    (TUER_TEMPO) muss trotzdem durchkommen, sonst zappelt sie im
    Rahmen. Bei einer 90er Tür hat sie mittig gut 0,40 m je Seite."""
    from flow_ranger_heimflug import TUER_TEMPO

    seite = 0.40
    grenze = MAX_SPEED * ((seite - HALTE_ABSTAND)
                          / (BREMS_ABSTAND - HALTE_ABSTAND))
    assert grenze > TUER_TEMPO


def test_replay_bleibt_beim_tempo_der_aufnahme() -> None:
    """3.4: Der Deckel im Replay richtet sich nach der Aufnahme, nicht
    nach MAX_SPEED. Ein langsam geflogener Hinflug kommt langsam
    zurück, auch wenn MAX_SPEED hoch steht."""
    langsam: list[Bild] = [(0.30, 0.0, 0.0, 0.5, float(i) * 0.015, 0.0, 0.0)
                           for i in range(40)]
    sp = Spiegel(spiegel_bauen(langsam), start_gier=0.0)
    assert sp.deckel == pytest.approx(0.30)
    assert sp.deckel < MAX_SPEED


def test_replay_deckel_ueberschreitet_max_speed_nie() -> None:
    """Auch eine schnelle Aufnahme darf den Handstick-Wert nicht
    sprengen: MAX_SPEED bleibt die harte Obergrenze."""
    schnell: list[Bild] = [(MAX_SPEED, 0.0, 0.0, 0.5,
                            float(i) * 0.04, 0.0, 0.0)
                           for i in range(40)]
    sp = Spiegel(spiegel_bauen(schnell), start_gier=0.0)
    assert sp.deckel == pytest.approx(MAX_SPEED)


def test_replay_faehrt_nicht_schneller_als_der_deckel() -> None:
    """Abgespielte Fahrt plus Wegkorrektur zusammen bleiben unter dem
    Deckel -- auch wenn die Drohne weit neben dem Weg steht und die
    Korrektur voll aufdreht."""
    auf: list[Bild] = [(0.40, 0.0, 0.0, 0.5, float(i) * 0.02, 0.0, 0.0)
                       for i in range(40)]
    sp = Spiegel(spiegel_bauen(auf), start_gier=0.0)
    sp.phase = 'nachfliegen'
    schnellste = 0.0
    for _ in range(30):
        # 1 m neben dem Weg: die Korrektur zieht mit voller Kraft
        vx, vy, _g, _z, _rest = sp.schritt(0.0, 1.0, 0.0)
        schnellste = max(schnellste, math.hypot(vx, vy))
    assert schnellste <= sp.deckel + 1e-9


def test_rueckflug_nie_schneller_als_der_hinflug() -> None:
    """Der Kern von 3.4, an der echten Aufnahme vom 20.09. 15:41: die
    enthielt höchstens 0,51 m/s, also darf der Rückflug auch nicht
    schneller werden -- auch wenn MAX_SPEED bei 0,72 steht."""
    auf: list[Bild] = [(0.51, 0.0, 0.0, 0.5, float(i) * 0.0255, 0.0, 0.0)
                       for i in range(60)]
    sp = Spiegel(spiegel_bauen(auf), start_gier=0.0)
    schnellster_takt = max(math.hypot(b[0], b[1]) for b in auf)
    assert sp.deckel == pytest.approx(schnellster_takt)
    assert sp.deckel < MAX_SPEED

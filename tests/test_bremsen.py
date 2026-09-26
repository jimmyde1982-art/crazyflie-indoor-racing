"""Tests für die Bremsrampe in FlowRanger.bremsen().

Das ist die Funktion, die verhindert, dass die Drohne in eine Wand
fliegt. Sie ist reine Rechnerei: Abstände rein, erlaubte Geschwindigkeit
raus. Deshalb lässt sie sich ohne Drohne prüfen.

Die Abstände stehen in self.d in Millimetern, so wie sie vom
Multi-Ranger kommen. abstand() rechnet daraus Meter.
"""

import pytest

from flow_ranger_recorder import (
    BREMS_ABSTAND,
    HALTE_ABSTAND,
    MAX_SPEED,
    FlowRanger,
)


def ranger(**abstaende_mm):
    """FlowRanger mit vorgegebenen Sensorwerten, ohne Hardware.

    Nicht angegebene Richtungen bekommen 8000 mm = 'nichts gesehen'.
    """
    r = FlowRanger(None)
    r.d = {
        'range.front': 8000,
        'range.back': 8000,
        'range.left': 8000,
        'range.right': 8000,
    }
    r.d.update(abstaende_mm)
    return r


def test_freie_bahn_bremst_nicht():
    """Nichts in der Nähe: die volle Geschwindigkeit kommt durch."""
    vx, vy, gebremst = ranger().bremsen(MAX_SPEED, 0.0)
    assert vx == MAX_SPEED
    assert vy == 0.0
    assert gebremst is False


def test_ab_brems_abstand_noch_volle_fahrt():
    """Genau auf der Bremsschwelle wird noch nicht gedrosselt."""
    mm = int(BREMS_ABSTAND * 1000)
    vx, _, gebremst = ranger(**{'range.front': mm}).bremsen(MAX_SPEED, 0.0)
    assert vx == MAX_SPEED
    assert gebremst is False


def test_am_halte_abstand_steht_sie():
    """Bei 15 cm ist die erlaubte Geschwindigkeit null."""
    mm = int(HALTE_ABSTAND * 1000)
    vx, _, gebremst = ranger(**{'range.front': mm}).bremsen(MAX_SPEED, 0.0)
    assert vx == 0.0
    assert gebremst is True


def test_unter_halte_abstand_steht_sie_auch():
    """Näher als 15 cm darf sie sich dem Hindernis nicht mehr nähern.

    10 cm ist der Notlandungs-Abstand. Käme hier ein Wert > 0 heraus,
    würde sie in die Notlandung hineinkriechen.
    """
    vx, _, gebremst = ranger(**{'range.front': 100}).bremsen(MAX_SPEED, 0.0)
    assert vx == 0.0
    assert gebremst is True


def test_mitte_der_rampe_ist_halbe_geschwindigkeit():
    """Zwischen Halte- und Bremsabstand fällt die Grenze gleichmäßig."""
    mitte_m = (HALTE_ABSTAND + BREMS_ABSTAND) / 2
    vx, _, gebremst = ranger(
        **{'range.front': int(mitte_m * 1000)}
    ).bremsen(MAX_SPEED, 0.0)
    assert vx == pytest.approx(MAX_SPEED / 2)
    assert gebremst is True


def test_wegfliegen_ist_immer_erlaubt():
    """Hindernis vorn, sie fliegt rückwärts: das wird nicht gebremst.

    Sonst säße sie vor einem Hindernis fest.
    """
    vx, _, gebremst = ranger(**{'range.front': 100}).bremsen(-MAX_SPEED, 0.0)
    assert vx == -MAX_SPEED
    assert gebremst is False


def test_seitwaerts_wird_genauso_gebremst():
    """Links ist positiv. Hindernis links bremst die Fahrt nach links."""
    mm = int(HALTE_ABSTAND * 1000)
    _, vy, gebremst = ranger(**{'range.left': mm}).bremsen(0.0, MAX_SPEED)
    assert vy == 0.0
    assert gebremst is True


def test_ungueltige_messung_gilt_als_frei():
    """Werte unter SENSOR_MIN sind keine Messung, sondern Rauschen.

    abstand() gibt dafür None zurück, und None heißt 'freie Bahn'.
    Wichtig: ein hängender Sensor darf sie nicht mitten im Flug festsetzen.
    """
    vx, _, gebremst = ranger(**{'range.front': 10}).bremsen(MAX_SPEED, 0.0)
    assert vx == MAX_SPEED
    assert gebremst is False

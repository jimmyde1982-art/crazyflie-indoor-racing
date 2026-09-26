import sys

import cflib.crtp
import pygame
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

URI = 'radio://0/80/2M/E7E7E7E7E7'

# Sicherheits- und Fluglimits
MAX_THRUST = 45000
MIN_THRUST = 20000
MAX_ROLL = 20.0
MAX_PITCH = 20.0
MAX_YAW_RATE = 100.0

current_battery_string = "Warte auf Daten..."

def battery_callback(timestamp, data, logconf):
    global current_battery_string
    vbat = data['pm.vbat']
    level = data['pm.batteryLevel']
    status = "OK"
    if vbat < 3.5:
        status = "🚨 NOTLANDUNG!"
    elif vbat < 3.7:
        status = "⚠️ AKKU RECHT LEER!"
    current_battery_string = f"Akku: {vbat:.2f}V ({level}%) [{status}]"

def init_xbox_controller():
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("Fehler: Kein Xbox-Controller gefunden!")
        sys.exit()
    controller = pygame.joystick.Joystick(0)
    controller.init()
    print(f"Controller erkannt: {controller.get_name()}")
    return controller

def run_flight_and_log(scf, controller):
    cf = scf.cf
    clock = pygame.time.Clock()

    log_config = LogConfig(name='BatteryStatus', period_in_ms=1000)
    log_config.add_variable('pm.vbat', 'float')
    log_config.add_variable('pm.batteryLevel', 'uint8_t')

    cf.log.add_config(log_config)
    log_config.data_received_cb.add_callback(battery_callback)
    log_config.start()

    print("\n=========================================")
    print(" READY TO FLY - SICHERER MODUS AKTIV")
    print(" Linker Stick NACH OBEN = Gas geben")
    print(" X-Taste am Controller   = NOT-AUS")
    print("=========================================\n")

    try:
        while True:
            pygame.event.pump()

            # Not-Aus Abfrage (Zur Sicherheit reagiert es jetzt auf X (2) oder Back-Taste (4))
            if controller.get_button(2) or controller.get_button(4):
                print("\n!!! NOT-AUS BETÄTIGT !!!")
                break

            # 2. Sticks präzise auslesen (Standard Windows XInput Layout)
            axis_left_y  = -controller.get_axis(1)  # Linker Stick Vertikal (-1 unten, +1 oben)
            axis_left_x  = controller.get_axis(0)   # Linker Stick Horizontal
            axis_right_y = -controller.get_axis(4)  # Rechter Stick Vertikal (oft Achse 4 bei Windows)
            axis_right_x = controller.get_axis(3)   # Rechter Stick Horizontal (oft Achse 3 bei Windows)

            # Deadzone gegen Ausleiern (15% für mehr Sicherheit)
            if abs(axis_left_y) < 0.15:
                axis_left_y = 0
            if abs(axis_left_x) < 0.15:
                axis_left_x = 0
            if abs(axis_right_y) < 0.15:
                axis_right_y = 0
            if abs(axis_right_x) < 0.15:
                axis_right_x = 0

            # 3. KORRIGIERTE SCHUB-LOGIK:
            # Nur wenn der Stick aktiv nach oben geschoben wird (> 0), gibt es Schub.
            # Unten und Mitte bedeuten ab jetzt absolut 0% Gas.
            if axis_left_y > 0:
                # Skaliert den Bereich von 0.0 bis 1.0 auf MIN_THRUST bis MAX_THRUST
                thrust = int(MIN_THRUST + (axis_left_y * (MAX_THRUST - MIN_THRUST)))
            else:
                thrust = 0

            roll = axis_right_x * MAX_ROLL
            pitch = axis_right_y * MAX_PITCH
            yaw_rate = axis_left_x * MAX_YAW_RATE

            # 4. Befehle senden
            if thrust > 0:
                cf.commander.send_setpoint(roll, pitch, yaw_rate, thrust)
            else:
                cf.commander.send_stop_setpoint()

            # Statuszeile
            print(f"[Flug] Schub: {thrust:5d} | Roll: {roll:5.1f} | Pitch: {pitch:5.1f} || {current_battery_string}      ", end='\r')

            clock.tick(50)

    except KeyboardInterrupt:
        print("\nAbbruch durch Tastatur.")
    finally:
        log_config.stop()
        cf.commander.send_stop_setpoint()
        print("\nMotoren aus. System gestoppt.")

if __name__ == '__main__':
    cflib.crtp.init_drivers()
    xbox_pad = init_xbox_controller()

    try:
        with SyncCrazyflie(URI, cf=Crazyflie(rw_cache='./cache')) as scf:
            run_flight_and_log(scf, xbox_pad)
    except Exception as e:
        print(f"\nFehler bei der Verbindung: {e}")


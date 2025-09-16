import os
from dotenv import load_dotenv
import csv
import time
import datetime
import argparse
from tinkerforge.ip_connection import IPConnection
from tinkerforge.bricklet_analog_in_v3 import BrickletAnalogInV3

# -----------------------------
# CLI arguments (with fallback)
# -----------------------------
load_dotenv()

parser = argparse.ArgumentParser(description="Read AnalogInV3 voltage and (optionally) convert to pH from two-point calibration.")
parser.add_argument("uid", nargs="?", default=os.getenv("TF_UID", "missing"),
                    help="Tinkerforge Bricklet UID (positional). Defaults to TF_UID from .env.")
parser.add_argument("--v_low_mv", type=float, default=None,
                    help="Voltage in mV at the lower pH calibration point (e.g., 1800).")
parser.add_argument("--v_high_mv", type=float, default=None,
                    help="Voltage in mV at the higher pH calibration point (e.g., 1200).")
parser.add_argument("--ph_low", type=float, default=None,
                    help="Lower pH calibration value (e.g., 4.00).")
parser.add_argument("--ph_high", type=float, default=None,
                    help="Higher pH calibration value (e.g., 7.00).")
args = parser.parse_args()

UID = args.uid

# Optional PubNub publishing
PUBLISH = os.getenv('PUBLISH', 'True').lower() in ('1', 'true', 'yes')
PUBNUB_PUBLISH_KEY = os.getenv('PUBNUB_PUBLISH_KEY', '')
PUBNUB_SUBSCRIBE_KEY = os.getenv('PUBNUB_SUBSCRIBE_KEY', '')
PUBNUB_CHANNEL = os.getenv('PUBNUB_CHANNEL', '')

if PUBLISH:
    from pubnub.pnconfiguration import PNConfiguration
    from pubnub.pubnub import PubNub

    pnconfig = PNConfiguration()
    pnconfig.publish_key = PUBNUB_PUBLISH_KEY
    pnconfig.subscribe_key = PUBNUB_SUBSCRIBE_KEY
    pnconfig.uuid = 'tinkerforge-analog-in'
    pubnub = PubNub(pnconfig)

# Tinkerforge setup
HOST = os.getenv('TF_HOST', 'localhost')
PORT = int(os.getenv('TF_PORT', 4223))

CSV_FILE = os.getenv('CSV_FILE_COLLECTOR', 'sensor_data.csv')
CSV_FILE_WITH_UID = f"{CSV_FILE.split('.csv')[0]}_{UID}.csv"
INTERVAL = int(os.getenv('INTERVAL', 5))  # seconds

# -----------------------------
# Calibration & transform()
# -----------------------------
def calibration_complete() -> bool:
    return (args.v_low_mv is not None and
            args.v_high_mv is not None and
            args.ph_low is not None and
            args.ph_high is not None and
            args.v_high_mv != args.v_low_mv)

def transform(voltage_mV: float):
    """
    Convert voltage (mV) to pH using two-point linear calibration.
    Returns a float pH value, or None if calibration is incomplete/invalid.
    """
    if not calibration_complete():
        return None
    # Linear mapping through (v_low, pH_low) and (v_high, pH_high)
    slope = (args.ph_high - args.ph_low) / (args.v_high_mv - args.v_low_mv)
    return args.ph_low + (voltage_mV - args.v_low_mv) * slope

# Ensure CSV has header (now includes pH column)
if not os.path.exists(CSV_FILE_WITH_UID):
    with open(CSV_FILE_WITH_UID, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['time', 'value', 'pH'])  # keep 'value' for backward compat; add pH

# Create IP connection and device object
ipcon = IPConnection()
analog_in = BrickletAnalogInV3(UID, ipcon)

try:
    ipcon.connect(HOST, PORT)
    print(f'Connected to Tinkerforge at {HOST}:{PORT}, reading Analog In {UID}')

    if calibration_complete():
        print(f'Calibration active: (v_low={args.v_low_mv} mV, pH_low={args.ph_low}) '
              f'-> (v_high={args.v_high_mv} mV, pH_high={args.ph_high})')
    else:
        print('No valid calibration provided. pH will be left blank in CSV.')

    while True:
        # Read value (raw mV)
        mV = analog_in.get_voltage()
        timestamp = datetime.datetime.now().isoformat()

        # Transform to pH if possible
        pH_val = transform(mV)
        pH_out = f'{pH_val:.3f}' if pH_val is not None else ''

        # Write to CSV
        with open(CSV_FILE_WITH_UID, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, mV, pH_out])

        # Console output
        if pH_val is not None:
            print(f'[{timestamp}] Voltage: {mV/1000:.3f} V | pH: {pH_val:.3f}')
        else:
            print(f'[{timestamp}] Voltage: {mV/1000:.3f} V | pH: (no calibration)')

        # Publish to PubNub if enabled (include pH only if available)
        if PUBLISH:
            try:
                message = {'time': timestamp, 'value_mV': mV}
                if pH_val is not None:
                    message['pH'] = round(pH_val, 3)
                pubnub.publish().channel(PUBNUB_CHANNEL).message(message).sync()
            except Exception as e:
                print(f'Error publishing to PubNub: {e}')

        time.sleep(INTERVAL)

except KeyboardInterrupt:
    print('Interrupted by user')

finally:
    ipcon.disconnect()
    print('Disconnected.')

import os
from dotenv import load_dotenv
import csv
import time
import datetime
from tinkerforge.ip_connection import IPConnection
from tinkerforge.bricklet_analog_in_v3 import BrickletAnalogInV3

# Read command line argument for UID
import sys
if len(sys.argv) > 1:
    UID = sys.argv[1]   # Use UID from command line argument
else:
    UID = os.getenv('TF_UID', 'missing')

# Load environment variables from .env file
load_dotenv()

# Optional PubNub publishing
PUBLISH = os.getenv('PUBLISH', 'True').lower() in ('1', 'true', 'yes')  # Set PUBLISH in .env to 'False' to disable PubNub publishing
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

# Ensure CSV has header
if not os.path.exists(CSV_FILE_WITH_UID):
    with open(CSV_FILE_WITH_UID, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['time', 'value'])

# Create IP connection and device object
ipcon = IPConnection()
analog_in = BrickletAnalogInV3(UID, ipcon)

try:
    ipcon.connect(HOST, PORT)
    print(f'Connected to Tinkerforge at {HOST}:{PORT}, reading Analog In {UID}')

    while True:
        # Read value (raw mV)
        mV = analog_in.get_voltage()
        timestamp = datetime.datetime.now().isoformat()

        # Write to CSV
        with open(CSV_FILE_WITH_UID, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, mV])

        print(f'[{timestamp}] Voltage: {mV/1000:.3f} V')

        # Publish to PubNub if enabled
        if PUBLISH:
            try:
                pubnub.publish().channel(PUBNUB_CHANNEL).message({
                    'time': timestamp,
                    'value_mV': mV
                }).sync()
            except Exception as e:
                print(f'Error publishing to PubNub: {e}')

        time.sleep(INTERVAL)

except KeyboardInterrupt:
    print('Interrupted by user')

finally:
    ipcon.disconnect()
    print('Disconnected.')

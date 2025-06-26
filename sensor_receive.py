import os
from dotenv import load_dotenv
import csv
import time
from pubnub.pnconfiguration import PNConfiguration
from pubnub.pubnub import PubNub
from pubnub.callbacks import SubscribeCallback
from pubnub.enums import PNStatusCategory

# Load configuration from .env
load_dotenv()

PUBNUB_PUBLISH_KEY = os.getenv('PUBNUB_PUBLISH_KEY', 'your-publish-key')
PUBNUB_SUBSCRIBE_KEY = os.getenv('PUBNUB_SUBSCRIBE_KEY', 'your-subscribe-key')
PUBNUB_CHANNEL = os.getenv('PUBNUB_CHANNEL', 'analog_in_channel')
CSV_FILE = os.getenv('CSV_FILE_RECEIVER', 'sensor_data.csv')

# Ensure CSV has header
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['time', 'value'])

# Configure PubNub
pnconfig = PNConfiguration()
pnconfig.publish_key = PUBNUB_PUBLISH_KEY
pnconfig.subscribe_key = PUBNUB_SUBSCRIBE_KEY
pnconfig.uuid = 'tinkerforge-subscriber'

pubnub = PubNub(pnconfig)

class AnalogInListener(SubscribeCallback):
    def status(self, pubnub, status):
        if status.category == PNStatusCategory.PNConnectedCategory:
            print(f"Connected to PubNub channel '{PUBNUB_CHANNEL}'")

    def message(self, pubnub, message):
        try:
            payload = message.message
            timestamp = payload.get('time')
            value = payload.get('value_mV')

            # Append to CSV
            with open(CSV_FILE, mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, value])

            print(f"[{timestamp}] Received value: {value} mV")
        except Exception as e:
            print(f"Error handling message: {e}")

listener = AnalogInListener()
pubnub.add_listener(listener)
pubnub.subscribe().channels(PUBNUB_CHANNEL).execute()

try:
    # Keep the script running to listen for messages
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Interrupted by user, shutting down...")
    pubnub.unsubscribe().channels(PUBNUB_CHANNEL).execute()
    pubnub.stop()

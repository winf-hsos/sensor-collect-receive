# Sensor Sender and Receiver Dashboard

## Run 

Start the `sensor_collect.py` script to start collecting data from the sensor and sending it to the PubNub channel (optional). Make sure you rename the `.env-RENAME` file to `.env` and fill in the required values. The first argument is the UID of your Tinkerforge device. If you don't provide it, the script will use the `TF_UID` value from the `.env` file.

```bash
python sensor_collect.py 2ccC
```

At the receiving end, start the `sensor_receiver.py` script to receive the data and save it to a CSV file.

```bash
python sensor_receiver.py
```

## Run the Streamlit Dashboard

To run the Streamlit dashboard, execute the following command in your terminal:
```bash
streamlit run app.py
```
## Dashboard Configuration

You can configure the dashboard by modifying the `.env` file. The following environment variables are available:

- `PUBNUB_PUBLISH_KEY`: Your PubNub publish key.
- `PUBNUB_SUBSCRIBE_KEY`: Your PubNub subscribe key.
- `PUBNUB_CHANNEL`: The PubNub channel to subscribe to.
- `CSV_FILE_COLLECTOR`: The CSV file where the collected sensor data will be saved.
- `CSV_FILE_RECEIVER`: The CSV file where the received sensor data will be saved.
- `INTERVAL`: The interval in seconds for the auto-refresh of the dashboard.
- `TF_UID`: The unique identifier for the Tinkerforge device. Only used if no UID is provided as an argument.
- `DASHBOARD_TITLE`: The title of the dashboard.

from flask import Flask, jsonify, request
from datetime import datetime, timezone, timedelta
import requests
import os

app = Flask(__name__)

NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")
NASA_BASE = "https://api.nasa.gov/DONKI"

@app.route("/")
def home():
    return jsonify({
        "project": "ASTRA",
        "message": "ASTRA API is running",
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

@app.route("/api/status")
def api_status():
    return jsonify({
        "project": "ASTRA",
        "service": "NASA Data Processing API",
        "status": "online",
        "data_sources": {
            "NASA_DONKI": "available",
            "NASA_OSDR": "not_connected",
            "Radiation_Dosimetry": "not_connected"
        }
    })

@app.route("/api/donki")
def donki():
    event_type = request.args.get("type", "SEP").upper()

    allowed_types = ["SEP", "FLR", "CME", "GST"]

    if event_type not in allowed_types:
        return jsonify({
            "status": "error",
            "message": "Unsupported event type",
            "allowed_types": allowed_types
        }), 400

    end_date = request.args.get(
        "end_date",
        datetime.now(timezone.utc).date().isoformat()
    )

    start_date = request.args.get(
        "start_date",
        (datetime.now(timezone.utc).date() - timedelta(days=7)).isoformat()
    )

    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({
            "status": "error",
            "message": "Dates must use YYYY-MM-DD"
        }), 400

    if start > end or (end - start).days > 30:
        return jsonify({
            "status": "error",
            "message": "Date range must be between 0 and 30 days"
        }), 400

    url = f"{NASA_BASE}/{event_type}"

    try:
        response = requests.get(
            url,
            params={
                "startDate": start_date,
                "endDate": end_date,
                "api_key": NASA_API_KEY
            },
            timeout=25
        )

        response.raise_for_status()
        events = response.json()

        if not isinstance(events, list):
            return jsonify({
                "status": "error",
                "message": "Unexpected NASA response"
            }), 502

        return jsonify({
            "status": "success",
            "source": "NASA DONKI",
            "event_type": event_type,
            "start_date": start_date,
            "end_date": end_date,
            "event_count": len(events),
            "events": events
        })

    except requests.RequestException as error:
        return jsonify({
            "status": "error",
            "source": "NASA DONKI",
            "message": "Could not retrieve NASA data",
            "details": str(error)
        }), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)


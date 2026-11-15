
from flask import Flask, jsonify, request, render_template
from datetime import datetime, timezone, timedelta
import requests

app = Flask(__name__)

NASA_DONKI_BASE = "https://ccmc.gsfc.nasa.gov/DONKI-API/get"

ALLOWED_EVENTS = ["SEP", "FLR", "CME", "GST"]


# Main ASTRA Dashboard
@app.route("/")
def home():
    return render_template("index.html")


# Health Check
@app.route("/health")
def health():
    return jsonify({
        "project": "ASTRA",
        "status": "healthy"
    })


# API Status
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


# NASA DONKI Events API
@app.route("/api/donki")
def get_donki_events():

    event_type = request.args.get("type", "SEP").upper()

    if event_type not in ALLOWED_EVENTS:
        return jsonify({
            "status": "error",
            "message": "Unsupported event type",
            "allowed_types": ALLOWED_EVENTS
        }), 400

    today = datetime.now(timezone.utc).date()
    default_start = today - timedelta(days=7)

    start_date = request.args.get(
        "start_date",
        default_start.isoformat()
    )

    end_date = request.args.get(
        "end_date",
        today.isoformat()
    )

    try:
        start = datetime.strptime(
            start_date, "%Y-%m-%d"
        ).date()

        end = datetime.strptime(
            end_date, "%Y-%m-%d"
        ).date()

    except ValueError:
        return jsonify({
            "status": "error",
            "message": "Dates must use YYYY-MM-DD"
        }), 400

    if start > end:
        return jsonify({
            "status": "error",
            "message": "Start date cannot be after end date"
        }), 400

    if (end - start).days > 30:
        return jsonify({
            "status": "error",
            "message": "Maximum date range is 30 days"
        }), 400

    url = f"{NASA_DONKI_BASE}/{event_type}"

    try:
        response = requests.get(
            url,
            params={
                "startDate": start_date,
                "endDate": end_date
            },
            headers={
                "Accept": "application/json",
                "User-Agent": "ASTRA-NASA-SpaceApps/1.0"
            },
            timeout=30
        )

        response.raise_for_status()

        events = response.json()

        if not isinstance(events, list):
            return jsonify({
                "status": "error",
                "message": "Unexpected response from NASA DONKI"
            }), 502

        return jsonify({
            "status": "success",
            "source": "NASA CCMC DONKI",
            "event_type": event_type,
            "start_date": start_date,
            "end_date": end_date,
            "event_count": len(events),
            "events": events
        })

    except requests.exceptions.Timeout:
        return jsonify({
            "status": "error",
            "message": "NASA DONKI request timed out"
        }), 504

    except requests.exceptions.HTTPError as error:
        return jsonify({
            "status": "error",
            "source": "NASA CCMC DONKI",
            "message": "NASA returned an HTTP error",
            "details": str(error)
        }), 502

    except requests.exceptions.RequestException as error:
        return jsonify({
            "status": "error",
            "message": "Could not connect to NASA DONKI",
            "details": str(error)
        }), 502

    except ValueError:
        return jsonify({
            "status": "error",
            "message": "NASA returned invalid JSON"
        }), 502


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )


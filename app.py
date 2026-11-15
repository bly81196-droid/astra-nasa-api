
import csv
from pathlib import Path
from statistics import mean, median
from datetime import datetime, timezone, timedelta

import requests
from flask import Flask, jsonify, request, render_template


app = Flask(__name__)

# NASA DONKI
NASA_DONKI_BASE = "https://ccmc.gsfc.nasa.gov/DONKI-API/get"
ALLOWED_EVENTS = ["SEP", "FLR", "CME", "GST"]

# NASA OSDR Radiation Data
RADIATION_CSV = Path(app.root_path) / "ASTRA_DosTel1_NASA.csv"


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
    radiation_available = RADIATION_CSV.is_file()

    return jsonify({
        "project": "ASTRA",
        "service": "NASA Data Processing API",
        "status": "online",
        "data_sources": {
            "NASA_DONKI": "available",
            "NASA_OSDR": (
                "available" if radiation_available else "not_connected"
            ),
            "Radiation_Dosimetry": (
                "available" if radiation_available else "not_connected"
            )
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


# NASA OSDR Radiation Dosimetry API
@app.route("/api/radiation")
def get_radiation_data():

    if not RADIATION_CSV.is_file():
        return jsonify({
            "status": "error",
            "message": "NASA radiation CSV file not found",
            "expected_file": RADIATION_CSV.name
        }), 404

    # Optional date filters
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    try:
        if start_date:
            datetime.strptime(start_date, "%Y-%m-%d")

        if end_date:
            datetime.strptime(end_date, "%Y-%m-%d")

    except ValueError:
        return jsonify({
            "status": "error",
            "message": "Dates must use YYYY-MM-DD"
        }), 400

    if start_date and end_date and start_date > end_date:
        return jsonify({
            "status": "error",
            "message": "Start date cannot be after end date"
        }), 400

    readings = []

    try:
        with open(
            RADIATION_CSV,
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            reader = csv.DictReader(file)

            required_columns = {
                "timestamp",
                "instrument_id",
                "absorbed_dose_rate",
                "instrument",
                "module",
                "spacecraft"
            }

            available_columns = set(reader.fieldnames or [])

            if not required_columns.issubset(available_columns):
                return jsonify({
                    "status": "error",
                    "message": "Unexpected CSV structure",
                    "required_columns": sorted(required_columns)
                }), 500

            for row in reader:

                timestamp = row["timestamp"].strip()
                date_only = timestamp[:10]

                # Validate timestamp
                try:
                    datetime.strptime(
                        timestamp,
                        "%Y-%m-%dT%H:%M:%S"
                    )
                except ValueError:
                    continue

                # Apply date filters
                if start_date and date_only < start_date:
                    continue

                if end_date and date_only > end_date:
                    continue

                try:
                    value = float(row["absorbed_dose_rate"])
                except (ValueError, TypeError):
                    continue

                if not (value >= 0 and value < float("inf")):
                    continue

                readings.append({
                    "timestamp": timestamp,
                    "instrument_id": row["instrument_id"],
                    "absorbed_dose_rate": value,
                    "instrument": row["instrument"],
                    "module": row["module"],
                    "spacecraft": row["spacecraft"]
                })

        # Keep readings in chronological order
        readings.sort(key=lambda item: item["timestamp"])

        if not readings:
            return jsonify({
                "status": "success",
                "source": "NASA OSDR RadLab",
                "measurement": "Absorbed dose rate",
                "unit": "µGy/hour",
                "reading_count": 0,
                "message": "No readings found for selected dates",
                "readings": []
            })

        values = [
            item["absorbed_dose_rate"]
            for item in readings
        ]

        return jsonify({
            "status": "success",
            "source": "NASA OSDR RadLab",
            "source_file": RADIATION_CSV.name,
            "measurement": "Absorbed dose rate",
            "unit": "µGy/hour",

            "instrument": "DosTel1",
            "module": "Columbus",
            "spacecraft": "ISS",

            "start_date": readings[0]["timestamp"][:10],
            "end_date": readings[-1]["timestamp"][:10],

            "reading_count": len(readings),

            "statistics": {
                "mean": round(mean(values), 6),
                "median": round(median(values), 6),
                "minimum": round(min(values), 6),
                "maximum": round(max(values), 6)
            },

            "readings": readings
        })

    except OSError as error:
        return jsonify({
            "status": "error",
            "message": "Could not read radiation CSV file",
            "details": str(error)
        }), 500


# Run Flask Application
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )


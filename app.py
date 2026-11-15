from flask import Flask, jsonify
from datetime import datetime, timezone

app = Flask(__name__)

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
    return jsonify({
        "status": "healthy"
    })

@app.route("/api/status")
def api_status():
    return jsonify({
        "project": "ASTRA",
        "service": "NASA Data Processing API",
        "status": "online",
        "data_sources": {
            "NASA_DONKI": "not_connected",
            "NASA_OSDR": "not_connected",
            "Radiation_Dosimetry": "not_connected"
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

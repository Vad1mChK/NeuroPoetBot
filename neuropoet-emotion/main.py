from flask import Flask, request, jsonify
from datetime import datetime, UTC
import random
import os
from dotenv import load_dotenv

app = Flask(__name__)


# Mock emotion detector - replace with actual ML model
def analyze_text(text: str) -> dict:
    """Returns mock emotion scores for demonstration"""
    emotions = ['happy', 'sad', 'anger', 'surprise', 'fear', 'disgust']
    return {e: round(random.uniform(0, 1), 2) for e in emotions}


@app.route('/analyze', methods=['POST'])
def analyze_endpoint():
    try:
        data = request.json

        # Validate request format
        if not data or 'user_id' not in data or 'text' not in data:
            return jsonify({"error": "Invalid request format"}), 400

        # Process request
        result = {
            "emotions": analyze_text(data['text']),
            "timestamp": datetime.now(UTC).isoformat(),
            "user_id": data['user_id']
        }

        return jsonify(result), 200

    except Exception as e:
        app.logger.error(f"Analyze error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "OK",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": "1.0"
    }), 200


if __name__ == '__main__':
    load_dotenv()
    port = int(os.getenv("NPB_EMOTION_API_PORT", 5000))
    app.run(host='0.0.0.0', port=port)
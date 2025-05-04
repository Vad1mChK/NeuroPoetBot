from flask import Flask, request, jsonify
from datetime import datetime, UTC
import random
import os
from dotenv import load_dotenv

app = Flask(__name__)


def generate_poem(emotions: dict[str, float]) -> str:
    words = 'I am Steve this is a crafting table big ol\' red ones chicken jockey flint and steel ender pearl'.split()
    return '\n'.join(
        [' '.join(
            [random.choice(words) for _ in range(10)]
        )
            for _ in range(4)
        ]
    )


@app.route('/generate', methods=['POST'])
def generate_endpoint():
    try:
        data = request.json

        # Validate request format
        if not data or 'user_id' not in data or 'emotions' not in data:
            return jsonify({"error": "Invalid request format"}), 400

        # Process request
        result = {
            "poem": generate_poem(data['emotions']),
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
    port = int(os.getenv("NPB_POETRY_API_PORT", 5001))
    app.run(host='0.0.0.0', port=port)

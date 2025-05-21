from flask import Flask, request, jsonify
from datetime import datetime
import os
from dotenv import load_dotenv
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch.nn.functional as F


app = Flask(__name__)

# Загрузка модели один раз при старте сервера
MODEL_PATH = "rubert_emotion_cedr_neutral"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH).to(DEVICE)
model.eval()

EMOTION_LABELS = ['joy', 'sadness', 'surprise', 'fear', 'anger', 'neutral']


def analyze_text(text: str) -> dict:
    """Returns emotion scores"""
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True).to(DEVICE)
    with torch.no_grad():
        outputs = model(**inputs)
        probs = F.softmax(outputs.logits, dim=1).squeeze().cpu().numpy()

    return {label: round(float(prob), 4) for label, prob in zip(EMOTION_LABELS, probs)}


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
            "timestamp": datetime.utcnow().isoformat(),
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
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0"
    }), 200


if __name__ == '__main__':
    load_dotenv()
    port = int(os.getenv("NPB_EMOTION_API_PORT", 5000))
    app.run(host='0.0.0.0', port=port)
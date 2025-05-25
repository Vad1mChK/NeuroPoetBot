from flask import Flask, request, jsonify
from datetime import datetime, UTC
import random
import os
from dotenv import load_dotenv
from src.inference.emotion_poetry_generator import EmotionPoetryGenerator, GenerationStrategy
from src.inference.postprocessing import RhymeScheme

app = Flask(__name__)
generator = EmotionPoetryGenerator()

def generate_poem(
        emotions: dict[str, float],
        rhyme_scheme: RhymeScheme = RhymeScheme.ABBA,
        gen_strategy: GenerationStrategy = GenerationStrategy.RUGPT3
) -> dict[str, str]:
    global generator

    emotions.setdefault("no_emotion", emotions.get("neutral", 0.0))
    emotions.pop('neutral', None)

    return generator.generate_poem(
        emotion_dict=emotions,
        rhyme_scheme=rhyme_scheme,
        gen_strategy=gen_strategy,
        do_rhyme_substitution=(gen_strategy == GenerationStrategy.RUGPT3),
    )


@app.route('/generate', methods=['POST'])
def generate_endpoint():
    try:
        data = request.json

        # Validate request format
        if not data or 'user_id' not in data or 'emotions' not in data:
            return jsonify({"error": "Invalid request format"}), 400

        rhyme_scheme = random.choice([rs for rs in RhymeScheme])
        generation_result = generate_poem(
                data['emotions'],
                rhyme_scheme=rhyme_scheme,
                gen_strategy=GenerationStrategy.for_value(
                    data.get('gen_strategy', 'rugpt_3')
                ) or GenerationStrategy.RUGPT3,
            )

        is_postprocessed = bool(generation_result['poem'].strip())


        result = {
            "poem": (
                generation_result['poem']
                if is_postprocessed
                else generation_result["original_poem"]
            ),
            "rhyme_scheme": rhyme_scheme.value,
            "timestamp": datetime.now(UTC).isoformat(),
            "user_id": data['user_id'],
            "gen_strategy": data.get('gen_strategy', None),
            "genre": generation_result['genre'],
            "is_postprocessed": is_postprocessed,
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

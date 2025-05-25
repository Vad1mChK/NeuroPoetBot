EMOTION_TRANSLATIONS = {
    "happy": "радость",
    "joy": "радость",
    "sad": "грусть",
    "sadness": "грусть",
    "anger": "гнев",
    "disgust": "отвращение",
    "fear": "страх",
    "surprise": "удивление",
    "neutral": "нейтральная",
    "no_emotion": "нейтральная"
}


def translate_emotion(emotion):
    return EMOTION_TRANSLATIONS.get(emotion, emotion)


def top_emotions_translated(emotion_dict: dict[str, float], limit: int | None = None) -> list[str]:
    """
    Returns top emotions translated into Russian, formatted as "emotion (percentage%)".
    Sorted by descending percentage.
    If limit is provided, returns only the top N emotions.
    """
    sorted_emotions = sorted(
        emotion_dict.items(),
        key=lambda item: item[1],
        reverse=True
    )

    if limit is not None:
        sorted_emotions = sorted_emotions[:limit]

    return [
        f"{translate_emotion(emotion)} ({percentage * 100:.1f}%)"
        for emotion, percentage in sorted_emotions
    ]


if __name__ == "__main__":
    print(top_emotions_translated({
        "joy": 0.98,
        "fear": 0.01,
        "sadness": 0.01,
    }))
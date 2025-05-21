import json
import re
from transformers import pipeline
from tqdm import tqdm
from preprocessing_utils import (
    line_syllable_count,
    extract_rhyme_key,
    line_syllable_split,
    remove_accents
)

if __name__ == "__main__":
    emotion_classifier = pipeline(
        "text-classification",
        model="cointegrated/rubert-tiny2-cedr-emotion-detection",
        top_k=None,
        device=0  # GPU, use -1 for CPU
    )

    punctuation_pattern = re.compile(r'[.,!?\-—:;"«»\']+$')

    with open("../../data/rifma_dataset.json", "r", encoding="utf-8") as f:
        rifma_data = json.load(f)

    annotated_data = []

    for entry in tqdm(rifma_data):
        poem = entry["poem_text"]
        accented_poem = entry["accentuation_markup"]

        emotions = emotion_classifier(poem[:512])[0]
        emotion_dict = {emo['label']: emo['score'] for emo in emotions}

        lines = poem.strip().split('\n')
        accented_lines = accented_poem.strip().split('\n')

        line_annotations = []
        for line, accented_line in zip(lines, accented_lines):
            clean_line = punctuation_pattern.sub('', line.strip())
            clean_accented_line = punctuation_pattern.sub('', accented_line.strip())

            syllable_count = line_syllable_count(clean_line)
            rhyme_key = extract_rhyme_key(clean_accented_line)
            syllable_division = [syllable for word in line_syllable_split(clean_line) for syllable in word]

            line_annotations.append({
                "text": clean_line,
                "accented_text": clean_accented_line,
                "syllable_count": syllable_count,
                "rhyme_key": rhyme_key,
                "syllable_division": syllable_division
            })

        annotated_entry = {
            "poem_text": poem,
            "accentuation_markup": accented_poem,
            "rhyme_scheme": entry.get("rhyme_scheme", ""),
            "emotions": emotion_dict,
            "lines": line_annotations
        }

        annotated_data.append(annotated_entry)

    with open("../../data/rifma_annotated.json", "w", encoding="utf-8") as f:
        json.dump(annotated_data, f, ensure_ascii=False, indent=2)

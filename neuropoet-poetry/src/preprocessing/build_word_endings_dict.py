import json
import re
from collections import defaultdict
from tqdm import tqdm
from transformers import pipeline
from preprocessing_utils import (
    count_syllables,
    syllable_split,
    extract_rhyme_key
)
import pandas as pd

emotion_classifier = pipeline(
    "text-classification",
    model="cointegrated/rubert-tiny2-cedr-emotion-detection",
    top_k=None,
    device=0  # GPU, use -1 for CPU
)

with open("../../data/rifma_dataset.json", "r", encoding="utf-8") as f:
    rifma_data = json.load(f)

word_endings_dict = defaultdict(list)
word_regex = re.compile(r'\b[а-яА-ЯёЁ́̀]+\b')  # explicitly allow accented letters

unique_accented_words = set()

# Collect accented words explicitly from the original dataset
for poem in rifma_data:
    accented_lines = poem["accentuation_markup"].split("\n")
    for line in accented_lines:
        accented_words = word_regex.findall(line.lower())
        for word in accented_words:
            if re.search('[́̀]', word):  # only words with stress marks
                unique_accented_words.add(word)

# Explicitly add words from nouns_processed.csv
nouns_df = pd.read_csv("../../data/nouns_processed.csv")
for word in nouns_df['accented']:
    if isinstance(word, str) and re.search('[́̀]', word):
        unique_accented_words.add(word.lower())

print(f"Unique accented words collected: {len(unique_accented_words)}")

# word_amount = 50_000
# print(f"Truncating accented words to {word_amount}")
# unique_accented_words = list(unique_accented_words)[:word_amount]

for accented_word in tqdm(unique_accented_words):
    syllables = syllable_split(accented_word)
    syllable_count = count_syllables(accented_word)

    if syllable_count == 0 or not re.search(r'[аеёиоуыэюя]', accented_word):
        continue

    rhyme_key = extract_rhyme_key(accented_word)
    if not rhyme_key:
        continue

    # Predict emotions explicitly for the word (after accent removal)
    clean_word = accented_word.replace('́', '').replace('̀', '')
    emotions_output = emotion_classifier(clean_word)[0]
    emotions = {emo['label']: emo['score'] for emo in emotions_output}

    word_data = {
        "word": clean_word,
        "accented_word": accented_word,
        "syllable_count": syllable_count,
        "syllable_division": syllables,
        "rhyme_key": rhyme_key,
        "emotions": emotions
    }

    word_endings_dict[rhyme_key].append(word_data)

with open("../../data/word_endings_dict.json", "w", encoding="utf-8") as f:
    json.dump(word_endings_dict, f, ensure_ascii=False, indent=2)

print(f"Word endings dictionary saved with {len(word_endings_dict)} rhyme keys.")

import json
from tqdm import tqdm

from preprocessing.preprocessing_utils import emotion_dict_to_russian_str, get_genre_from_top_emotion

# Load annotated dataset
with open("../../data/rifma_annotated.json", "r", encoding="utf-8") as f:
    rifma_annotated = json.load(f)

training_samples = []

for poem_entry in tqdm(rifma_annotated):
    emotions = poem_entry['emotions']
    rhyme_scheme = poem_entry.get('rhyme_scheme', '')

    emotion_prompt = emotion_dict_to_russian_str(emotions)

    line_prompts = []
    for idx, line_info in enumerate(poem_entry['lines'], start=1):
        syllables = line_info['syllable_count']
        accented_line = line_info['accented_text']

        line_prompts.append(f"{idx}: {accented_line} [{syllables} слогов]")

    structured_prompt = (
            f"Эмоции: {emotion_prompt}\n"
            f"Рифма: {rhyme_scheme}\n"
            f"Жанр: {get_genre_from_top_emotion(emotion_dict=emotions)}"
            "\n[СТИХ]\n"
    )

    poem_text = "\n".join(
        f"{index}. " + line['text'] for index, line in enumerate(poem_entry['lines'], start=1)
    )

    training_sample = {
        "text": structured_prompt + poem_text
    }

    training_samples.append(training_sample)

# Save the structured examples
with open("../../data/processed_dataset.jsonl", "w", encoding="utf-8") as f:
    for sample in training_samples:
        f.write(json.dumps(sample, ensure_ascii=False) + "\n")

print(f"Processed {len(training_samples)} examples for GPT training.")
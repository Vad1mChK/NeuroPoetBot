# NeuroPoetBot, Poetry microservice
Generates a poem based on emotion inputs.

Expects an emotion dictionary (`dict[str, float]`) in the format:
```json
{
  "joy": 0.76,
  "sadness": 0.33,
  "anger": 0.09,
  "neutral": 0.01,
  "fear": 0.01,
  "surprise": 0.0
}
```

Returns a poem written using one of the rhyming schemes:
- `AABB`
- `ABAB`
- `ABBA`
- `AABA`

## General framework
### Training-time
1. Preprocesses the [RIFMA dataset](https://github.com/Koziev/Rifma/blob/main/rifma_dataset.json), annotating it with: emotion vectors, syllable division, and the rhyming ending. The original dataset already contains: the original texts, texts accented with stress marks, and rhyming schemes.
2. Generates a lookup dataset of all words from original poems or additional datasets that have stress markings.
3. Generates a `JSONL` dataset with original poems, formatted in the way the model is expected to generate new poems (the internal format, including line numbering)
4. Trains a `rugpt3-small` on the `JSONL` dataset and saves it locally.
### Invocation-time
1. Generates a poem using a finetuned `rugpt3-small`
2. Performs a naïve simplified post-processing, replacing trailing words to enforce rhymes
3. Formats and returns the generated poem

## Usage
## Training
1. Download the RIFMA dataset, and place it under `data/`. It should be named `rifma_dataset.json`.
3. Launch `src/preprocessing/annotate_emotions_and_syllables.py`
4. Launch `src/preprocessing/preprocess_additional_datasets.py`
3. Launch `src/preprocessing/build_word_endings_dict.py`
4. Launch `src/preprocessing/preprocess_for_gpt.py`
5. Launch `src/training/train.py`
6. The model should be saved under `models/rugpt3_finetuned/`

## Generating
Launch `main.py`. The generation should be accessible via web API (`POST /generate`)
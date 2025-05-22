import pandas as pd
import re
from stressrnn import StressRNN

COMBINING_ACUTE = '\u0301'

VOWELS = 'аеёиоуыэюя'
ACCENTED_VOWEL_PATTERN = re.compile(f"[{VOWELS}]{COMBINING_ACUTE}")
VOWEL_PATTERN = re.compile(f"[{VOWELS}]")
VALID_WORD_PATTERN = re.compile(fr"[А-Яа-яЁё{COMBINING_ACUTE}\-]+")

stress_rnn = StressRNN()

def replace_apostrophe_with_acute(word: str) -> str:
    return word.replace("'", COMBINING_ACUTE)

def accent_with_stress_rnn(word: str) -> str:
    accented_word = stress_rnn.put_stress(word).replace('+', COMBINING_ACUTE)
    return accented_word

def accent_single_vowel(word: str) -> str:
    if type(word) is not str:
        return None

    if ACCENTED_VOWEL_PATTERN.search(word):
        return word

    vowels = list(VOWEL_PATTERN.finditer(word))

    if len(vowels) == 1:
        idx = vowels[0].end()
        word = word[:idx] + COMBINING_ACUTE + word[idx:]
    else:
        word = accent_with_stress_rnn(word)

    return word

def is_valid_word(word: str) -> bool:
    if type(word) is not str:
        return False

    return (
        bool(VALID_WORD_PATTERN.fullmatch(word)) and
        bool(VOWEL_PATTERN.search(word)) and
        word.islower() and
        4 <= len(word.replace(COMBINING_ACUTE, '')) <= 16
    )

def preprocess_noun_dataset(input_csv: str, output_csv: str):
    df = pd.read_csv(input_csv, usecols=['accented', 'pl_nom'], sep="\t")

    words = set()
    for col in ['accented', 'pl_nom']:
        df[col] = df[col].dropna().apply(replace_apostrophe_with_acute)
        df[col] = df[col].apply(accent_single_vowel)
        valid_words = df[col].apply(is_valid_word)
        words.update(df[col][valid_words])

    result_df = pd.DataFrame({'accented': list(words)})
    result_df.to_csv(output_csv, index=False, encoding='utf-8')

# Explicit usage example:
if __name__ == "__main__":
    preprocess_noun_dataset('../../data/nouns.csv', '../../data/nouns_processed.csv')

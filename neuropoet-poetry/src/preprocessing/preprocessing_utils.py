import re
import string
import pyphen

pyphen_dic = pyphen.Pyphen(lang='ru')

VOWELS = "аеёиоуыэюя"
ACCENTED_VOWELS = "а́е́ё́и́о́у́ы́э́ю́я́а̀ѐё̀ѝо̀у̀ы̀э̀ю̀я̀"
STRESS_ACCENTS = '́̀'
OTHER_SUBSTITUTION_PATTERNS = {
    'ий': 'и',
    'ый': 'ы',
    'тс': 'ц',
    'тьс': 'ц',
    'ь': ''
}

# explicitly unify vowel variants for rhyming purposes
VOWEL_UNIFICATION = str.maketrans("яэыёю", "аеиоу")

EMOTION_TRANSLATIONS = {
    'anger': 'гнев',
    'disgust': 'отвращение',
    'fear': 'страх',
    'joy': 'радость',
    'sadness': 'грусть',
    'surprise': 'удивление',
    'neutral': 'нейтральная',
    'no_emotion': 'нейтральная'
}

GENRES = {

}


def impute_rhyme_scheme(rhyme_scheme: str) -> str | None:
    '''
    Attempts to find the largest existing letter in the rhyme_scheme,
    then imputes unfilled lines ("-") with newly generated letters.

    Examples:
    - "AA--"  → "AABC"
    - "A-A-A" → "ABACA"
    - "-A-A"  → "BACA"

    Returns None if it runs out of capital Latin letters.
    '''
    letters = list(string.ascii_uppercase)
    used_letters = set(filter(lambda c: c in letters, rhyme_scheme))

    if not letters:
        return None

    imputed_scheme = ""
    next_letter_index = 0

    for char in rhyme_scheme:
        if char == "-":
            while letters[next_letter_index] in used_letters:
                next_letter_index += 1
                if next_letter_index >= len(letters):
                    return None  # Ran out of letters

            new_letter = letters[next_letter_index]
            used_letters.add(new_letter)
            imputed_scheme += new_letter
        else:
            imputed_scheme += char

    return imputed_scheme


def stress_accents() -> str:
    return STRESS_ACCENTS


def remove_accents(text: str) -> str:
    """Remove stress accents from Russian text."""
    return text.translate(str.maketrans('', '', STRESS_ACCENTS))


def squash_duplicate_consonants(text: str) -> str:
    """Squash duplicate consonants into a single consonant."""
    return re.sub(r'([бвгджзйклмнпрстфхцчшщ])\1+', r'\1', text)


def unify_endings(text: str) -> str:
    """Apply specific ending substitutions for rhyme unification."""
    for original, replacement in OTHER_SUBSTITUTION_PATTERNS.items():
        text = text.replace(original, replacement)
    return text


def syllable_split(word: str) -> list[str]:
    """Splits a Russian word into syllables, correctly handling accented letters."""
    normalized_word = remove_accents(word.lower())
    syllables = pyphen_dic.inserted(normalized_word).split('-')
    return syllables


def count_syllables(word: str) -> int:
    """Counts syllables in a Russian word accurately."""
    return len(syllable_split(word))


def line_syllable_count(line: str) -> int:
    """Counts total syllables in a line."""
    words = re.findall(r'\w+', remove_accents(line.lower()))
    return sum(count_syllables(word) for word in words)


def line_syllable_split(line: str) -> list[list[str]]:
    """Returns syllable splits for each word in a line."""
    words = re.findall(r'\w+', line.lower())
    return [syllable_split(word) for word in words]


def extract_rhyme_key(accented_line: str, debug_log: bool = False) -> str:
    """Extracts rhyme key from the last accented vowel to the end of the last word."""
    # Remove punctuation first
    accented_line_clean = re.sub(fr'[^\w\s{STRESS_ACCENTS}]', '', accented_line.lower())
    if debug_log:
        print(f'accented_line_clean: {accented_line_clean}')

    vowels_pattern = f"[{VOWELS}][{''.join(STRESS_ACCENTS)}]"
    matches = list(re.finditer(vowels_pattern, accented_line_clean))
    if debug_log:
        print(f'vowel+accent matches: {[match.group() for match in matches]}')

    if not matches:
        return None

    last_stress_pos = matches[-1].start()

    # Extract from last stressed vowel to the end of the word
    post_stress_part = accented_line_clean[last_stress_pos:]
    rhyme_part = post_stress_part.split()[0]  # take the first word after the last match
    if debug_log:
        print(f'rhyme_part: {rhyme_part}')

    # Remove accents, unify vowels
    rhyme_part_clean = remove_accents(rhyme_part)
    rhyme_part_clean = squash_duplicate_consonants(rhyme_part_clean)
    rhyme_part_clean = unify_endings(rhyme_part_clean)
    rhyme_part_clean = rhyme_part_clean.translate(str.maketrans("яэыёю", "аеиоу"))
    if debug_log:
        print(f'rhyme_part_clean: {rhyme_part_clean}')

    return rhyme_part_clean.strip()


def emotion_dict_to_russian_str(
        emotions: dict[str, float],
        high_threshold: float | None = 0.2,
        low_threshold: float | None = 0.001,
        max_emotions: int | None = 3,
) -> str:
    sorted_emotions = sorted(emotions.items(), key=lambda item: item[1], reverse=True)

    if high_threshold is not None and any(score >= high_threshold for _, score in sorted_emotions):
        filtered_emotions = [(emo, score) for emo, score in sorted_emotions if score >= high_threshold]
    else:
        filtered_emotions = [(emo, score) for emo, score in sorted_emotions if score >= low_threshold]

    top_emotions = filtered_emotions[:max_emotions]

    return ', '.join(
        f"{EMOTION_TRANSLATIONS.get(emo, emo)} ({int(score * 100)}%)"
        for emo, score in top_emotions
    )

# Функция определения жанра по главной эмоции
def get_genre_from_top_emotion(emotion_dict):
    top_emotion = max(emotion_dict, key=emotion_dict.get)
    genre_mapping = {
        'joy': 'лирическая поэзия',
        'sadness': 'элегия',
        'anger': 'сатира',
        'fear': 'мистическая поэзия',
        'surprise': 'экспериментальная поэзия',
        'neutral': 'философская поэзия'
    }
    return genre_mapping.get(top_emotion, 'лирическая поэзия')


# Test your fixed implementation explicitly
if __name__ == '__main__':
    examples = [
        ("Зна́чит, ду́б выно́сливый,", "выносливый"),
        ("Идё́т девчо́нка по́ доро́ге", "дороге"),
        ("Твоё́ лицо́ гори́т огнё́м", "огнём"),
        ("Зовё́т меня́ в далё́кий кра́й", "край"),
        ("Сия́ет со́лнце за́ горо́й", "горой")
    ]

    for accented_line, original in examples:
        print(f"Original: {original}")
        print(f"Extracted rhyme key: {extract_rhyme_key(accented_line)}\n")

    example_emotion_dict = {
        "joy": 0.81,
        "no_emotion": 0.28,
        "anger": 0.01,
        "surprise": 0.01,
        "sadness": 0.00,
        "fear": 0.00,
    }
    print(f"Translated emotion_dict: {emotion_dict_to_russian_str(example_emotion_dict)}")

    example_rhyme_scheme = "A--B A--B"
    print(f"Imputed rhyme scheme for {example_rhyme_scheme}: {impute_rhyme_scheme(example_rhyme_scheme)}")


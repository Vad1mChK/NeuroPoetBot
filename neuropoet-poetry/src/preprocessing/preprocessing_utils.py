import re
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
}

# explicitly unify vowel variants for rhyming purposes
VOWEL_UNIFICATION = str.maketrans("яэыёю", "аеиоу")

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

import json
import re
import numpy as np
from enum import Enum
from preprocessing.preprocessing_utils import extract_rhyme_key, stress_accents, count_syllables
from stressrnn import StressRNN


import os
# Explicitly get project root from current file location
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../.."))


class RhymeScheme(Enum):
    ABAB = "ABAB"
    ABBA = "ABBA"
    AABB = "AABB"
    BACA = "BACA"


class PoemPostprocessor:
    def __init__(
            self,
            word_endings_dict_path = os.path.join(project_root, "data", "word_endings_dict.json"),
    ):
        with open(word_endings_dict_path, "r", encoding="utf-8") as f:
            self.word_endings_dict = json.load(f)
        self.stress_rnn = StressRNN()
        self.used_words = {}
        self.line_number_regex = re.compile(r"^\s*\d+\.\s*(.*)$")

    def retain_lines_with_numbers(self, lines: list[str]) -> list[str]:
        return [
            line
            for line in lines
            if re.match(pattern=self.line_number_regex, string=line)
        ]

    def strip_line_numbers(self, lines: list[str]) -> list[str]:

        return [
            re.sub(self.line_number_regex, r'\1', line).strip()
            for line in lines
        ]

    @staticmethod
    def remove_blank_lines(lines: list[str]) -> list[str]:
        blank_lines_regex = re.compile(r'^\s*$')  # Matches blank or whitespace-only lines explicitly
        return [
            line
            for line in lines
            if not blank_lines_regex.match(line)  # Explicitly keeps non-blank lines
        ]

    @staticmethod
    def _euclidean_distance(vec1: dict[str, float], vec2):
        emotions = ["anger", "no_emotion", "fear", "joy", "sadness", "surprise"]
        v1 = np.array([vec1.get(e, 0.0) for e in emotions])
        v2 = np.array([vec2.get(e, 0.0) for e in emotions])
        return np.linalg.norm(v1 - v2)

    def _accent_text(self, text: str) -> str:
        return self.stress_rnn.put_stress(text).replace('+', stress_accents()[0])

    def find_candidates(
            self,
            rhyme_key: str,
            words_to_exclude: list[str | None]
    ):
        candidates = self.word_endings_dict.get(rhyme_key, [])
        if not all(candidate["word"] in words_to_exclude for candidate in candidates):
            candidates = [
                candidate
                for candidate in self.word_endings_dict.get(rhyme_key, [])
                if (candidate["word"] not in words_to_exclude)
            ]
        return candidates

    def choose_word_top_p(self, candidates, target_emotion: dict[str, float], top_p=0.9):
        distances = np.array([self._euclidean_distance(w["emotions"], target_emotion) for w in candidates])
        probs = np.exp(-distances)
        probs /= probs.sum()

        sorted_indices = np.argsort(-probs)
        cumulative_probs = np.cumsum(probs[sorted_indices])
        top_indices = sorted_indices[cumulative_probs <= top_p]

        if len(top_indices) == 0:
            top_indices = [sorted_indices[0]]

        chosen_index = np.random.choice(top_indices)
        return candidates[chosen_index]["word"]

    def enforce_rhyme_scheme(self, poem_lines: list[str], rhyme_scheme: RhymeScheme, poem_emotion: dict[str, float]):
        scheme = rhyme_scheme.value
        corrected_lines = poem_lines.copy()

        lines_length = len(poem_lines)
        scheme_length = len(scheme)

        for i in range((lines_length + scheme_length - 1) // scheme_length):
            self.used_words.clear()

            rhyme_groups = {}
            for idx, letter in enumerate(scheme):
                idx_global = idx + i * scheme_length
                if idx_global < lines_length:
                    rhyme_groups.setdefault(letter, []).append(idx_global)
            # print(rhyme_groups)

            for letter, indices in rhyme_groups.items():
                ref_line_idx = indices[0]
                ref_line = poem_lines[ref_line_idx]
                ref_line_last_word = self.find_last_word(ref_line)
                rhyme_key = extract_rhyme_key(
                    self._accent_text(ref_line)
                )

                # print(f"ref_line: {ref_line}, last_word: {ref_line_last_word}, rhyme_key: {rhyme_key}")
                if not rhyme_key:
                    continue

                candidates = self.find_candidates(rhyme_key, words_to_exclude=[ref_line_last_word])

                # print(f"for rhyme_key: {rhyme_key}, candidates: {[candidate["word"] for candidate in candidates]}")
                if not candidates:
                    continue

                for idx in indices[1:]:
                    original_line = poem_lines[idx]
                    if extract_rhyme_key(original_line) == rhyme_key:
                        continue

                    chosen_word = self.choose_word_top_p(candidates, poem_emotion)

                    # Prevent repeated substitutions
                    attempts = 0
                    while (letter in self.used_words and chosen_word in self.used_words[letter]) and attempts < 5:
                        chosen_word = self.choose_word_top_p(candidates, poem_emotion)
                        attempts += 1

                    self.used_words.setdefault(letter, set()).add(chosen_word)
                    corrected_lines[idx] = self.replace_last_word(original_line, chosen_word)

        return corrected_lines

    @staticmethod
    def drop_last_short_line(lines: list[str], threshold: int = 5) -> list[str]:
        """Explicitly drops the last line if its syllable count is below the given threshold."""
        if lines:
            last_line_syllables = count_syllables(lines[-1])
            if last_line_syllables < threshold:
                return lines[:-1]
        return lines

    @staticmethod
    def split_long_lines(lines: list[str], max_syllables: int = 10) -> list[str]:
        """Explicitly splits lines exceeding max syllables at punctuation."""
        punctuation_pattern = re.compile(r'[,;:—–…]')
        new_lines = []

        for line in lines:
            if count_syllables(line) > max_syllables:
                parts = punctuation_pattern.split(line)
                punctuations = punctuation_pattern.findall(line)

                temp_line = ""
                temp_syllables = 0
                split_made = False

                for idx, part in enumerate(parts):
                    syllables = count_syllables(part.strip())
                    if temp_syllables + syllables <= max_syllables or not temp_line:
                        temp_line += part.strip()
                        if idx < len(punctuations):
                            temp_line += punctuations[idx] + " "
                        temp_syllables += syllables
                    else:
                        new_lines.append(temp_line.strip())
                        temp_line = part.strip()
                        if idx < len(punctuations):
                            temp_line += punctuations[idx] + " "
                        temp_syllables = syllables
                        split_made = True

                new_lines.append(temp_line.strip())

                if not split_made:  # explicitly ensures no empty additions
                    new_lines[-1] = line
            else:
                new_lines.append(line)

        return new_lines

    @staticmethod
    def replace_last_word(line: str, replacement: str) -> str:
        return re.sub(fr'\b[\w{stress_accents()}]+\b[^\w{stress_accents()}]*$', replacement, line)

    @staticmethod
    def find_last_word(line: str) -> str | None:
        match = re.search(fr'\b[\w{stress_accents()}]+\b[^\w{stress_accents()}]*$', line)
        if match is not None:
            return match.group()
        return None


# Example usage
if __name__ == "__main__":
    poem_lines = [
        "В небе голубом - свет небесный",  # Quatrain 1 start
        "Сияет над землёй и на дне земли",
        "И с высоты ввысь смотрит на небосклон",
        "Когда луна светит на востоке",
        "А за тем солнцем, как тень облаков",  # Quatrain 2 start
        "Летит, словно бы в ночи звёздной, звезда",
        "На землю опускается, будто не глядя вниз",
        "На луну летит она так нежно",
        "Словно плачет о чём-то своём",  # Quatrain 3 start
        "О любви, что была у неё всегда",
        "О том, что любовь дарила нам жизнь",
        "Что мы жили, любили, не зная слов",
        "Лишь миг разлуки длился бесконечно",
        "Что было в тот час, когда душа моя вновь вернулась"
    ]

    poem_emotion = {"joy": 0.98, "anger": 0.01, "sadness": 0.01}

    postprocessor = PoemPostprocessor()
    corrected_poem = postprocessor.enforce_rhyme_scheme(
        poem_lines, RhymeScheme.ABBA, poem_emotion
    )

    print("Corrected Poem:")
    for line in corrected_poem:
        print(line)

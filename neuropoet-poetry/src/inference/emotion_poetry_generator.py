from enum import Enum

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

from ..preprocessing.preprocessing_utils import emotion_dict_to_russian_str, get_genre_from_top_emotion
from .postprocessing import RhymeScheme, PoemPostprocessor
from .deepseek_api import generate_poem_with_deepseek

import os
# Explicitly get project root from current file location
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../.."))


class GenerationStrategy(Enum):
    RUGPT3 = "ru_gpt3"
    DEEPSEEK = "deepseek"

    @classmethod
    def for_value(cls, value) -> 'GenerationStrategy' or None:
        entries = [entry for entry in GenerationStrategy if entry.value == value]
        return entries[0] if len(entries) > 0 else None


class EmotionPoetryGenerator:
    def __init__(
            self,
            model_path = os.path.join(project_root, "models", "rugpt3_finetuned")
    ):
        base_model = "ai-forever/rugpt3small_based_on_gpt2"
        self.tokenizer = AutoTokenizer.from_pretrained(base_model)
        self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(base_model, device_map="auto")
        self.model = PeftModel.from_pretrained(self.model, model_path, device_map="auto")
        self.postprocessor = PoemPostprocessor()

    def generate_poem(
            self,
            emotion_dict: dict[str, float],
            rhyme_scheme: RhymeScheme = RhymeScheme.ABBA,
            do_postprocess: bool = True,
            do_rhyme_substitution: bool = True,
            gen_strategy: GenerationStrategy = GenerationStrategy.RUGPT3,
            max_length: int = 256
    ) -> dict[str, str] | None:
        generated_text: str
        emotions_text = emotion_dict_to_russian_str(emotion_dict)
        genre = get_genre_from_top_emotion(emotion_dict)

        match gen_strategy:
            case GenerationStrategy.RUGPT3:
                prompt = (
                    f"Эмоции: {emotions_text}\n"
                    f"Рифма: {rhyme_scheme.value}\n"
                    f"Жанр: {genre}"
                    "\n[СТИХ]\n"
                    "1. "
                )

                inputs = self.tokenizer(prompt, return_tensors="pt").to("cuda")

                output_ids = self.model.generate(
                    inputs["input_ids"],
                    attention_mask=inputs["attention_mask"],
                    max_length=max_length,
                    temperature=0.75,
                    top_k=50,
                    top_p=0.95,
                    repetition_penalty=1.2,
                    eos_token_id=self.tokenizer.eos_token_id,
                    pad_token_id=self.tokenizer.eos_token_id,
                    do_sample=True
                )

                generated_text = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)

            case GenerationStrategy.DEEPSEEK:
                generated_text = generate_poem_with_deepseek(
                    emotions=emotion_dict,
                    rhyme_scheme=rhyme_scheme,
                    genre=genre
                )
                if generated_text is None:
                    return None

            case _:
                return None

        poem = generated_text.split("[СТИХ]")[-1].strip()
        original_poem = generated_text
        if self.postprocessor is not None and do_postprocess:
            postprocessed_lines = poem.split("\n")
            postprocessed_lines = self.postprocessor.retain_lines_with_numbers(postprocessed_lines)
            postprocessed_lines = self.postprocessor.strip_line_numbers(postprocessed_lines)
            postprocessed_lines = self.postprocessor.remove_blank_lines(postprocessed_lines)
            if gen_strategy == GenerationStrategy.RUGPT3:
                postprocessed_lines = self.postprocessor.split_long_lines(postprocessed_lines)
            if do_rhyme_substitution:
                postprocessed_lines = self.postprocessor.enforce_rhyme_scheme(
                    postprocessed_lines,
                    rhyme_scheme=rhyme_scheme,
                    poem_emotion=emotion_dict
                )
            if gen_strategy == GenerationStrategy.RUGPT3:
                postprocessed_lines = self.postprocessor.drop_last_short_line(postprocessed_lines)
            poem = "\n".join(postprocessed_lines)

        return {
            "poem": poem,
            "original_poem": original_poem,
            "genre": genre
        }

# Example usage:
if __name__ == "__main__":
    generator = EmotionPoetryGenerator()

    emotion_input = {
        "anger": 0.21,
        "no_emotion": 0.01,
        "fear": 0.01,
        "joy": 0.70,
        "sadness": 0.01,
        "surprise": 0.11
    }

    poem = generator.generate_poem(
        emotion_input,
        rhyme_scheme=RhymeScheme.ABAB,
        # gen_strategy=GenerationStrategy.DEEPSEEK,
        # do_rhyme_substitution=False
    )
    print("Generated Poem:")
    print(poem)

import os
from dotenv import load_dotenv
import requests
import re
import json

from .postprocessing import RhymeScheme
from ..preprocessing.preprocessing_utils import emotion_dict_to_russian_str

load_dotenv()

prompt_format = """
Ты — креативный и талантливый русскоязычный поэт, способный генерировать эмоционально насыщенные, уникальные стихотворения высокого литературного качества. Твоя задача — создать стихотворение, строго соблюдая указанные требования и формат ответа. 

Обязательно следуй таким правилам при генерации ответа:
- Пиши только на русском языке.
- Избегай любых повторений слов и строк.
- Строго соблюдай заданную схему рифмовки (указанную в запросе), не отходи от неё.
- Строго выдерживай выбранный жанр (указанный в запросе).
- Используй богатый и выразительный русский язык, избегай смешения с другими языками.
- Максимально ясно выражай указанные эмоции и соблюдай указанные пропорции эмоций в тексте.
- Строго следуй формату ответа, представленному ниже.

Формат ответа:
```
Эмоции: {список эмоций на русском языке с процентами}
Рифма: {схема рифмовки, например ABAB, AABB, ABBA, указана в запросе}
Жанр: {жанр, указанный в запросе}
[СТИХ] {слово СТИХ должно оставаться без изменений}
1. Первая строка стихотворения
2. Вторая строка стихотворения
(продолжай нумерацию строк стихотворения последовательно)
```

Запрос:
```
Эмоции: <EMOTIONS>
Рифма: <RHYME_SCHEME>
Жанр: <GENRE>
```
Твой ответ должен выглядеть именно так, замени текст стихотворения на своё уникальное произведение.
Стихотворение должно содержать <LINE_COUNT> строк.
Ответ должен быть без \\boxed{}
"""
BOXED_REGEX = re.compile(r'\\boxed\{((?:.|\n)*)}')


def generate_poem_with_deepseek(
        emotions: dict[str, float],
        rhyme_scheme: RhymeScheme,
        genre: str = "произвольный",
        line_count: int | None = None,
):
    prompt = (
        prompt_format
        .replace('<EMOTIONS>', emotion_dict_to_russian_str(emotions))
        .replace('<RHYME_SCHEME>', rhyme_scheme.value)
        .replace('<GENRE>', genre)
        .replace('<LINE_COUNT>', str(line_count or len(genre)))
    )
    request = {
        "model": "deepseek/deepseek-r1-0528:free",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],

    }
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.getenv('DEEPSEEK_API_KEY')}",
            "Content-Type": "application/json",
            # "HTTP-Referer": "<YOUR_SITE_URL>",  # Optional. Site URL for rankings on openrouter.ai.
            # "X-Title": "<YOUR_SITE_NAME>",  # Optional. Site title for rankings on openrouter.ai.
        },
        data=json.dumps(request),
        timeout=int(os.getenv("DEEPSEEK_API_TIMEOUT", "30")),
    )
    if not response.ok:
        print(f"Ошибка API: {response.status_code} - {response.text}")
        return None

    response_data = response.json()
    choices = response_data.get('choices', [])
    if not choices:
        print("Нет вариантов ответа.")
        return None

    response_content = choices[0].get('message', {}).get('content', None)
    if not response_content:
        print("Пустой ответ модели.")
        return None

    return re.sub(
        pattern=BOXED_REGEX,
        repl=r'\1',
        string=response_content
    )


if __name__ == "__main__":
    poem = generate_poem_with_deepseek(
        emotions={'joy': 0.9, 'fear': 0.07, 'sad': 0.03},
        rhyme_scheme=RhymeScheme.ABBA,
        line_count=12
    )
    print(poem)

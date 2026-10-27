# 18. Разбор креаторов

> EN: Creator breakdowns from Civitai generation metadata: Sleeps_In_Sunbeams — one-line prompts plus a stack of 3–6 style LoRAs on Krea 2 Turbo, 8–15 steps, cfg 1; file list with triggers; how to rebuild the stack.

Разбираем работы авторов с узнаваемым почерком: модель, стек LoRA, настройки. Потом переносим рецепт в свой workflow.

- Почерк многих авторов — короткий промпт и стек из 3–6 стилевых LoRA.
- Метаданные Civitai показывают модель, LoRA и шаги, но силы LoRA часто скрыты — их подбирают перебором.
- Чужие картинки не копируем: ссылка на оригинал, рядом наш результат.

## Как мы разбираем авторов

У каждой картинки на Civitai есть данные генерации: модель, LoRA, число шагов, иногда промпт и весь граф ComfyUI. Мы читаем только эти данные, сами картинки не копируем: это чужая работа, ссылки ведут на оригинал. Дальше выделяем почерк автора, собираем список файлов, переносим рецепт в наш стиль workflow и показываем, что получилось у нас.

## Sleeps_In_Sunbeams

[Профиль на Civitai](https://civitai.com/user/Sleeps_In_Sunbeams). За сентябрь–октябрь 2026 — 200 работ: 122 в OpenAI (gpt-image), 69 на **Krea 2 Turbo** (нашей модели), остальное Krea 2 и Flux. Самые любимые зрителями: сова в ночи (2,2 тыс.), «Reflections of riding the wave» (1,5 тыс.), девушка-киборг (1,2 тыс.).

- **Почерк: короткий промпт + стек стилевых LoRA.** Промпт — одна строка настроения («Reflections of riding the wave») или вовсе не опубликован. Внешний вид делают 3–6 LoRA на Krea 2 Turbo, 8–15 шагов, cfg 1.

- **Любимая семья LoRA:** KreaFactory, KreaPhotoArt, KreaIllustrator, KreaLand, KreaWetbrush — один автор, общий триггер `Bradhamel art style`. Плюс плёнка **Ektachrome Fade Film**, **Detailer – beauty** для лиц и живописные LoRA (Impasto, NeoObscura, Eldritch).

- **Силы LoRA он не публикует.** Их придётся подбирать перебором. Для стека из 3 LoRA стартуем с 0,6 у каждой, для 5–6 — с 0,4–0,5.

| Работа | Модель · шаги | Стек LoRA | Промпт |
|---|---|---|---|
| [Девушка-киборг](https://civitai.com/images/146130242) | Krea 2 Turbo · 8 · 1248×1872 | ta86_inkriot · Ektachrome Fade Film · NIJISIS | не опубликован |
| [Сова](https://civitai.com/images/145610283) | Krea 2 Turbo · 8 | KreaFactory · Detailer beauty · Ektachrome · TextFusion | одно предложение-сцена |
| [Волна](https://civitai.com/images/145013337) | Krea 2 Turbo · 10 | KreaIllustrator · Impasto · NeoObscura · KreaPhotoArt | «Reflections of riding the wave» |
| [145817419](https://civitai.com/images/145817419) | Krea 2 Turbo · 10 | KreaFactory · Detailer beauty · Ektachrome · Eldritch · TextFusion | не опубликован |
| [146024108](https://civitai.com/images/146024108) | Krea 2 Turbo · 15 | KreaWetbrush · KreaPhotoArt · V67 Bas-reliefs | не опубликован |
| [102502031](https://civitai.com/images/102502031) (2025) | Juggernaut XL Ragnarok (SDXL) · апскейл до 2560×3712 | Detail Tweaker XL · эмбеддинги · апскейлер Remacri | не опубликован |

### Файлы для загрузки

| LoRA (Krea 2) | Размер | Триггер |
|---|---|---|
| [ta86_inkriot](https://civitai.com/models/2827717?modelVersionId=3190465) — чернильные контуры, cel-shading | 218 МБ | `ta86_inkriot, graphic cel shading, bold black outlines` |
| [Ektachrome Fade Film](https://civitai.com/models/2904145?modelVersionId=3284125) — выцветшая плёнка | 218 МБ | `ektachrome fade film` |
| [NIJISIS](https://civitai.com/models/2863875?modelVersionId=3302337) | 436 МБ | `@NIJISIS` |
| [KreaFactory](https://civitai.com/models/2765417?modelVersionId=3112670) | 218 МБ | `Bradhamel art style` |
| [KreaPhotoArt](https://civitai.com/models/2877293?modelVersionId=3284663) | 218 МБ | `Bradhamel art style` |
| [KreaIllustrator](https://civitai.com/models/2759107?modelVersionId=3104877) | 218 МБ | `Bradhamel art style` |
| [Detailer – beauty for Krea2](https://civitai.com/models/2790112?modelVersionId=3144156) | 109 МБ | — |
| [Impasto Painting](https://civitai.com/models/2834955?modelVersionId=3199393) · [NeoObscura](https://civitai.com/models/2861285?modelVersionId=3232205) · [Eldritch Digital Painting](https://civitai.com/models/2955749?modelVersionId=3348066) | 126–327 МБ | NeoObscura: `illustration Image, Poster` · Eldritch: `Digital Painting` |

### Как сделать у нас

- **База:** Krea 2 Turbo int8, как в `01b`: 8–10 шагов, euler/simple, cfg 1, размер 1248×1872 (2:3).

- **Стек LoRA:** цепочка `LoraLoaderModelOnly`, у каждой своя ручка силы. Старт 0,6 / 0,6 / 0,6 для трёх LoRA, затем перебор ±0,2 на главной стилевой.

- **Промпт:** триггеры в начале, дальше одна-две строки сцены. Длинные описания этому стилю не нужны.

- **Workflow:** отдельного файла нет — цепочка LoRA ставится в граф `01b`; готовые графы со стеками LoRA лежат на страницах [«Повтор трендов»](ch-trends.html).

### Что получилось у нас

Без LoRA автора Krea 2 уже близко повторяет стиль «девушки-киборга» — см. [«Сравнение моделей»](ch-scout.html#sc-art). Этим же методом в серии 8 разобраны и повторены шесть постов других авторов — [«Повтор трендов»](ch-trends.html).

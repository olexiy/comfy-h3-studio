# 6. Промпты

> EN: Copy-paste prompt templates: H3 timed shot-list with appearance/background locks, tag-style and prose-style still prompts; slot for the prompt-engineering lab (series 7, running).

Рабочие шаблоны промптов для кадра и для видео. Скопируйте, замените субъект и сцену.

- Для видео — раскадровка по секундам и строки-«замки» внешности и фона.
- Для картинок теги работают не хуже прозы; важна конкретика: 3–5 предметов в сцене, свет, ракурс.
- Возраст и черты лица пишите явно: модели молодят лица по умолчанию.

## Как устроен хороший промпт

- **Для кадра:** кто (возраст, лицо, волосы, телосложение) → что делает (поза, руки) → во что одет (по предметам) → где (3–5 конкретных предметов фона) → свет → камера и фактура. Современные энкодеры понимают и теги, и прозу ([почему](ch-theory.html#th-text)).

- **Для видео:** раскадровка по секундам, одно действие на 1,5–2,5 с, в каждой строке — какая рука и где предмет; строки-«замки» внешности, фона и света; звук отдельной строкой; никаких слов настроения (warm, cosy) — от них уплывает цвет.

- **Для постоянного персонажа:** «слой личности» (короткое неизменное описание) + «слой кадра» (переписывается целиком). Промпты ничего не помнят: «снова», «та же» не работают.

- **У турбо-моделей negative prompt не действует** (cfg 1): всё нужное пишите в позитив ([почему](ch-theory.html#th-cfg)).

## Шаблоны промптов

### Видео: раскадровка на 5 секунд (победитель V13)

```
integrated_multimodal_description: [Shot 1] <Picture 1> is the first frame. Whole clip is 5 seconds. Live-action. Static medium shot of a fictional 28-year-old woman sitting on a black metal mesh bench inside a glass bus shelter in daylight.
Appearance lock: long wavy copper-red hair, freckles, mature adult face, light everyday makeup, untucked white linen blouse with rolled sleeves, dark-blue high-waisted jeans, small silver pendant, silver hoop earrings, black bag on the bench. Keep face, outfit and proportions exactly as in <Picture 1>.
Background lock: red brick shop with striped awning, yellow curb, glass shelter panels with soft reflections; background stays still apart from natural light flicker.
[Shot 2] 0s-2.5s: she lifts her right hand and tucks a strand of hair behind her ear, then smiles warmly at the camera; small natural breathing and blinking.
[Shot 3] 2.5s-5s: she glances briefly to her left toward the street, looks back at the camera and gives a small playful wink, then relaxes, hands return to her lap and she keeps smiling softly.
camera: handheld phone feel, almost static, very slight natural sway, no zoom, no cuts.
overall_soundscape: quiet city street ambience, distant traffic, a soft breeze, faint footsteps on the pavement.
non_diegetic_music: None.
negative: morphing face, identity drift, extra fingers, warped hands, flicker, jitter, text, subtitles, watermark, music, talking.
```

### Картинка: структура в тегах

```
crisp detailed instagram photograph of
masterpiece, best quality, realistic, photorealistic, photo \(medium\),
[age]-year-old adult woman, [face], [hair], [build],
[pose and hands], [clothing],
[location: 3–5 concrete objects], [light], [camera angle], bokeh, depth of field
```

### Картинка: структура прозой (как у автора образца)

```
Amateur smartphone photo of a fictional [age]-year-old adult woman, late-20s, mature facial features,
[face: eyes, nose, lips, freckles, uneven skin tone, faint visible veins],
[hair], [build], [pose and action], [clothing item by item],
[location with 3–5 concrete background objects],
[light: harsh side light with deep shadows on the far side],
slight phone-camera noise, natural skin texture, unretouched.
```

## Лаборатория промптов (серия 7)

идёт Серия 7 проверяет на одних и тех же сценах: теги или проза, короткий или длинный промпт, как задавать возраст, сколько действий выдерживает раскадровка видео. Результаты появятся здесь, а шаблоны выше обновятся по её итогам.

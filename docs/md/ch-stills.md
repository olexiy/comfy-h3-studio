# 5. Кадр: фото на Krea 2

> EN: Photoreal stills on Krea 2 Turbo: simple one-pass vs the two-pass author recipe vs MOSS, fixing the 'AI face' (realism LoRA 0.5, upscale denoise 0.22, mature-feature words), strong body words at cfg 1.

Первый кадр решает больше половины качества видео. Здесь сравнение моделей для фото и приёмы, которые сработали на практике.

- Самый натуральный кадр — один проход Krea 2 за 13–32 с; сложный рецепт добавляет детали, но и глянец.
- «ИИ-лицо» лечится слабее LoRA реализма (0,5 вместо 0,7) и словами о зрелых чертах и неровной коже.
- Krea 2 Turbo работает с cfg 1 и не слышит мягких слов: формулировка должна быть сильной и конкретной.

## Картинки: Krea 2 против MOSS

![Один промпт: Krea простой, Krea рецепт автора, MOSS](media/h3-stills-t1-krea-a-b-moss.jpg)

**Один промпт, один сид.** Слева Krea простой (один проход, 13–32 с): самый натуральный. В центре рецепт автора (два прохода, детейлер, апскейл, 97 с): больше деталей, но «инстаграмный» глянец от LoRA. Справа MOSS (57–81 с): насыщенный стилизованный вид.

![Первый кадр для видео: Krea B, Krea B оптимизированный, MOSS](media/h3-stills-t4-krea-b-opt-moss.jpg)

**Первый кадр для видео.** Krea B → Krea B оптимизированный (живее кожа и веснушки) → MOSS (потеряла стеклянную остановку из промпта).

![Лицо до и после оптимизации](media/face-fix-u1-u2.jpg)

**Как убрать «ИИшное» лицо.** Слева исходный рецепт, справа оптимизированный: Realism Engine 0.7 → 0.5, denoise апскейла 0.1 → 0.22, в промпте «late-20s, mature facial features, uneven skin tone, harsh side light». Веснушки разной плотности, нормальные ресницы, видны поры.

## Фигура: как получить нужные пропорции

![Кадр для видео: пышная фигура, серая майка, медитация в гостиной](media/body-wording-best.jpg)

кадр для видео**M6 · seed 7** · оптимизированный `01` · 896×1120 → 1344×1680 · 65 с.

![Слева кадр с мягкими словами о фигуре, справа три сида с сильными словами](media/body-wording-before-after.jpg)

**Слева:** «voluptuous, large full breasts, curvy hourglass», фигура осталась спортивной. **Справа три сида:** «slightly chubby body, curvy, thick, huge breasts, sagging breasts, wide hips, big round butt, thick thighs». Workflow и настройки одинаковые, изменились только слова.

- **Krea 2 Turbo слушает только сильные слова о теле.** Модель дистиллирована и работает с cfg 1, поэтому мягкие «large / full / curvy hourglass» почти ничего не меняют. Проверено на 8 кадрах в `01` и `01b`, плюс прозой и тегами. А «slightly chubby body, huge breasts, sagging breasts» срабатывает с первого сида.

- **Сцена тянет фигуру к своему стереотипу.** Йога и медитация дают «спортивное» тело, если не перебить это словами о теле. Сложенные у груди ладони вдобавок прячут силуэт. Работает, если описать связь тела и позы: «her breasts rest on top of her forearms».

- **Одежда:** облегающая майка с вырезом показывает форму. Против просвечивания пишите «thick opaque fabric».

- **Для видео** те же слова о фигуре повторяются в appearance lock раскадровки, иначе H3 начинает «стройнить» тело к концу клипа.

### Картинка: пышная фигура (теги, workflow 01)

```
crisp detailed instagram photograph of
masterpiece, best quality, realistic, photorealistic, photo \(medium\), instagram model, fictional 28-year-old adult woman, mature facial features, narrow face, pouty lips, sleek pulled back ponytail, 1girl, slightly chubby body, curvy, thick, blonde hair, huge breasts, sagging breasts, wide hips, big round butt, thick thighs, eyes closed, calm meditation, hands praying in front of her, her breasts rest on top of her forearms.
indoors, kneeling, living room, couch, floor, yoga mat, light fitted heather-grey cotton tank top, thick opaque fabric, scoop neckline, cleavage, black athletic leggings, straight on, bokeh, depth of field
```

# YouTube-обложки — основной визуальный референс

> Статус: утверждённый референс  
> Дата фиксации: 2026-07-24  
> Проект: @infobiz  
> Готовый вариант: [youtube-thumbnail-budget-reference.png](youtube-thumbnail-budget-reference.png)

## Что сохранять во всех следующих обложках

- Формат: YouTube thumbnail, 16:9.
- Композиция: крупный заголовок занимает левые 55–60%; Володя — правая треть кадра.
- Персонаж: узнаваемое лицо Володи, взгляд в камеру, уверенная спокойная эмоция, чёрная одежда, контрастный контровой свет.
- Фон: глубокий тёмно-фиолетовый `#2B223A`.
- Акцент: янтарно-жёлтый `#FFBA24`.
- Свет: cinematic high-contrast, тёплое жёлтое свечение за героем, глубокие тени.
- Типографика: очень крупный жирный гротеск, тёплый белый + жёлтое выделение ключевых слов, лёгкая тёмная тень.
- Объекты: 3D-символы темы выпуска располагаются вокруг героя справа и не спорят с заголовком.
- Настроение: современный financial-tech / business, дорого, резко, без визуального мусора.

## Инварианты

- Не менять лицо на похожего вымышленного человека.
- Не добавлять ребёнка из исходного портрета.
- Не ставить мелкий текст.
- Не использовать больше 2 основных цветов кроме оттенков фона и кожи.
- Не заводить декоративные элементы под заголовок.
- Не добавлять логотипы, водяные знаки и лишние подписи.
- Проверять русскую орфографию и точное воспроизведение заголовка.

## Базовый промпт

```text
Use case: identity-preserve
Asset type: final YouTube thumbnail, exact 16:9 landscape

Input images:
- Image 1: approved thumbnail reference for composition, palette, lighting and typography.
- Image 2: identity reference for the adult man only.

Primary request:
Create a new YouTube thumbnail in the exact visual system of Image 1. Preserve the recognizable facial identity of the adult man from Image 2 very closely: same facial structure, short dark hair, light mustache/stubble, eyes, nose, jaw and natural age. Do not include the child. Place the man on the RIGHT third, looking at camera, with a confident restrained expression. Keep black clothing and cinematic studio lighting.

Headline on the LEFT, exactly:
«{{ЗАГОЛОВОК}}»

Typography:
Very large heavy modern sans-serif Cyrillic, thumbnail-readable. Warm white with the key words {{КЛЮЧЕВЫЕ СЛОВА}} highlighted in amber yellow #FFBA24. Strong clean contrast, subtle dark shadow, generous margins.

Scene and supporting objects:
Deep-purple background #2B223A. Add a soft amber radial glow behind the subject. Place a small set of photorealistic 3D objects related to {{ТЕМА ВЫПУСКА}} strictly around and behind the man in the rightmost 40%. Keep the left 55–60% clean for the headline.

Style:
Cinematic high-contrast advertising photography, premium 3D compositing, bold modern business/financial-tech mood, sharp studio key light, dramatic amber rim light, shallow depth of field, ultra-sharp subject.

Constraints:
Exact 16:9. Preserve adult identity faithfully. One adult only. Exclude the child completely. Accurate face and hands. Exact Russian headline only. No extra words, letters, logos, watermark or captions. Do not place objects behind or across the headline.
```

## Переменные для нового выпуска

1. `{{ЗАГОЛОВОК}}` — финальный текст с нужным переносом строк.
2. `{{КЛЮЧЕВЫЕ СЛОВА}}` — 1–3 слова, которые выделяем жёлтым.
3. `{{ТЕМА ВЫПУСКА}}` — предметная метафора для 3D-объектов.
4. Эмоция героя — по умолчанию спокойная уверенность; менять только под смысл выпуска.

## Эталон этого варианта

- Заголовок: «Сколько нужно тратить денег на рекламу?»
- Жёлтые слова: «тратить», «рекламу?»
- 3D-объекты: монеты ₽, калькулятор, деньги → воронка → клиенты, растущий график.
- Исходное изображение личности: `C:\Users\User\Desktop\IMG_0165.jpg`.


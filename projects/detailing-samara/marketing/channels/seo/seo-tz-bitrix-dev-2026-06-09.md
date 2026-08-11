# ТЗ Битрикс-разработчику: техническое SEO

**Дата:** 2026-06-09
**Сайт:** levsha-group.ru (1С-Битрикс)
**Объём:** только техническая часть (шаблоны, schema, скорость, мета-инфраструктура). Тексты и контент — отдельно, не входит.

> Задача: устранить технические SEO-дыры. Весь нужный код — внутри этого документа. Где стоит `<...>` — подставить реальное значение.

---

## 1. JSON-LD разметка (сейчас на сайте 0 schema)

Вставлять в `<head>` соответствующих типов страниц.

### 1.1. Главная + страница контактов — `WebSite` и `AutomotiveBusiness`

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Детейлинг-центр «Левша»",
  "url": "https://levsha-group.ru/"
}
</script>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "AutomotiveBusiness",
  "name": "Детейлинг-центр «Левша»",
  "image": "https://levsha-group.ru/<фото-студии>",
  "url": "https://levsha-group.ru/",
  "telephone": "+7-846-211-63-11",
  "email": "info@levsha163.ru",
  "priceRange": "₽₽",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "ул. Ново-Садовая, 162Б",
    "addressLocality": "Самара",
    "addressRegion": "Самарская область",
    "postalCode": "<индекс>",
    "addressCountry": "RU"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": "<широта из Я.Карт>",
    "longitude": "<долгота из Я.Карт>"
  },
  "openingHoursSpecification": [
    {"@type":"OpeningHoursSpecification","dayOfWeek":["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],"opens":"<чч:мм>","closes":"<чч:мм>"}
  ],
  "sameAs": [
    "https://vk.com/levshapro",
    "https://t.me/levshasamara",
    "<карточка Яндекс.Карт>",
    "<карточка 2ГИС>"
  ]
}
</script>
```

### 1.2. Страницы статей — `Article` + `BreadcrumbList`
Поля `headline`, `image`, `datePublished/dateModified`, крошки — подставлять из свойств страницы (динамически из инфоблока).

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "<заголовок статьи>",
  "author": {"@type": "Organization", "name": "Детейлинг-центр «Левша»"},
  "publisher": {
    "@type": "Organization",
    "name": "Левша",
    "logo": {"@type": "ImageObject", "url": "https://levsha-group.ru/<лого>"}
  },
  "datePublished": "<YYYY-MM-DD>",
  "dateModified": "<YYYY-MM-DD>",
  "image": "<URL обложки>",
  "mainEntityOfPage": "<URL страницы>"
}
</script>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {"@type":"ListItem","position":1,"name":"Главная","item":"https://levsha-group.ru/"},
    {"@type":"ListItem","position":2,"name":"<раздел>","item":"<URL раздела>"},
    {"@type":"ListItem","position":3,"name":"<страница>","item":"<URL страницы>"}
  ]
}
</script>
```

`BreadcrumbList` — генерировать сайтово на всех внутренних страницах из текущей навигации.

---

## 2. Canonical (сейчас отсутствует)
На всех типах страниц — самоссылающийся canonical:
```html
<link rel="canonical" href="<абсолютный URL текущей страницы без GET-параметров>">
```

---

## 3. Мета-инфраструктура (правит контент-менеджер, но включает разработчик)
- Убедиться, что `title` и `meta description` **редактируются на каждую страницу/раздел** (SEO-свойства инфоблоков: `SEO_TITLE`, `SEO_DESCRIPTION` / шаблоны мета у инфоблока).
- **Убрать дефолт-заглушку** `meta description = "Корпоративный сайт"` — она сейчас подставляется глобально. Сделать, чтобы при пустом поле description не выводился вообще (а не заглушка).
- H1 главной сейчас захардкожен как «Записывайтесь» — вынести в редактируемое поле или поправить в шаблоне (текст даст контент). H1 должен быть один на странице.

---

## 4. Скорость / Core Web Vitals
HTML главной ~427 КБ — тяжёлая. Цель — зелёные LCP/INP/CLS в Яндекс.Вебмастер и PageSpeed Insights.
- Включить **композитный кэш** Битрикса (если не включён).
- Минификация и объединение CSS/JS, `defer/async` для несрочных скриптов.
- Отложенная загрузка (`loading="lazy"`) для несложных изображений ниже первого экрана.
- Проставить `width`/`height` на `<img>` (против скачков вёрстки, CLS).
- **WebP/AVIF** — сейчас 0 картинок в современных форматах; настроить конвертацию/отдачу (модуль или сервер).
- По возможности CDN для статики.
- После — прогнать PageSpeed Insights + Яндекс.Вебмастер, приложить замеры LCP/INP/CLS.

> ⚠️ Отдельно: оцените и напишите вердикт — **реально ли разогнать Битрикс до нормальных CWV на текущем шаблоне, или упираемся в потолок движка.** От этого зависит решение «остаёмся / переезжаем». Это ключевой пункт.

---

## 5. Robots / Sitemap
- `/sitemap.xml` отдаёт **404**, а в `robots.txt` заявлен `/sitemap-files.xml` (200) и работает `/sitemap_index.xml`. Привести к одному: либо отдавать `/sitemap.xml`, либо убрать ссылки на несуществующий. Карта должна быть актуальной и автообновляемой.
- В `robots.txt` строка `Disallow: /services/ukhod-za-salonom-avtomobilya/` закрывает услугу «химчистка салона» от индексации. **Уточнить у заказчика** — если услуга продаётся, открыть.

---

## 6. Прочее (low)
- Добавить `<meta name="twitter:card" content="summary_large_image">` (превью в соцсетях; og-теги уже есть).
- На главной ~478 ссылок (419 внутренних) — проверить меню/футер на дубли, по возможности сократить.

---

## Что НЕ входит в это ТЗ (отдельная задача)
- Перенос текста статей из картинок в HTML, написание мета-текстов, описаний услуг, «О нас» — это контент (копирайтер/контент-менеджер).
- Заведение и ведение Яндекс.Бизнес / 2ГИС, отзывы — маркетинг/SMM.

## Что прислать по итогу
1. Внедрённые schema (проверить в валидаторе Schema.org / Яндекс.Вебмастер).
2. Замеры скорости до/после (PageSpeed + Вебмастер).
3. Вердикт по п.4: разгоняется Битрикс до нормы или нет.

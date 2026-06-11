# 🚀 SMM Publish Skills

Автоматизована система публікації постів у соціальних мережах через інтеграцію з **n8n** та використанням Markdown-файлів як джерела контенту.

Проект розроблений для автоматизації роботи SMM-спеціалістів та ШІ-агентів, дозволяючи публікувати готові дописи в різні соцмережі за розкладом або за запитом.

---

## 🛠️ Архітектура та можливості

- **Формат постів**: Усі дописи зберігаються у вигляді стандартних Markdown-файлів із Frontmatter-метаданими та розділами для різних мереж.
- **Підтримувані соцмережі**: 
  - ✈️ Telegram (`tg`)
  - 📸 Instagram (`inst`)
  - 💼 LinkedIn (`ln`)
  - 👥 Facebook (`fb`)
  - 🧵 Threads (`th`)
  - 🏢 Google Business (`gb`)
- **Статуси дописів**: 
  - `draft` — чернетка допису
  - `ready` — готовий до публікації
  - `processing` — у процесі відправки (захист від дублювання)
  - `partial` — опубліковано частково (є помилки в окремих мережах)
  - `published` — успішно опубліковано у всіх вказаних мережах
- **Розумна обробка медіафайлів**: Передає локальні зображення (включаючи окремі для LinkedIn) у вигляді multipart/form-data.
- **Інтеграція з n8n**: Скрипт надсилає структурований JSON з контентом та файлами на вебхук n8n, отримує результати публікації для кожної мережі та оновлює статус файлу допису.

---

## 📁 Структура проекту

```text
├── .agents/
│   └── skills/
│       └── smm-publisher/
│           ├── SKILL.md                 # Інструкція для ШІ-агента з використання скіла
│           ├── scripts/
│           │   ├── smm_publish.py       # Головний Python-скрипт публікації
│           │   ├── requirements.txt     # Залежності скрипта
│           │   └── .env.example         # Приклад конфігураційного файлу
│           └── venv/                    # Віртуальне середовище Python (створюється під час інсталяції)
├── .env                                 # Локальні конфігурації (URL вебхука, папка постів тощо)
├── .gitignore                           # Виключення Git
├── n8n.json                             # Експорт сценарію/налаштувань n8n
├── приклад файлу з дописами.md          # Шаблон/приклад файлу допису
└── README.md                            # Цей файл
```

---

## ⚙️ Налаштування (Setup)

### 1. Підготовка Python середовища

Для роботи автопублікатора необхідно створити віртуальне середовище та встановити залежності:

```bash
# 1. Створення віртуального середовища
python3 -m venv .agents/skills/smm-publisher/venv

# 2. Активація та встановлення пакетів
.agents/skills/smm-publisher/venv/bin/pip install -r .agents/skills/smm-publisher/scripts/requirements.txt
```

### 2. Конфігурація середовища (`.env`)

Створіть файл `.env` в корені проекту та вкажіть ваші налаштування:

```env
# Шлях до папки, де зберігаються Markdown файли з дописами
POSTS_DIR="/Users/serhiy/Developer/SMM Post/parsing"

# URL вебхука n8n для прийому постів
N8N_WEBHOOK_URL="https://your-n8n-instance.com/webhook/smm-post-input"

# Кількість постів для обробки за один цикл запуску скрипта
BATCH_SIZE=1
```

---

## 📝 Формат файлу допису (Markdown)

Кожен допис має містити Frontmatter-метадані та розділений контент для кожної мережі за допомогою заголовків `## Content: <NETWORK>`.

### Приклад структури файлу:

```markdown
---
id: "unique_post_id_123"
status: ready
publish_date: "2026-06-11T12:00:00Z"
networks: tg, ln, fb
networks_success: []
networks_failed: []
media: file:///path/to/image.png
media_ln: file:///path/to/linkedin_special_image.png
source_url: https://example.com
---
# Метадані

**inputType**: RSS
**author**: Example Blog
**title**: Заголовок допису

# Контент

## Content: TG

Текст для Telegram каналу з #хештегами.

## Content: LN

Text formatted specifically for LinkedIn audience.

## Content: FB

Текст для сторінки Facebook.
```

---

## 🚀 Запуск публікації

Скрипт перевіряє файли у папці `POSTS_DIR`. Якщо дата `publish_date` наступила (або порожня) та статус є `ready` або `partial`, скрипт ініціює публікацію.

Запуск вручну:
```bash
.agents/skills/smm-publisher/venv/bin/python .agents/skills/smm-publisher/scripts/smm_publish.py
```

### Автоматизація за розкладом (Cron)
Для регулярної перевірки та публікації нових постів рекомендується налаштувати запуск скрипта через `cron` на сервері або через планувальник вашого ШІ-агента (наприклад, кожні 15 хвилин).

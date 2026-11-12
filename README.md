# ⭐ Хотєлочки — вішліст для рідних і друзів

Telegram Mini App, де рідні й друзі ведуть свої списки бажань і бачать списки одне одного. Вхід — лише за посиланням-запрошенням.

**Стек:** React + Vite + TypeScript · Python FastAPI + aiogram · PostgreSQL

## Документи
- [Бачення продукту](docs/vision.md)
- [Беклог](docs/backlog.md)
- [Правила роботи](CLAUDE.md)

## Запуск однією командою (Windows)
```powershell
powershell -ExecutionPolicy Bypass -File .\dev.ps1       # Docker, база, міграції, бекенд, фронт, тунель, бот
powershell -ExecutionPolicy Bypass -File .\dev-stop.ps1  # зупинити все, що запустив dev.ps1
```
Скрипт сам впише нову адресу тунелю в `WEBAPP_URL` у `backend/.env` перед стартом бота.
Після запуску надішли боту `/start` і відкрий застосунок **новою** кнопкою.

## Запуск локально
Потрібно: Git, Node.js 22, [uv](https://docs.astral.sh/uv/) (сам поставить Python 3.12), Docker Desktop.

1. Скопіюй `.env.example` у `backend/.env`, впиши `BOT_TOKEN` і `ADMIN_TELEGRAM_IDS=<твій id>`.
   Для перевірки в звичайному браузері (без Telegram) можна тимчасово ввімкнути `DEV_AUTH=true`
   і додати `1` (dev-користувач) в `ADMIN_TELEGRAM_IDS` — **але лише без тунелю**: через тунель
   це дало б будь-кому вхід адміном. `dev.ps1` відмовиться стартувати, якщо `DEV_AUTH` увімкнено.
2. База даних (PostgreSQL у Docker, доступна лише з цього комп'ютера):
   ```bash
   docker compose up -d db   # порт 5433 на localhost
   ```
3. Бекенд:
   ```bash
   cd backend
   uv sync
   uv run alembic upgrade head   # застосувати міграції
   uv run uvicorn app.main:app --reload
   ```
4. Фронтенд (в іншому терміналі):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
5. Відкрий http://localhost:5173

## Доступ
Адміністратор (`ADMIN_TELEGRAM_IDS`) має доступ завжди і бачить у застосунку розділ «Запросити» з посиланням `t.me/<бот>?start=<код>`.
Хто відкрив посилання — отримує доступ назавжди. Посилання можна перегенерувати: старе перестане працювати.

## Міграції
Після зміни моделей у `backend/app/models.py`:
```bash
cd backend
uv run alembic revision --autogenerate -m "short description"
uv run alembic upgrade head
```
У Docker міграції застосовуються автоматично при старті бекенду.

## Фото бажань
Завантажені фото зберігаються в `MEDIA_DIR` (локально — `backend/media/`, у Docker — том `media-data`).
Кожне фото перекодовується в JPEG до 1600 px, метадані (зокрема GPS) видаляються.

## Тести
Тести за замовчуванням працюють на SQLite у пам'яті; CI додатково ганяє їх на PostgreSQL.
```bash
cd backend && uv run pytest -q
cd frontend && npm run lint && npm run build
```

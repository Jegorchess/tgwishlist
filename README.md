# 🎁 Вішліст для рідних і друзів

Telegram Mini App, де рідні й друзі ведуть свої списки бажань і бачать списки одне одного. Вхід — лише за посиланням-запрошенням.

**Стек:** React + Vite + TypeScript · Python FastAPI + aiogram · PostgreSQL

## Документи
- [Бачення продукту](docs/vision.md)
- [Беклог](docs/backlog.md)
- [Правила роботи](CLAUDE.md)

## Запуск локально
Потрібно: Git, Node.js 22, [uv](https://docs.astral.sh/uv/) (сам поставить Python 3.12), Docker Desktop.

1. Скопіюй `.env.example` у `backend/.env`, впиши `BOT_TOKEN`, `DEV_AUTH=true` і `ADMIN_TELEGRAM_IDS=<твій id>,1`
   (`1` — це dev-користувач браузерного режиму; на сервері його не додавай).
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

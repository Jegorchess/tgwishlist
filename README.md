# 🎁 Сімейний вішліст

Telegram Mini App, де кожен член сім'ї веде свій список бажань, а рідні бачать списки одне одного.

**Стек:** React + Vite + TypeScript · Python FastAPI + aiogram · PostgreSQL

## Документи
- [Бачення продукту](docs/vision.md)
- [Беклог](docs/backlog.md)
- [Правила роботи](CLAUDE.md)

## Запуск локально
Потрібно: Git, Node.js 22, [uv](https://docs.astral.sh/uv/) (сам поставить Python 3.12), Docker Desktop.

1. Скопіюй `.env.example` у `backend/.env`, впиши `BOT_TOKEN` і `DEV_AUTH=true`.
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

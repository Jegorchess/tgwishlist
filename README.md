# 🎁 Сімейний вішліст

Telegram Mini App, де кожен член сім'ї веде свій список бажань, а рідні бачать списки одне одного.

**Стек:** React + Vite + TypeScript · Python FastAPI + aiogram · PostgreSQL

## Документи
- [Бачення продукту](docs/vision.md)
- [Беклог](docs/backlog.md)
- [Правила роботи](CLAUDE.md)

## Запуск локально
Потрібно: Git, Node.js 22, Python 3.12+, [uv](https://docs.astral.sh/uv/).

1. Скопіюй `.env.example` у `backend/.env`, впиши `BOT_TOKEN` і `DEV_AUTH=true`.
2. Бекенд:
   ```bash
   cd backend
   uv sync
   uv run uvicorn app.main:app --reload
   ```
3. Фронтенд (в іншому терміналі):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
4. Відкрий http://localhost:5173

## Тести
```bash
cd backend && uv run pytest -q
cd frontend && npm run lint && npm run build
```

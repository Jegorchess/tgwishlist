# 🎁 Сімейний вішліст — Telegram Mini App

Міні-застосунок у Telegram, де кожен член сім'ї веде свій список бажань, а рідні бачать списки одне одного.

- Продукт і бачення: [`docs/vision.md`](docs/vision.md)
- Беклог: [`docs/backlog.md`](docs/backlog.md)
- Правила для Claude і процес: [`CLAUDE.md`](CLAUDE.md)

## Стек
React + Vite + TypeScript · Python FastAPI + aiogram 3 · PostgreSQL · Docker Compose + Caddy

## Локальний запуск (VS Code)

Потрібно: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 22, Docker (опційно).

1. Створи бота в [@BotFather](https://t.me/BotFather) (`/newbot`) і скопіюй токен.
2. `cp .env.example backend/.env` і заповни `BOT_TOKEN`; для розробки в браузері — `DEV_AUTH=true`.
3. Бекенд:
   ```bash
   cd backend
   uv sync
   uv run uvicorn app.main:app --reload
   ```
4. Фронтенд (в іншому терміналі):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Відкрий http://localhost:5173 — побачиш «Привіт, Dev!».

### Перевірка всередині Telegram
Mini App вимагає HTTPS. Підніми тунель до фронтенду:
```bash
cloudflared tunnel --url http://localhost:5173
```
Пропиши отриманий `https://...trycloudflare.com` у `WEBAPP_URL` в `backend/.env`, запусти бота:
```bash
cd backend && uv run python -m app.bot.polling
```
і напиши боту `/start`.

## Тести та лінт
```bash
cd backend && uv run pytest -q && uv run ruff check .
cd frontend && npm run lint && npm run build
```

## Деплой на VPS
```bash
cp .env.example .env   # BOT_TOKEN, WEBAPP_URL=https://<домен>, SITE_ADDRESS=<домен>, POSTGRES_PASSWORD
docker compose up -d --build
```
DNS A-запис домену має вказувати на VPS; Caddy сам отримає HTTPS-сертифікат.

## Як ми працюємо
1. Єгор створює issue за шаблоном **User story** (з критеріями приймання).
2. Claude реалізує в гілці, проганяє тести й рев'ю (`code-reviewer`), відкриває PR.
3. Єгор перевіряє і мерджить.

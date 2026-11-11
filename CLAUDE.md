# CLAUDE.md

Вішліст для рідних і друзів — Telegram Mini App (без «сімей»: один спільний простір, вхід за посиланням-запрошенням). Продукт: `docs/vision.md`, беклог: `docs/backlog.md`.

## Ролі
- **Єгор** — Product Owner / аналітик: пише user stories з AC в GitHub Issues, приймає PR.
- **Claude** — розробник: реалізує issue, пише тести, відкриває PR.
- Субагенти (`.claude/agents/`): `code-reviewer` — рев'ю перед PR; `qa-tester` — перевірка AC.

## Процес
1. Береш issue → читаєш AC. Якщо AC неоднозначні — питаєш Єгора, не вигадуєш.
2. Реалізація + тести (бекенд — pytest обов'язково для кожного ендпоінта).
3. Перед PR — запусти субагента `code-reviewer`, для фіч з UI — `qa-tester`.
4. PR за шаблоном, з `Closes #N`. Комунікація з Єгором — українською; код, коміти, назви — англійською.

## Стек
- `backend/` — Python 3.12+, FastAPI, aiogram 3, pydantic-settings, uv. (Ітерація 1: SQLAlchemy 2 async + Alembic + PostgreSQL.)
- `frontend/` — React 18 + Vite + TypeScript, `telegram-web-app.js` (обгортка у `src/telegram.ts`).
- Деплой — `docker-compose.yml` + Caddy (`deploy/Caddyfile`) на VPS.

## Команди
```bash
cd backend && uv sync && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
cd backend && uv run uvicorn app.main:app --reload       # API на :8000
cd backend && uv run python -m app.bot.polling           # бот локально
cd frontend && npm install && npm run dev                 # :5173, проксі /api -> :8000
cd frontend && npm run lint && npm run build
docker compose up --build                                 # усе разом на :80
```

## Безпека (обов'язково)
- Кожен `/api/*` ендпоінт залежить від `CurrentInitData` (`app/auth/deps.py`) — підпис `initData` перевіряється на бекенді.
- Довіряти лише `telegram_id` з перевіреного `initData`; ніколи з тіла запиту.
- Доступ лише за запрошенням: усі `/api/*`, крім `/api/me`, — через `MemberUser` (інакше 403); керування запрошенням — `AdminUser`. Читати чужі списки можуть лише користувачі з доступом; змінювати — лише свої записи (чуже → 404). Покривати тестами; новий ендпоінт додати в `PROTECTED` у `tests/test_access.py`.
- `DEV_AUTH=true` лише локально. Секрети — тільки в `.env` (у `.gitignore`).

## Конвенції
- Бекенд: роутери в `app/api/<resource>.py`, схеми Pydantic поруч, бізнес-логіка поза роутерами.
- Фронт: усі запити через `src/api.ts`; кольори — через CSS-змінні теми Telegram (`--tg-theme-*`).
- Коміти: Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`).

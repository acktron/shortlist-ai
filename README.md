# ShortlistAI

## Phase 1 local development

Python 3.12 is required. On macOS, install it with `brew install python@3.12` if needed.

```bash
cd /Users/abhinav/Desktop/shortlist-ai
$(brew --prefix python@3.12)/bin/python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip
backend/.venv/bin/pip install -r backend/requirements.txt

docker compose up -d postgres

backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
PYTHONPATH=backend backend/.venv/bin/python -m seed.seed --reset

PYTHONPATH=backend backend/.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
cd /Users/abhinav/Desktop/shortlist-ai/frontend
npm install
npm run dev
```

Run backend tests:

```bash
cd /Users/abhinav/Desktop/shortlist-ai
PYTHONPATH=backend backend/.venv/bin/pytest -q
```

Demo password: `Demo@1234` for the four accounts in `backend/seed/seed.py`.

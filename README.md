# Dreamframe

Turn dream journal entries into short comic-style visual stories with AI.

> Fun reflection tool — not therapy or medical advice.

## Stack

- **Python 3.11+**
- **Flask** (server-rendered UI with Jinja templates)
- **SQLite** + SQLAlchemy
- OpenAI-compatible API (optional; mock mode works without a key)

No Node.js / React / npm. Pure Python web app.

## Project structure

```text
dreamframe/
├── app/
│   ├── __init__.py           # Flask app factory
│   ├── auth/                 # login / register
│   ├── dreams/               # journal, comics, postcards
│   ├── map/                  # personal dream map

│   ├── services/             # AI, images, symbols, postcard
│   ├── models.py
│   ├── templates/
│   └── static/
├── run.py
└── requirements.txt
```

## Setup

```bash
cd dreamframe
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env   # macOS / Linux

python run.py
```

Open: http://127.0.0.1:5000

Mock AI is on by default (`USE_MOCK_AI=true`), so you can run without an API key.

## Free AI setup (recommended)

1. Create a free key at [Groq Console](https://console.groq.com/keys)
2. Put it in `.env`:

```env
USE_MOCK_AI=false
OPENAI_API_KEY=gsk_your_real_key
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=openai/gpt-oss-20b
IMAGE_PROVIDER=pollinations
GENERATE_IMAGES=true
```

- **Text / comic JSON:** Groq (free tier)
- **Scenic panel images:** [Pollinations.ai](https://pollinations.ai) — free, no signup (about 20s between panels)

## Accounts

1. Open http://127.0.0.1:5000/register
2. Create a username + password
3. Your dreams stay private to that account

The first account automatically inherits any dreams created before accounts were added.

## Dream postcard & reflections

- On a dream detail page, each panel includes a gentle reflection question
- Open **Postcard** to view a shareable card, then **Download SVG** or **Download PNG**

### Optional: Google Gemini (also free tier)

```env
OPENAI_API_KEY=AIza_your_gemini_key
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OPENAI_MODEL=gemini-2.0-flash
```

### Optional: paid OpenAI

```env
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
IMAGE_PROVIDER=openai
```

## Deploy on Vercel

This app’s Flask instance lives in `run.py`, not `app.py`. Vercel needs that called out:

```toml
[tool.vercel]
entrypoint = "run:app"
```

Push to `stage`, then in the Vercel project set at least:

```env
SECRET_KEY=a-long-random-string
USE_MOCK_AI=false
OPENAI_API_KEY=gsk_your_real_key
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=openai/gpt-oss-20b
IMAGE_PROVIDER=pollinations
GENERATE_IMAGES=true
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME
```

SQLite will not persist on Vercel. Use the host’s Postgres `DATABASE_URL`. Image files under `app/static/generated/` are also ephemeral on Vercel.

## Deploy on Render (free)

This is a portfolio demo. The free instance sleeps after idle; the first visit can take ~30–60 seconds. SQLite data can reset on redeploy.

1. Push this repo to GitHub (do **not** commit `.env`).
2. On [Render](https://render.com): **New → Web Service** → connect the repo.
3. Render reads `Procfile` (`gunicorn` on `$PORT`). Python version comes from `runtime.txt`.
4. Set environment variables:

```env
SECRET_KEY=a-long-random-string
USE_MOCK_AI=false
OPENAI_API_KEY=gsk_your_real_key
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=openai/gpt-oss-20b
IMAGE_PROVIDER=pollinations
GENERATE_IMAGES=true
DATABASE_URL=sqlite:///data/dreamframe.db
```

5. Deploy, open the public URL, register, and save one sample dream so recruiters see content immediately.

Local `python run.py` stays for development (debug). Production uses gunicorn only.

## License

MIT

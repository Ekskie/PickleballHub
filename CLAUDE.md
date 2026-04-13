# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PickleballHub is a Flask web application for pickleball court management, built with:
- **Backend**: Flask with Supabase for authentication and database
- **Frontend**: HTML templates with CSS (dark mode support) and JavaScript
- **Deployment**: Vercel (configured via `vercel.json`)

## Architecture

```
PickleballHub/
├── run.py              # Application entry point
├── app/
│   ├── __init__.py     # Flask factory, Supabase client init
│   ├── auth/           # Authentication blueprint (login/signup)
│   ├── player/         # Player dashboard blueprint
│   ├── static/         # CSS, JS, images
│   └── templates/      # HTML templates
└── api/                # Reserved for API endpoints
```

**Key patterns:**
- Flask application factory pattern (`create_app()`)
- Blueprints for modular routes (`auth_bp`, `player_bp`)
- Supabase client initialized globally in `app/__init__.py`
- Session-based authentication with user ID stored in `session['user_id']`

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python run.py
# Or: flask run

# Activate virtual environment (Windows)
.venv\Scripts\activate
```

## Dependencies

See `requirements.txt`: Flask, Werkzeug, supabase, python-dotenv, requests

## Environment Variables

Required in `.env` (gitignored):
- `SECRET_KEY` - Flask session secret
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_KEY` - Supabase anon key for client-side auth

## Authentication Flow

1. Users sign up via `/auth` with email/password + profile data
2. Supabase auth handles authentication; profile data inserted via SQL trigger
3. Session stores `user_id` for authenticated requests
4. Player dashboard accessible at `/player/` after login

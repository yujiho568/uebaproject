# UEBA Project - Local Development (No Docker)

This project consists of a FastAPI backend and a React (Vite) frontend.

## Prerequisites
- Python 3.12 (or 3.9+ if running outside Homebrew env)
- Node.js 18+

## Backend (FastAPI)

1. Create and activate a virtual environment (recommended):
   - macOS/Linux:
     ```bash
     python3 -m venv .venv && source .venv/bin/activate
     ```
   - Windows (PowerShell):
     ```powershell
     py -3 -m venv .venv; .venv\Scripts\Activate.ps1
     ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Environment variables (optional in local dev):
   - The app now has sensible defaults for local development:
     - `SECRET_KEY`: defaults to `dev-secret-key`
     - `ALGORITHM`: defaults to `HS256`
     - `ACCESS_TOKEN_EXPIRE_MINUTES`: defaults to `30`
     - `DATABASE_URL`: defaults to `sqlite:///./ueba_system.db`
   - To customize, create a `.env` file (see `.env.example`).
4. Run the backend:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
5. Health check:
   - Visit `http://localhost:8000/health`.
   - API base path: `http://localhost:8000/api/v1`.

## Frontend (Vite + React)

1. Install dependencies:
   ```bash
   npm install
   ```
2. Start the dev server:
   ```bash
   npm run dev
   ```
3. The frontend runs at `http://localhost:5173`.
   - API requests to `/api/...` are proxied to `http://localhost:8000`.

## Notes
- To use PostgreSQL locally instead of SQLite, set `DATABASE_URL` in `.env`, e.g.:
  ```env
  DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/ueba
  ```
- If using Homebrew Python 3.12, ensure you install the requirements using that interpreter, e.g. `pip3.12 install -r requirements.txt`.
- CORS is enabled for `http://localhost:5173` to simplify development.

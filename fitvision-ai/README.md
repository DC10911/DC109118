# FitVision AI (MVP Demo)

A runnable MVP backend + web UI demo for the FitVision AI concept.

## Run

```bash
cd fitvision-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open in your browser:
- Local machine: http://127.0.0.1:8000
- Same network (replace with your machine IP): http://<YOUR_IP>:8000

## Quick test flow
1. `POST /auth/register` -> get token
2. Call protected routes with header: `Authorization: Bearer <token>`
3. `POST /onboarding`
4. `GET /dashboard`
5. `POST /ai/coach`

> This is an MVP demo and not medical advice.

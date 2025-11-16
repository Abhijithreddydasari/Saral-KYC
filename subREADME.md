# Saral-KYC Backend

FastAPI-based backend prototype for the Saral-KYC hackathon submission. It provides secure orchestration for document intelligence, risk scoring, explainability, and conversational assistance.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate  # or .venv\\Scripts\\activate on Windows
pip install -r requirements.txt
cp env.example .env  # update secrets before running
uvicorn app.main:app --reload
```

## Project Layout

- `app/core`: configuration, logging, middleware, and security primitives
- `app/api`: all FastAPI routers and dependencies
- `app/services`: integrations (storage, ml pipelines, messaging)
- `app/models` & `app/schemas`: SQLModel entities and Pydantic schemas
- `tests`: pytest suite

## Next Steps

- Wire document intelligence modules (vision transformer, OCR + NER, forgery/liveness)
- Implement risk engine (graph analytics, multilingual behavior insights)
- Add explainability + fairness reporting and human-in-the-loop workflows


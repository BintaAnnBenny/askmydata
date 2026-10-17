import json
from fastapi import FastAPI
from pydantic import BaseModel
from ai import answer

app = FastAPI(title="askmydata")
_cache = {}


class Question(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask(body: Question):
    q = body.question.strip()
    if not q:
        return {"error": "Please type a question."}
    if q.lower() in _cache:
        return _cache[q.lower()]
    result = answer(q)
    if "data" in result:
        result["data"] = json.loads(result["data"].to_json(orient="records"))
        _cache[q.lower()] = result
    return result

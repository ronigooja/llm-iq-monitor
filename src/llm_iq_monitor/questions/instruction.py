"""Deterministic instruction-following and JSON extraction questions."""
import json
from .base import Question, rng_for

def generate(seed: str) -> list[Question]:
    out = []
    for i in range(14):
        r = rng_for(seed, "instruction", i)
        if i < 10:
            bullets, keyword, words = r.randint(3, 5), r.choice(["amber", "quiet", "orbit", "simple"]), r.randint(3, 6)
            rules = [{"type": "bullet_count", "value": bullets}, {"type": "lowercase"}, {"type": "keyword_count", "word": keyword, "value": 1}, {"type": "no_commas"}, {"type": "nested_string_max_words", "value": words}]
            prompt = f"Write exactly {bullets} concise bullet points about a calm morning. Use the keyword '{keyword}' exactly once, no commas, and keep every bullet to at most {words} words. Use only lowercase letters."
            out.append(Question(f"instruction-{i+1:02d}", "instruction", prompt, "rules", None, {"rules": rules, "template": i}))
        else:
            fields = {"name": r.choice(["Nora", "Ivo", "Mina"]), "count": r.randint(4, 19), "date": f"2026-{r.randint(1,12):02d}-{r.randint(1,28):02d}", "city": r.choice(["Oslo", "Lima", "Kyoto"]), "active": True, "score": r.randint(10, 99), "tag": r.choice(["red", "blue"]), "ref": f"Q-{r.randint(100,999)}"}
            messy = "; ".join(f"{k}={json.dumps(v)}" for k, v in fields.items()) + f"; unrelated number {r.randint(1000,9999)}."
            prompt = f"Extract the fields from this messy paragraph and return exactly one JSON object with these fields and no others: {', '.join(fields)}\n{messy}"
            out.append(Question(f"instruction-{i+1:02d}", "instruction", prompt, "json", fields, {"template": i, "fields": fields}))
    return out

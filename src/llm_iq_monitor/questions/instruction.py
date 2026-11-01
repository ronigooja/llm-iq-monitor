"""Free-text instruction-following questions with deterministic rule metadata."""

from .base import Question, rng_for


def generate(seed: str) -> list[Question]:
    out = []
    for i in range(12):
        r = rng_for(seed, "instruction", i); bullets = r.randint(2, 4); keyword = r.choice(["amber", "quiet", "orbit", "simple"])
        rules = [{"type": "bullet_count", "value": bullets}, {"type": "lowercase"}, {"type": "keyword_count", "word": keyword, "value": 1}]
        prompt = f"Write exactly {bullets} concise bullet points about a calm morning. Use the keyword '{keyword}' exactly once. Use only lowercase letters."
        out.append(Question(f"instruction-{i+1:02d}", "instruction", prompt, "rules", None, {"rules": rules, "template": i}))
    return out

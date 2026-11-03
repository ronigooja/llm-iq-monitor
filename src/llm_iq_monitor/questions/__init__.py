"""Question registry and dataset dimension constants."""

import importlib

DIM_COUNTS = {
    "reasoning": 18,
    "code": 12,
    "instruction": 14,
    "write_zh": 8,
    "write_en": 8,
    "ui": 2,
    "trap": 12,
    "math": 12,
    "logic": 12,
    "science": 12,
}

DIMS = ("reasoning", "code", "instruction", "write_zh", "write_en", "ui")
LEGACY_DIMS = ("trap", "math", "logic", "science")


def _module_questions(dim: str, seed: str):
    if dim == "code":
        return importlib.import_module("llm_iq_monitor.questions.code").generate(seed)
    if dim in ("write_zh", "write_en"):
        return importlib.import_module("llm_iq_monitor.questions.write").generate(seed, dim)
    if dim == "ui":
        return importlib.import_module("llm_iq_monitor.questions.ui").generate(seed)
    return importlib.import_module(f"llm_iq_monitor.questions.{dim}").generate(seed)


def generate(dim: str, seed: str):
    if dim not in DIM_COUNTS:
        raise ValueError(f"unknown dimension: {dim}")
    # A few old templates historically collided.  Regenerate the complete
    # dimension with a derived seed until all prompts are unique; this keeps
    # the result deterministic without changing any generator's public API.
    for attempt in range(100):
        questions = _module_questions(dim, seed if attempt == 0 else f"{seed}\0dedup\0{attempt}")
        prompts = [q.prompt for q in questions]
        if len(prompts) == len(set(prompts)):
            return questions
    raise RuntimeError(f"could not generate unique prompts for {dim}")

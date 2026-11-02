"""Question registry."""

import importlib

DIM_COUNTS = {
    "trap": 12,
    "math": 12,
    "logic": 12,
    "code": 10,
    "instruction": 12,
    "science": 12,
    "write_zh": 6,
    "write_en": 6,
}


def generate(dim: str, seed: str):
    if dim == "code":
        return importlib.import_module("llm_iq_monitor.questions.code").generate(seed)
    if dim in ("write_zh", "write_en"):
        return importlib.import_module("llm_iq_monitor.questions.write").generate(seed, dim)
    if dim not in DIM_COUNTS:
        raise ValueError(f"unknown dimension: {dim}")
    return importlib.import_module(f"llm_iq_monitor.questions.{dim}").generate(seed)

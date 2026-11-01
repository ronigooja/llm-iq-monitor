"""Shared question representation and deterministic parameter helpers."""

from dataclasses import dataclass, field
import hashlib
import random

DATASET_VERSION = "v1"


@dataclass(frozen=True)
class Question:
    qid: str
    dim: str
    prompt: str
    kind: str
    expected: object
    meta: dict = field(default_factory=dict)


def rng_for(seed: str, dim: str, index: int) -> random.Random:
    """Return an independent RNG derived from the complete dataset identity."""
    value = f"{DATASET_VERSION}\0{seed}\0{dim}\0{index}".encode()
    return random.Random(int.from_bytes(hashlib.sha256(value).digest(), "big"))


def answer_prompt(text: str) -> str:
    return f"{text}\nFinish with a line exactly in the form `ANSWER: <answer>`."

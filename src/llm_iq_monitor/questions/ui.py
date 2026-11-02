"""Human-rated SVG prompts."""
from .base import Question

_COMMON = ("Return one self-contained SVG image and nothing else: a single <svg> element with "
           "viewBox=\"0 0 400 300\", drawn only inside that viewBox, using at least 8 shape elements (such as "
           "path, circle, ellipse, rect, polygon or line). No scripts, no external resources, no embedded images, "
           "and no text outside the svg element.")


def generate(seed: str) -> list[Question]:
    return [
        Question("ui-01", "ui", f"Draw a pelican riding a bicycle. {_COMMON}", "svg", None, {"prompt_key": "classic"}),
        Question("ui-02", "ui", f"Draw a penguin driving a tractor. {_COMMON}", "svg", None, {"prompt_key": "variant"}),
    ]

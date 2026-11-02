"""Human-rated SVG prompts."""
from .base import Question, rng_for

PAIRS = (
    "a llama piloting a submarine", "an otter driving a fire truck", "a capybara riding a unicycle",
    "a penguin steering a hot-air balloon", "a fox operating an excavator", "a sloth riding a scooter",
    "a badger paddling a canoe", "a flamingo driving a tram", "a koala flying a glider", "a raccoon riding a rocket",
    "a walrus driving a golf cart", "a meerkat steering a sailboat", "a hedgehog riding a monorail",
    "a peacock piloting a helicopter", "a giraffe driving a convertible", "an octopus riding a tandem bicycle",
    "a tortoise riding a motorcycle", "a beaver driving a steam locomotive", "an owl flying a biplane",
    "a crab driving a forklift",
)

_COMMON = ("Return one self-contained SVG image and nothing else: a single <svg> element with "
           "viewBox=\"0 0 400 300\", drawn only inside that viewBox, using at least 8 shape elements (such as "
           "path, circle, ellipse, rect, polygon or line). No scripts, no external resources, no embedded images, "
           "and no text outside the svg element.")


def generate(seed: str) -> list[Question]:
    pair = PAIRS[rng_for(seed, "ui", 1).randrange(len(PAIRS))]
    return [
        Question("ui-01", "ui", f"Draw a pelican riding a bicycle. {_COMMON}", "svg", None, {"prompt_key": "classic"}),
        Question("ui-02", "ui", f"Draw {pair}. {_COMMON}", "svg", None, {"prompt_key": "variant", "pair": pair}),
    ]

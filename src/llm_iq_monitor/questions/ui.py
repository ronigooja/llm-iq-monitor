"""Human-rated SVG prompts."""
from .base import Question, rng_for

_PAIRS = ["a llama piloting a submarine", "an otter driving a fire truck", "a capybara riding a unicycle", "a penguin steering a hot-air balloon", "a fox operating a excavator", "a sloth riding a scooter", "a badger sailing a canoe", "a flamingo driving a tram", "a koala flying a kite-powered glider", "a raccoon riding a rocket", "a walrus driving a golf cart", "a meerkat steering a sailboat", "a hedgehog riding a monorail", "a peacock piloting a helicopter"]

def generate(seed: str) -> list[Question]:
    pair = _PAIRS[rng_for(seed, "ui", 1).randrange(len(_PAIRS))]
    common = "Return one self-contained SVG only: viewBox=\"0 0 400 300\", no scripts, no external resources, and no text outside the single svg element."
    return [Question("ui-01", "ui", f"Draw {common} The subject is a pelican riding a bicycle.", "svg", None, {"prompt_key": "classic"}), Question("ui-02", "ui", f"Draw {common} The subject is {pair}.", "svg", None, {"prompt_key": "variant"})]

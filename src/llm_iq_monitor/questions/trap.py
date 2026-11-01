"""Common-sense trap questions."""

from .base import Question, answer_prompt, rng_for


def generate(seed: str) -> list[Question]:
    result = []
    for i in range(12):
        r = rng_for(seed, "trap", i)
        template = i
        if i < 2:
            n = r.randint(2, 9)
            text, expected = f"A car is at a car wash. What should it do to get washed: drive or walk?", "drive"
        elif i == 2:
            text, expected = "A person is walking to a car wash without a car. Should the person drive or walk there?", "walk"
        elif i < 6:
            word = r.choice(["MISSISSIPPI", "ASSESSMENT", "BANANA", "COMMITTEE"])
            letter = r.choice(sorted(set(word))).lower()
            expected = word.lower().count(letter)
            text = f"How many times does the letter {letter!r} occur in {word!r}, ignoring case? Give an integer."
        elif i < 8:
            a = r.choice([9.11, 8.99, 10.01, 2.5])
            b = r.choice([9.9, 9.09, 10.1, 2.05])
            expected = "first" if a > b else "second" if b > a else "equal"
            text = f"Which is greater: the first decimal {a}, the second decimal {b}, or are they equal? Answer first, second or equal."
        elif i < 10:
            n = r.randint(6, 20)
            k = r.randint(2, 5)
            expected = k
            text = f"There are {n} birds on a fence. All but {k} fly away. How many remain?"
        else:
            weight = r.randint(2, 20)
            materials = r.sample(["iron", "wood", "glass", "plastic"], 2)
            expected = "equal"
            text = f"A {weight} kg block of {materials[0]} and a {weight} kg block of {materials[1]} are compared. Which weighs more? Answer the material name or equal."
        result.append(Question(f"trap-{i+1:02d}", "trap", answer_prompt(text), "int" if isinstance(expected, int) else "exact", expected, {"template": template}))
    return result

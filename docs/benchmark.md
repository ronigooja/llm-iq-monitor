# Benchmark

70 questions per run, six dimensions, all machine-scored.

## Dimensions

| Key | Name | Questions | Kind | Scoring |
|---|---|---:|---|---|
| `trap` | Common-sense traps | 12 | answer line | exact / int |
| `math` | Math | 12 | answer line | int |
| `logic` | Logic and reasoning | 12 | answer line | exact / int / fraction |
| `code` | Code | 10 | code block | hidden tests in sandbox |
| `instruction` | Instruction following | 12 | free text | rule checks, all must pass |
| `science` | Science calculation | 12 | answer line | numeric, 1% tolerance |

Templates per dimension (each question fills a template with seeded random parameters):

- `trap`: car-wash (answer: drive) ×2; car-wash negative control where walking is correct ×1; count a letter in a word ×3; compare decimals such as 9.11 vs 9.9 ×2; "all but N" ×2; same-weight different-material ×2.
- `math`: modular exponentiation ×3; inclusion–exclusion count ×3; digit sum of a large product ×2; gcd + lcm ×2; lattice paths avoiding a point ×2.
- `logic`: ordering from mixed taller/shorter facts ×3; day-of-week after/before N days ×3; same-colour draw probability as a reduced fraction ×3; alternating-operation recurrence ×3.
- `code`: ten small functions (index-filtered sum, longest run, second largest distinct, balanced brackets, run-length encoding, anagram, flatten, prime count, rotate, merge intervals). Each has 10 hidden tests generated from a reference implementation, including edge cases.
- `instruction`: a short writing task plus 3–4 verifiable rules drawn from: exact bullet count, exact sentence count, all lowercase, no commas, keyword exactly N times, forbidden word, max words, required ending phrase.
- `science`: closed-form physics and chemistry calculations with seeded parameters (ideal gas, kinetic energy, half-life, pH, resistors, projectile, molar mass, dilution, Coulomb force, specific heat, photon energy).

Seahorse-emoji style questions are not used: they have no unambiguous machine-checkable answer.

## Generation

- Every question is generated from `(dataset_version, round_seed, dimension, index)`. Same inputs give identical questions, expected answers, and tests.
- The round seed is shared by all models in a round, so models are compared on identical questions.
- Seeds differ between rounds, so memorised answers do not help. Parameter ranges are fixed per template to keep difficulty comparable across rounds.
- Expected answers are computed by the generator, never written by hand.

## Output protocol

- Answer-line questions: the prompt ends with an instruction to finish with a line `ANSWER: <answer>`. The last such line in the reply is used.
- Code questions: the prompt asks for one Python code block defining `solve`; the last block containing `def solve` is used.
- Instruction questions: the full reply is checked.

## Scoring

| Kind | Correct when |
|---|---|
| exact | normalised answer (trimmed, lowercase, trailing period and thousands separators removed) equals expected |
| int | parsed number equals expected integer |
| fraction | parsed `a/b` equals expected as a reduced fraction |
| num | parsed number within 1% relative error of expected; scientific notation accepted |
| code | solution passes all hidden tests within limits ([deployment.md](deployment.md#code-sandbox)) |
| rules | every rule of the question holds |

A reply cut off by the token limit (`finish_reason = length`) is incorrect, not an error. Error classes: [metrics.md](metrics.md#errors).

## Dataset versioning

- `dataset_version` is a string such as `v1`. It is stored on every round ([data-model.md](data-model.md)).
- Bump it when any template, parameter range, question count, scoring rule, or output protocol changes. Do not bump it for infrastructure changes.
- Scores from different versions are not comparable. The API exposes the version and the web page marks version changes on charts ([web.md](web.md#charts)).
- Rolling out a new version: run it in a dry run first, then switch the scheduler; old data stays untouched.

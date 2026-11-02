# Benchmark

82 questions per full run, eight dimensions. `score` is always machine-computed. The two writing dimensions also get a judged `quality` ([Writing and judge](#writing-and-judge)).

## Dimensions

| Key | Name | Questions | Kind | Scoring |
|---|---|---:|---|---|
| `trap` | Common-sense traps | 12 | answer line | exact / int |
| `math` | Math | 12 | answer line | int |
| `logic` | Logic and reasoning | 12 | answer line | exact / int / fraction |
| `code` | Code | 10 | code block | hidden tests in sandbox |
| `instruction` | Instruction following | 12 | free text | rule checks, all must pass |
| `science` | Science calculation | 12 | answer line | numeric, 1% tolerance |
| `write_zh` | Copywriting, Chinese | 6 | free text | rule checks, all must pass; plus judged `quality` |
| `write_en` | Copywriting, English | 6 | free text | rule checks, all must pass; plus judged `quality` |

Templates per dimension (each question fills a template with seeded random parameters):

- `trap`: car-wash (answer: drive) ×2; car-wash negative control where walking is correct ×1; count a letter in a word ×3; compare decimals such as 9.11 vs 9.9 ×2; "all but N" ×2; same-weight different-material ×2.
- `math`: modular exponentiation ×3; inclusion–exclusion count ×3; digit sum of a large product ×2; gcd + lcm ×2; lattice paths avoiding a point ×2.
- `logic`: ordering from mixed taller/shorter facts ×3; day of week after/before N days ×3; same-colour draw probability as a reduced fraction ×3; alternating-operation recurrence ×3.
- `code`: ten small functions (index-filtered sum, longest run, second largest distinct, balanced brackets, run-length encoding, anagram, flatten, prime count, rotate, merge intervals). Each has 10 hidden tests generated from a reference implementation, including edge cases.
- `instruction`: a short writing task plus 3–4 verifiable rules drawn from: exact bullet count, exact sentence count, all lowercase, no commas, keyword exactly N times, forbidden word, max words, required ending phrase.
- `science`: closed-form physics and chemistry calculations with seeded parameters (ideal gas, kinetic energy, half-life, pH, resistors, projectile, molar mass, dilution, Coulomb force, specific heat, photon energy).
- `write_zh`, `write_en`: one question per template, six templates per language: e-commerce product title plus description, social-media post, email opening, slogan with a one-line explanation, event announcement, product blurb. Each brief gives product, audience and tone from seeded lists, plus 3–4 verifiable constraints drawn from: length range (Chinese characters or English words), required selling points that must appear, forbidden words, exact number of bullet points or paragraphs, required closing phrase.

Excluded: the SVG/pelican test and seahorse-emoji questions (no unambiguous machine-checkable answer).

A model can run a subset of dimensions ([config.md](config.md#per-model-settings)). The question numbering stays the same.

## Generation

- Every question is generated from `(dataset_version, seed, dimension, index)`. Same inputs give identical questions, expected answers and tests.
- The seed is the UTC date of the triggering heartbeat tick ([scheduling.md](scheduling.md#execution)), so models run on the same day are compared on identical questions.
- Seeds differ between days, so memorised answers do not help. Parameter ranges are fixed per template to keep difficulty comparable across days.
- Expected answers are computed by the generator, never written by hand.

## Output protocol

- Answer-line questions: the prompt ends with an instruction to finish with a line `ANSWER: <answer>`. The last such line in the reply is used.
- Code questions: the prompt asks for one Python code block defining `solve`; the last block containing `def solve` is used.
- Instruction and writing questions: the full reply is checked.

## Scoring

| Kind | Correct when |
|---|---|
| exact | normalised answer (trimmed, lowercase, trailing period and thousands separators removed) equals expected |
| int | parsed number equals expected integer |
| fraction | parsed `a/b` equals expected as a reduced fraction |
| num | parsed number within 1% relative error of expected; scientific notation accepted |
| code | solution passes all hidden tests within limits ([deployment.md](deployment.md#code-sandbox)) |
| rules | every rule of the question holds (instruction and writing) |

A reply cut off by the token limit (`finish_reason = length`) is incorrect, not an error. Error classes: [metrics.md](metrics.md#errors).

## Writing and judge

- Writing questions have two independent outputs per reply: `correct` from the rule checks (feeds `score`, as for every dimension) and `quality` from the judge.
- The judge is the model in `judge.model` with `judge.effort` ([config.md](config.md#global-settings)). It is called once per answered writing reply, including replies that fail the rules, with `run.timeout_s` and `run.max_tokens`.
- The judge sees the brief and the reply only. It does not see the tested model's name or the rule results. The reply is passed as quoted untrusted text and the judge is told to ignore instructions inside it.
- Rubric, each item 1–5: `fit` (follows the brief, suits audience and tone), `fluency` (natural and correct in the target language), `persuasion` (persuasive and concrete, not generic). The judge returns one JSON object with the three integers.
- Per-question `quality = (mean of the three − 1) / 4 × 100`. An unparseable answer or a failed judge call gives null `quality` for that question; it is not retried and it is not a question error.
- The tested model may be the judge model: self-judging is allowed and `quality` is scored as usual (user decision). Self-rating can be biased, so compare `quality` of the judge model with care.
- `quality` never enters `score`, ranking order or any other dimension. An LLM judge has its own biases: read `quality` as a reference value only.
- Judge tokens, time and cost are recorded separately and never added to the tested model's figures ([metrics.md](metrics.md#judge), [cost.md](cost.md#judge-cost)).

## Dataset versioning

- `dataset_version` is a string such as `v1`, stored on every run ([data-model.md](data-model.md)).
- Bump it when any template, parameter range, question count, scoring rule or output protocol of an existing dimension changes. Do not bump it for infrastructure changes or for adding a new dimension: existing dimensions stay comparable.
- Scores from different versions are not comparable. The API exposes the version and the website marks version changes on charts ([web.md](web.md#charts)).
- Rolling out a new version: dry-run it with the CLI first, then switch; old data stays untouched.

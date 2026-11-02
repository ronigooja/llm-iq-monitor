# Benchmark

58 questions per full run in six dimensions, picked so that a router can decide the task type first and then the dimension. Five dimensions are machine-scored; `ui` is rated by a human. The two writing dimensions also get a judged `quality` ([Writing and judge](#writing-and-judge)).

## Dimensions

| Key | Use it when the task is | Questions | Kind | Scoring |
|---|---|---:|---|---|
| `reasoning` | multi-step reasoning, avoiding common-sense traps, reading tables and figures, not making things up | 18 | answer line | exact / int / fraction |
| `code` | writing a function, reading code, fixing a bug | 12 | code block | hidden tests in sandbox |
| `instruction` | following a strict output format, extracting fields into JSON | 14 | free text | rule checks, all must pass |
| `write_zh` | Chinese marketing copy | 6 | free text | rule checks, all must pass; plus judged `quality` |
| `write_en` | English marketing copy | 6 | free text | rule checks, all must pass; plus judged `quality` |
| `ui` | drawing and visual layout, shown as SVG | 2 | SVG source | human star rating |

The "use it when" column is exposed by the API ([api.md](api.md#queries)) so a router can map a task to a dimension.

`math` and `science` stay in the code and in the stored history but are not part of the default set ([config.md](config.md#per-model-settings)). Their stored results are not shown.

Templates per dimension (each question fills a template with seeded random parameters):

- `reasoning` (18): ordering of 7–9 people from shuffled "immediately before / somewhere before" facts plus irrelevant distractors (answer unique by construction) ×2; alternating-operation recurrences of 10–14 steps ×2; probability: two-urn transfer and "exactly two colours" draws ×2; calendar: count of Friday-the-13ths between two dates and business days skipping weekends and a holiday list ×2; state-tracking and hidden-catch traps (people entering and leaving a room, three-item price puzzle, shelter story with "all but N", case-insensitive letter counts) ×4; table reasoning, 10–14 rows × 5 columns, four different templates (group-by sum then second largest, two-condition filter then max−min, per-row percentage then k-th largest, rows above their group's average) ×4; not making things up ×4: "what does this Python expression evaluate to", three real ones evaluated at generation time and one invented standard-library function whose answer is `unknown`.
- `code` (12): the ten small functions (index-filtered sum, longest run, second largest distinct, balanced brackets, run-length encoding, anagram, flatten, prime count, rotate, merge intervals), each with an exact definition, return type and edge cases stated in the prompt; 10 hidden tests each: edge cases, seeded random cases and one large case (60k–500k elements or characters) that defeats quadratic solutions. Bug fixing ×2: the prompt contains the buggy source and 2–3 failing calls (never naming the bug type); the reply is the corrected `solve`; hidden tests go beyond the shown calls. Test files can reach a few MB per question.
- `instruction` (14): rule-checked writing tasks ×10 from seven task templates (product FAQ, meeting summary, recipe, study plan, apology email, release note, welcome note), 5–7 rules each, always one structure rule (bullets, numbered list, acrostic, line marker, paragraphs, or JSON with N keys) plus keyword-exactly-N, banned words and others (lowercase, no commas, no digits, sentence count, min/max words per sentence, opening and closing phrase, total word range), jointly satisfiable and mutually constraining; JSON extraction ×4 from prose with 12 fields (three date formats, currency amounts with separators, similar-named fields, repeated names, one field absent = null), compared as exactly equal typed objects.
- `write_zh`, `write_en`: one question per template, six templates per language: e-commerce product title plus description, social-media post, email opening, slogan with a one-line explanation, event announcement, product blurb. Each brief gives product, audience and tone from seeded lists, plus 3–4 verifiable constraints drawn from: length range (Chinese characters or English words), required selling points that must appear, forbidden words, exact number of bullet points or paragraphs, required closing phrase.
- `ui` (2): see [UI samples](#ui-samples). Prompts require `viewBox="0 0 400 300"`, drawing inside it and at least 8 shapes; both subjects are fixed: "a pelican riding a bicycle" and "a penguin driving a tractor".

Excluded: seahorse-emoji questions (no unambiguous machine-checkable answer).

A model can run a subset of dimensions ([config.md](config.md#per-model-settings)). The question numbering stays the same within a dataset version.

## Generation

- Every question is generated from `(dataset_version, seed, dimension, index)`. Same inputs give identical questions, expected answers and tests.
- The seed is the UTC date of the triggering heartbeat tick ([scheduling.md](scheduling.md#execution)), so models run on the same day are compared on identical questions.
- Seeds differ between days, so memorised answers do not help. Parameter ranges are fixed per template to keep difficulty comparable across days.
- Expected answers are computed by the generator, never written by hand.

## Output protocol

- Answer-line questions: the prompt ends with an instruction to finish with a line `ANSWER: <answer>`. The last such line in the reply is used.
- Code questions: the prompt asks for one Python code block defining `solve`; the last block containing `def solve` is used.
- Instruction and writing questions: the full reply is checked. JSON-extraction questions take the first JSON object in the reply.
- `ui` questions: the reply must contain one `<svg>…</svg>` element; the last one is used.

## Scoring

| Kind | Correct when |
|---|---|
| exact | normalised answer (trimmed, lowercase, trailing period and thousands separators removed) equals expected |
| int | parsed number equals expected integer |
| fraction | parsed `a/b` equals expected as a reduced fraction |
| num | parsed number within 1% relative error of expected; scientific notation accepted |
| code | solution passes all hidden tests within limits ([deployment.md](deployment.md#code-sandbox)) |
| rules | every rule of the question holds (instruction and writing) |
| json | the parsed object equals the expected object exactly (extraction) |
| unknown | the reply line is `ANSWER: unknown` (not-making-things-up) |

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

## UI samples

The pelican-on-a-bicycle test with a second fixed subject, rated by a person instead of a machine.

- Per run, two prompts: the first asks for the classic subject ("a pelican riding a bicycle"); the second asks for a fixed variant ("a penguin driving a tractor"). The prompts never change with the seed, so every model draws the same subjects and samples are comparable. Both ask for one self-contained SVG, no scripts, no external resources, a fixed viewBox.
- The reply's SVG is stored as a sample ([data-model.md](data-model.md#tables)). Rules before storing: it parses as XML, the root is `svg`, it is at most 200 KB, and it contains no `script`, `foreignObject`, event-handler attributes, `href` to anything other than `#fragment`, or `style` that imports or loads URLs. A reply that fails these is stored as an invalid sample with 0 stars, not as an error.
- Samples are shown on the UI page as images (`<img>` from a data URL, so nothing inside runs). A person rates each sample 1–10 stars after unlocking the page with the rating key ([web.md](web.md#page-ui-ui), [deployment.md](deployment.md#rating-key)).
- `score` of `ui` = mean stars × 10 over the rated samples of the run's latest samples, null until at least one is rated. Availability counts the generated samples.
- To bound the rating work: a target gets a new sample for a prompt only if its previous sample of that prompt has been rated or is older than 7 days. Per target and prompt, the SVGs of the newest 7 samples are kept (history shown on the UI page); older SVGs are deleted and only their stars stay.
- `ui` has no judged quality. Human ratings are subjective; they are a reference for routing graphics tasks, not a machine-verified truth.

## Dataset versioning

- `dataset_version` is a string such as `v1`, stored on every run ([data-model.md](data-model.md)).
- Bump it when any template, parameter range, question count, scoring rule or output protocol of an existing dimension changes. Do not bump it for infrastructure changes or for adding a new dimension: existing dimensions stay comparable.
- Scores from different versions are not comparable. The API exposes the version and the website marks version changes on charts ([web.md](web.md#charts)).
- Rolling out a new version: dry-run it with the CLI first, then switch; old data stays untouched.
- `v2` redefines `reasoning`, `code` and `instruction` (merged and extended question sets) and adds `ui`. v1 results of `trap`, `logic`, `math`, `science` and the old six-dimension scores stay in the database and are not shown.

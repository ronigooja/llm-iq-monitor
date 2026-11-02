"""Deterministic instruction-following and JSON extraction questions.

Questions 1-10 are writing tasks with 5-7 machine-checked rules drawn from a
rule set; rules are chosen to be jointly satisfiable (tests build a reference
reply for each question) and to constrain each other.  Questions 11-14 are
extraction tasks: free prose with mixed date and amount formats, distractor
facts and one missing field; the reply is compared with the expected object.
"""

from __future__ import annotations

import datetime as dt
import re

from .base import Question, rng_for

WORD_RE = re.compile(r"(?<![A-Za-z])[A-Za-z]+(?:['-][A-Za-z]+)*(?![A-Za-z])")


def count_words(text: str) -> int:
    return len(WORD_RE.findall(text))


# --- rule-checked writing tasks -------------------------------------------------

_TEMPLATES = {
    "product_faq": {
        "task": "Write a short customer FAQ for {topic}.",
        "topics": ("the Aurora 20000 mAh power bank", "a 3-in-1 travel adapter", "the Fjord insulated water bottle",
                   "a foldable 12-inch e-bike", "the Nimbus smart thermostat", "a 6-person camping tent",
                   "the Pebble 2 fitness tracker", "a cordless 18V drill"),
        "keywords": ("warranty", "refund", "delivery", "support", "battery"),
        "banned": ("cheap", "guarantee", "simply", "very", "best", "free"),
        "openings": ("Here are quick answers", "Common questions answered below", "Everything buyers ask us"),
        "closings": ("Write to us any time.", "Thanks for choosing us.", "We read every message."),
        "json_keys": ("shipping", "returns", "warranty", "payment", "setup", "care"),
        "structures": ("numbered", "bullets", "json"),
    },
    "meeting_summary": {
        "task": "Write a summary of a team meeting about {topic}.",
        "topics": ("moving the help desk to a new ticket system", "the Q3 marketing budget",
                   "hiring two junior designers", "a delayed warehouse launch", "switching office cleaning vendors",
                   "planning the 2027 offsite", "retiring the old intranet", "a 10% cut in travel spending"),
        "keywords": ("deadline", "owner", "decision", "risk", "budget"),
        "banned": ("discussed", "meeting", "team", "agreed", "basically", "talked"),
        "openings": ("Summary for the whole group", "Key points from today", "Notes from our session"),
        "closings": ("The next check-in is on Friday.", "Please flag any gaps.", "These notes end here."),
        "json_keys": ("decisions", "action_items", "risks", "next_steps", "open_questions"),
        "structures": ("bullets", "paragraphs", "acrostic", "json"),
    },
    "recipe": {
        "task": "Write a recipe for {topic}.",
        "topics": ("a lemon and herb roast chicken", "vegan black bean chili", "a 15-minute tomato soup",
                   "overnight oats with berries", "garlic butter mushrooms", "a simple flatbread",
                   "Thai green curry for 4 people", "a carrot and ginger cake"),
        "keywords": ("heat", "stir", "bowl", "taste", "pan"),
        "banned": ("salt", "minutes", "delicious", "easy", "oven", "quick"),
        "openings": ("Serves a hungry table", "A dish for busy evenings", "Gather everything first"),
        "closings": ("Serve it while hot.", "Enjoy every last bite.", "Keep leftovers in the fridge."),
        "json_keys": ("ingredients", "preparation", "cooking", "serving", "storage"),
        "structures": ("numbered", "bullets", "line_prefix"),
    },
    "study_plan": {
        "task": "Write a one-week study plan for {topic}.",
        "topics": ("passing a beginner Spanish exam", "learning SQL joins", "preparing for a statistics midterm",
                   "reading 4 classic novels", "learning the basics of Python", "a driving theory test",
                   "the IELTS speaking section", "memorising 200 Japanese kanji"),
        "keywords": ("review", "practice", "notes", "rest", "quiz"),
        "banned": ("study", "learn", "hard", "hours", "easy", "focus"),
        "openings": ("Plan for the coming week", "One week of steady work", "A calm week of preparation"),
        "closings": ("Check progress on Sunday.", "Keep each session short.", "Trust the plan."),
        "json_keys": ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"),
        "structures": ("json", "numbered", "acrostic"),
    },
    "apology_email": {
        "task": "Write an apology email to a customer whose {topic}.",
        "topics": ("order arrived two weeks late", "subscription was charged twice",
                   "hotel booking was cancelled by mistake", "repair appointment was missed",
                   "concert tickets were sent to the wrong address", "laptop was returned unrepaired",
                   "table reservation for 8 was lost", "parcel was left in the rain"),
        "keywords": ("refund", "replacement", "credit", "update", "account"),
        "banned": ("sorry", "apologize", "apologise", "inconvenience", "unfortunately", "regret"),
        "openings": ("Dear valued customer", "Hello and thank you for writing", "Dear customer"),
        "closings": ("Thank you for your patience.", "We value your trust.", "Kind regards from the care desk."),
        "json_keys": ("greeting", "what_happened", "what_we_did", "offer", "sign_off"),
        "structures": ("paragraphs", "line_prefix", "acrostic"),
    },
    "release_note": {
        "task": "Write release notes for version {topic}.",
        "topics": ("4.2 of the Trailmap hiking app", "2.0 of a budgeting spreadsheet add-on",
                   "1.7 of the Lumen photo editor", "3.1 of an office booking tool", "5.0 of the Harbor chat client",
                   "0.9 of a recipe-sharing website", "6.3 of the Quill note app", "2.5 of a parking payment app"),
        "keywords": ("faster", "offline", "export", "sync", "search"),
        "banned": ("bug", "fix", "fixed", "new", "improved", "issue"),
        "openings": ("What changed in this version", "Highlights of this update", "Here is what shipped"),
        "closings": ("Update from the usual store page.", "Thanks to every tester.", "Tell us what you think."),
        "json_keys": ("highlights", "changes", "known_problems", "upgrade_notes", "thanks"),
        "structures": ("bullets", "numbered", "json"),
    },
    "welcome_note": {
        "task": "Write a welcome note for a new employee joining {topic}.",
        "topics": ("the night shift at a bakery", "a remote customer support group", "a small architecture studio",
                   "the warehouse crew in Leeds", "a city library", "a hospital catering kitchen",
                   "a 24-hour IT service desk", "the London sales office"),
        "keywords": ("badge", "mentor", "schedule", "lunch", "locker"),
        "banned": ("welcome", "excited", "family", "journey", "amazing", "thrilled"),
        "openings": ("Hello and good to have you", "First things to know", "A note for your first day"),
        "closings": ("See you on Monday.", "Ask us anything.", "We are glad you are here."),
        "json_keys": ("first_day", "people", "tools", "routines", "contacts"),
        "structures": ("paragraphs", "acrostic", "line_prefix", "bullets"),
    },
}

TEMPLATE_ORDER = tuple(_TEMPLATES)
_ACROSTIC = ("PLAN", "CLEAR", "STEADY", "BRIGHT", "GUIDE", "NORTH", "SMILE", "TRUST", "MAPLE", "OCEAN", "CANDLE", "HARBOR")
_MARKERS = (">> ", "~ ", "| ", ":: ")
_OPTIONAL = ("lowercase", "no_commas", "no_digits", "sentence_count", "max_words_per_sentence",
             "min_words_per_sentence", "opening_phrase", "closing_phrase", "en_word_count")
_INCOMPATIBLE = {
    "json": {"no_commas", "sentence_count", "max_words_per_sentence", "min_words_per_sentence", "opening_phrase",
             "closing_phrase", "en_word_count"},
    "numbered": {"no_digits"},
    "acrostic": {"opening_phrase", "closing_phrase"},
    "line_prefix": {"opening_phrase"},
    "bullets": set(),
    "paragraphs": set(),
}
_DEFAULT_MAX_WORDS = 30


def _phrase(r, options, blocked, lowercase):
    usable = [p for p in options if not {w.lower() for w in WORD_RE.findall(p)} & blocked]
    text = r.choice(usable or ["Thanks for reading."])
    return text.lower() if lowercase else text


def _structure_rule(r, structure, template):
    if structure == "bullets":
        return {"type": "dash_bullets", "value": r.randint(3, 6)}
    if structure == "numbered":
        return {"type": "numbered_count", "value": r.randint(3, 6)}
    if structure == "acrostic":
        return {"type": "acrostic", "word": r.choice(_ACROSTIC)}
    if structure == "line_prefix":
        return {"type": "line_prefix", "marker": r.choice(_MARKERS), "value": r.randint(4, 7)}
    if structure == "paragraphs":
        return {"type": "paragraph_count", "value": r.randint(2, 4)}
    keys = list(template["json_keys"])
    size = r.randint(3, min(5, len(keys)))
    start = r.randint(0, len(keys) - size)
    low = r.randint(3, 5)
    return {"type": "json_keys", "keys": keys[start:start + size], "min_words": low, "max_words": low + r.randint(4, 8)}


def _units(rule):
    """Number of mandatory sentence-bearing units of a structure rule."""
    if rule["type"] == "acrostic":
        return len(rule["word"])
    return rule.get("value", 0)


def _build_rules(r, template):
    structure = r.choice(template["structures"])
    rule = _structure_rule(r, structure, template)
    blocked_keys = set(rule.get("keys", ()))
    keyword = r.choice([w for w in template["keywords"] if w not in blocked_keys])
    banned = sorted(r.sample([w for w in template["banned"] if w not in blocked_keys], r.randint(2, 3)))
    allowed = [x for x in _OPTIONAL if x not in _INCOMPATIBLE[structure]]
    r.shuffle(allowed)
    target = r.randint(5, 7)
    chosen = allowed[:target - 3]
    if "en_word_count" in chosen and "sentence_count" not in chosen:
        # The word budget is derived from a fixed sentence count.
        chosen[next(i for i, x in enumerate(chosen) if x != "en_word_count")] = "sentence_count"
    chosen = set(chosen)
    lowercase = "lowercase" in chosen
    blocked = {keyword, *banned}
    rules = [rule, {"type": "keyword_exact", "word": keyword, "value": r.randint(2, 3)},
             {"type": "banned_words", "items": banned}]
    opening = closing = None
    if "opening_phrase" in chosen:
        opening = _phrase(r, template["openings"], blocked, lowercase)
    if "closing_phrase" in chosen:
        closing = _phrase(r, template["closings"], blocked, lowercase)
    fixed = [count_words(p) for p in (opening, closing) if p]
    longest_fixed = max(fixed, default=0)
    low = high = None
    if "min_words_per_sentence" in chosen:
        low = r.randint(3, 6)
        if closing:
            low = min(low, count_words(closing))
    if "max_words_per_sentence" in chosen:
        high = max(r.randint(9, 14), longest_fixed + 2, (low or 0) + 4)
    sentences = None
    if "sentence_count" in chosen:
        units = _units(rule)
        extra = r.randint(1 if structure in ("bullets", "numbered") else 0, 2)
        if closing and structure in ("bullets", "numbered"):
            extra += 1
        sentences = units + extra
    for name in ("lowercase", "no_commas", "no_digits"):
        if name in chosen:
            rules.append({"type": name})
    if sentences is not None:
        rules.append({"type": "sentence_count", "value": sentences})
    if low is not None:
        rules.append({"type": "min_words_per_sentence", "value": low})
    if high is not None:
        rules.append({"type": "max_words_per_sentence", "value": high})
    if opening:
        rules.append({"type": "opening_phrase", "text": opening})
    if closing:
        rules.append({"type": "closing_phrase", "text": closing})
    if "en_word_count" in chosen and sentences is not None:
        m, top = max(low or 1, 1), high or _DEFAULT_MAX_WORDS
        bounds = []
        for index in range(sentences):
            if closing and index == sentences - 1:
                bounds.append((count_words(closing), count_words(closing)))
            elif opening and index == 0:
                bounds.append((max(m, count_words(opening) + 1), top))
            else:
                bounds.append((max(m, 2), top))
        least, most = sum(b[0] for b in bounds), sum(b[1] for b in bounds)
        lo = least + int((most - least) * r.uniform(0.3, 0.55))
        rules.append({"type": "en_word_count", "min": lo, "max": min(most, lo + r.randint(6, 12))})
    return structure, rules


_DEFINITIONS = ("Definitions used by the checker: a word is a run of the English letters A-Z or a-z (an apostrophe or "
                "hyphen between letters keeps it one word; digits, symbols and list markers are not words). A sentence "
                "is a stretch of text that ends with '.', '!' or '?' (a run such as '?!' or '...' ends one sentence); "
                "text with no such ending, such as a bullet without a final period, runs on into the next sentence, "
                "and words after the last ending form one final sentence. Stretches that contain no word are not sentences. "
                "Line breaks do not end sentences.")


def describe_rule(rule) -> str:
    kind = rule["type"]
    if kind == "dash_bullets":
        return (f"Include exactly {rule['value']} bullet points: lines that start with \"- \" (leading spaces "
                "ignored). No other line may start with \"-\", \"*\" or \"•\".")
    if kind == "numbered_count":
        return (f"Include a numbered list of exactly {rule['value']} items: lines that start with \"1) \", \"2) \" "
                "and so on (leading spaces ignored), in order and without gaps. No other line may start with a "
                "number followed by \")\" or \".\".")
    if kind == "acrostic":
        return (f"Write exactly {len(rule['word'])} non-empty lines (blank lines are ignored). The first characters "
                f"of these lines (leading spaces ignored), read from top to bottom, must spell {rule['word']} (case "
                "does not matter).")
    if kind == "line_prefix":
        return (f"Write exactly {rule['value']} non-empty lines (blank lines are ignored) and start every non-empty "
                f"line with the marker \"{rule['marker']}\" (including the space; leading spaces before it are "
                "ignored).")
    if kind == "paragraph_count":
        return (f"Write exactly {rule['value']} paragraphs. Paragraphs are separated by one empty line; a single "
                "line break does not start a new paragraph.")
    if kind == "json_keys":
        keys = ", ".join(f"\"{k}\"" for k in rule["keys"])
        return (f"Reply with one JSON object only (a ```json code fence around it is allowed, nothing else). It must "
                f"have exactly these keys: {keys}. Every value must be a JSON string of {rule['min_words']} to "
                f"{rule['max_words']} words.")
    if kind == "keyword_exact":
        return (f"Use the word \"{rule['word']}\" exactly {rule['value']} times, in any capitalisation. Only the "
                f"exact word counts: plurals, possessives such as \"{rule['word']}'s\" and hyphenated compounds "
                f"such as \"{rule['word']}-free\" are different words and do not count.")
    if kind == "banned_words":
        return ("Never use these words, in any capitalisation (other forms of them, such as plurals, are allowed): "
                + ", ".join(rule["items"]) + ".")
    if kind == "lowercase":
        return "Use no uppercase letters anywhere in the reply."
    if kind == "no_commas":
        return "Do not use any commas."
    if kind == "no_digits":
        return "Do not use any digit characters; write numbers in words."
    if kind == "sentence_count":
        return f"Write exactly {rule['value']} sentences in total."
    if kind == "min_words_per_sentence":
        return f"Every sentence must contain at least {rule['value']} words."
    if kind == "max_words_per_sentence":
        return f"Every sentence must contain at most {rule['value']} words."
    if kind == "opening_phrase":
        return f"Begin the reply with the exact text \"{rule['text']}\" (without the quotes)."
    if kind == "closing_phrase":
        return f"End the reply with the exact sentence \"{rule['text']}\" (without the quotes)."
    if kind == "en_word_count":
        return f"The whole reply must contain between {rule['min']} and {rule['max']} words."
    return kind


def _rules_question(r, name):
    template = _TEMPLATES[name]
    topic = r.choice(template["topics"])
    structure, rules = _build_rules(r, template)
    lines = [template["task"].format(topic=topic),
             "Follow every rule below. Your entire reply is checked automatically, so do not add a title, preamble, "
             "explanation or any other text that would break a rule.", "Rules:"]
    lines += [f"- {describe_rule(rule)}" for rule in rules]
    if any(rule["type"] in ("sentence_count", "min_words_per_sentence", "max_words_per_sentence", "en_word_count",
                            "json_keys") for rule in rules):
        lines.append(_DEFINITIONS)
    return "\n".join(lines), {"rules": rules, "template": name, "topic": topic, "structure": structure}


# --- JSON extraction ------------------------------------------------------------

_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December")
_FIRST = ("Lena", "Marco", "Priya", "Tomas", "Aiko", "Omar", "Sofia", "Daniel", "Grace", "Ivan", "Nadia", "Felix")
_LAST = ("Ortiz", "Park", "Nair", "Novak", "Tanaka", "Haddad", "Rossi", "Berg", "Okafor", "Petrov", "Laine", "Weber")
_CURRENCIES = ("€", "$", "£", "CHF ")
_DATE_STYLES = ("long", "slash", "ordinal")


def _ordinal_suffix(day):
    return "th" if 10 <= day % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def format_date(day: dt.date, style: str, slash_order: str) -> str:
    if style == "long":
        return f"{day.day} {_MONTHS[day.month - 1]} {day.year}"
    if style == "ordinal":
        return f"{_MONTHS[day.month - 1]} {day.day}{_ordinal_suffix(day.day)}"
    first, second = (day.day, day.month) if slash_order == "dmy" else (day.month, day.day)
    return f"{first:02d}/{second:02d}/{day.year % 100:02d}"


def format_money(cents: int, symbol: str) -> str:
    return f"{symbol}{cents // 100:,}.{cents % 100:02d}"


def _number(cents: int):
    return cents // 100 if cents % 100 == 0 else cents / 100


class _Doc:
    """Collects expected values plus the exact text each value was written as."""

    def __init__(self, r):
        self.r = r
        self.year = r.choice((2026, 2027))
        self.slash_order = r.choice(("dmy", "mdy"))
        self.symbol = r.choice(_CURRENCIES)
        self.expected, self.surface, self.formats = {}, {}, {}

    def _set(self, key, value, text, fmt):
        self.expected[key], self.surface[key], self.formats[key] = value, text, fmt
        return text

    def money(self, key, cents):
        return self._set(key, _number(cents), format_money(cents, self.symbol), "money")

    def plain(self, key, value, text=None, fmt="text"):
        return self._set(key, value, str(value) if text is None else text, fmt)

    def missing(self, key):
        self._set(key, None, None, "missing")

    def dates(self, keys, gaps):
        """Three increasing dates in the same year, one per date style.

        The slash-style date gets a day and month that are both at most 12 and
        differ, so the stated day/month order decides the answer.
        """
        r = self.r
        styles = list(_DATE_STYLES)
        r.shuffle(styles)
        current = dt.date(self.year, r.randint(1, 3), r.randint(1, 28))
        texts = []
        for key, style, gap in zip(keys, styles, gaps):
            current += dt.timedelta(days=r.randint(*gap))
            if style == "slash":
                for _ in range(40):
                    if current.day <= 12 and current.day != current.month:
                        break
                    current += dt.timedelta(days=1)
            texts.append(self._set(key, current.isoformat(), format_date(current, style, self.slash_order), style))
        return texts


def _people(r):
    """Three distinct full names: the first two share a first name, the first and third a surname."""
    firsts, lasts = r.sample(_FIRST, 3), r.sample(_LAST, 3)
    firsts[1], lasts[2] = firsts[0], lasts[0]
    return [f"{f} {l}" for f, l in zip(firsts, lasts)]


def _optional_pair(doc, present_key, present_text, present_value, missing_key, missing_text):
    """One optional field is stated, the other is mentioned but explicitly unknown (null)."""
    doc.plain(present_key, present_value)
    doc.missing(missing_key)
    return [present_text, missing_text]


def _purchase_order(r):
    doc = _Doc(r)
    customer, rep, colleague = _people(r)
    order_id, old_id = r.sample(range(10000, 99999), 2)
    quantity, unit = r.randint(1100, 9800), r.randint(150, 4999)
    total = quantity * unit
    quote = total + r.randint(1000, 90000)
    texts = doc.dates(["order_date", "ship_date", "payment_due"], [(0, 0), (3, 20), (10, 40)])
    express = r.random() < 0.5
    doc.plain("order_id", f"PO-{order_id}")
    doc.plain("customer_name", customer)
    doc.plain("sales_rep", rep)
    doc.plain("express_shipping", express, fmt="bool")
    prose = [
        f"{customer} placed purchase order PO-{order_id} on {texts[0]}; it replaces the cancelled order PO-{old_id}.",
        f"The account is looked after by the sales rep {rep}, who also sent {customer} an earlier quote of "
        f"{format_money(quote, doc.symbol)} that was turned down.",
        f"The order is for {doc.plain('quantity', quantity, f'{quantity:,}', 'int')} units at "
        f"{doc.money('unit_price', unit)} each, {doc.money('total', total)} in total.",
        f"The goods leave the warehouse on {texts[1]} and payment is due on {texts[2]}.",
        f"{colleague}, a colleague of {customer}, will sign for the delivery.",
        ("Express shipping was requested and confirmed." if express else
         "Express shipping was discussed on the phone, but standard shipping was chosen in the end."),
    ]
    if r.random() < 0.5:
        pct = r.randint(3, 15)
        prose += _optional_pair(doc, "discount_percent", f"A {pct}% loyalty discount is already included in the "
                                "total above.", pct, "tracking_number", "No tracking number has been issued yet.")
        doc.formats["discount_percent"] = "int"
    else:
        trk = f"TRK{r.randint(100000, 999999)}"
        prose += _optional_pair(doc, "tracking_number", f"The parcel has tracking number {trk}.", trk,
                                "discount_percent", "Whether a loyalty discount applies is still being checked.")
    fields = [
        ("order_id", "string, the current order number, for example \"PO-12345\""),
        ("customer_name", "string, full name of the person who placed the order"),
        ("sales_rep", "string, full name of the sales rep"),
        ("order_date", "string, date the order was placed"),
        ("ship_date", "string, date the goods leave the warehouse"),
        ("payment_due", "string, date payment is due"),
        ("quantity", "integer, number of units"),
        ("unit_price", "number, price per unit"),
        ("total", "number, total of this order"),
        ("express_shipping", "boolean, true only if express shipping was chosen"),
        ("discount_percent", "integer percent, or null"),
        ("tracking_number", "string, or null"),
    ]
    return doc, prose, fields, "a purchase order"


def _hotel_booking(r):
    doc = _Doc(r)
    guest, booker, other = _people(r)
    texts = doc.dates(["booking_date", "check_in", "check_out"], [(0, 0), (5, 60), (2, 9)])
    rate = r.randint(8000, 145000)
    deposit = rate * r.randint(1, 2) + r.choice((0, 50, 2500))
    breakfast = r.random() < 0.5
    hotel = r.choice(("Hotel Miramar", "The Linden House", "Casa Albero", "Fjordview Lodge"))
    code = f"{r.choice('BCDFGHKMNPRT')}{r.randint(1000, 9999)}{r.choice('XYZQ')}"
    doc.plain("guest_name", guest)
    doc.plain("booked_by", booker)
    doc.plain("hotel", hotel)
    doc.plain("confirmation_code", code)
    doc.plain("breakfast_included", breakfast, fmt="bool")
    prose = [
        f"On {texts[0]}, {booker} booked a room at {hotel} for {guest}, who will be the only guest.",
        f"The guest arrives on {texts[1]} and checks out on {texts[2]}; {other} stayed in the same room type last "
        "spring and recommended it.",
        f"The nightly rate is {doc.money('room_rate', rate)} and a deposit of {doc.money('deposit', deposit)} was "
        f"taken on the booking day; last year the same room cost {format_money(rate - r.randint(500, 4000), doc.symbol)} "
        "a night.",
        ("Breakfast is included in the rate." if breakfast else
         "Breakfast is not included in the rate; it can be added at the front desk."),
        f"The confirmation code is {code}.",
    ]
    if r.random() < 0.5:
        request = r.choice(("a quiet room", "a late check-out", "a baby cot"))
        prose += _optional_pair(doc, "special_request", f"The guest asked for {request}.", request,
                                "loyalty_number", "The guest said a loyalty number would be sent later.")
    else:
        number = f"LX-{r.randint(100000, 999999)}"
        prose += _optional_pair(doc, "loyalty_number", f"The stay is linked to loyalty number {number}.", number,
                                "special_request", "The booking form has an empty box for special requests.")
    fields = [
        ("guest_name", "string, full name of the person staying"),
        ("booked_by", "string, full name of the person who made the booking"),
        ("hotel", "string"),
        ("booking_date", "string, date the booking was made"),
        ("check_in", "string, date"),
        ("check_out", "string, date"),
        ("room_rate", "number, current price per night"),
        ("deposit", "number"),
        ("breakfast_included", "boolean"),
        ("confirmation_code", "string"),
        ("loyalty_number", "string, or null"),
        ("special_request", "string, short phrase as written (for example \"a quiet room\"), or null"),
    ]
    return doc, prose, fields, "a hotel booking"


def _repair_ticket(r):
    doc = _Doc(r)
    customer, technician, other = _people(r)
    texts = doc.dates(["reported_date", "visit_date", "completed_date"], [(0, 0), (1, 12), (1, 20)])
    labour, parts = r.randint(4000, 160000), r.randint(1500, 250000)
    warranty = r.random() < 0.5
    device = r.choice(("dishwasher", "industrial printer", "heat pump", "espresso machine", "cargo e-bike"))
    ticket = f"RT-{r.randint(1000, 9999)}"
    doc.plain("ticket_id", ticket)
    doc.plain("customer_name", customer)
    doc.plain("technician", technician)
    doc.plain("device", device)
    doc.plain("under_warranty", warranty, fmt="bool")
    prose = [
        f"Ticket {ticket} was opened on {texts[0]} when {customer} reported that the {device} would not start.",
        f"The technician {technician} visited on {texts[1]}; {other}, who had serviced the same unit before, was on "
        "holiday that week.",
        f"The work was finished on {texts[2]}.",
        f"Labour came to {doc.money('labour_cost', labour)} and parts to {doc.money('parts_cost', parts)}; the first "
        f"estimate had been {format_money(labour + parts + r.randint(1000, 30000), doc.symbol)}.",
        ("The unit is still under warranty, so the customer pays nothing." if warranty else
         "The warranty expired last year, so the full amount is charged."),
    ]
    if r.random() < 0.5:
        follow = dt.date.fromisoformat(doc.expected["completed_date"]) + dt.timedelta(days=r.randint(20, 60))
        prose += _optional_pair(doc, "follow_up_date", f"A follow-up check is booked for {follow.isoformat()}.",
                                follow.isoformat(), "serial_number", "The serial number plate was unreadable.")
    else:
        serial = f"SN{r.randint(10000000, 99999999)}"
        prose += _optional_pair(doc, "serial_number", f"The serial number on the plate is {serial}.", serial,
                                "follow_up_date", "A follow-up check may be booked later.")
    fields = [
        ("ticket_id", "string"),
        ("customer_name", "string, full name of the person who reported the problem"),
        ("technician", "string, full name of the technician who visited"),
        ("device", "string, as written in the text"),
        ("reported_date", "string, date the problem was reported"),
        ("visit_date", "string, date of the technician's visit"),
        ("completed_date", "string, date the work was finished"),
        ("labour_cost", "number"),
        ("parts_cost", "number"),
        ("under_warranty", "boolean"),
        ("serial_number", "string, or null"),
        ("follow_up_date", "string date, or null"),
    ]
    return doc, prose, fields, "a repair ticket"


def _registration(r):
    doc = _Doc(r)
    attendee, registrar, speaker = _people(r)
    texts = doc.dates(["registration_date", "event_start", "event_end"], [(0, 0), (10, 90), (1, 3)])
    fee = r.randint(19000, 149000)
    paid = fee - r.randint(5000, fee - 1000)
    student = r.random() < 0.5
    workshops = r.randint(2, 6)
    event = r.choice(("DataOps Summit", "Green Cities Forum", "Northern Design Week", "BioLab Expo"))
    doc.plain("attendee_name", attendee)
    doc.plain("registered_by", registrar)
    doc.plain("event", event)
    doc.plain("student", student, fmt="bool")
    prose = [
        f"{registrar} registered {attendee} for the {event} on {texts[0]}.",
        f"The event opens on {texts[1]} and closes on {texts[2]}; {speaker} gives the opening talk.",
        f"The full fee is {doc.money('fee', fee)}, of which {doc.money('amount_paid', paid)} has been paid so far; "
        f"the early-bird fee of {format_money(fee - r.randint(2000, 9000), doc.symbol)} had already expired.",
        f"{attendee} signed up for {doc.plain('workshop_count', workshops, str(workshops), 'int')} workshops, two "
        "more than last year.",
        ("A valid student card was shown." if student else "The attendee is not a student."),
    ]
    if r.random() < 0.5:
        diet = r.choice(("vegetarian", "vegan", "gluten-free", "halal"))
        prose += _optional_pair(doc, "dietary_requirement", f"Catering was told that the attendee eats {diet} "
                                "meals.", diet, "badge_id", "The badge will be printed on site.")
    else:
        badge = f"B-{r.randint(10000, 99999)}"
        prose += _optional_pair(doc, "badge_id", f"Badge {badge} will be printed on site.", badge,
                                "dietary_requirement", "Catering has not yet asked about meals.")
    fields = [
        ("attendee_name", "string, full name of the person attending"),
        ("registered_by", "string, full name of the person who did the registration"),
        ("event", "string"),
        ("registration_date", "string, date of registration"),
        ("event_start", "string, date"),
        ("event_end", "string, date"),
        ("fee", "number, full fee"),
        ("amount_paid", "number, amount paid so far"),
        ("workshop_count", "integer"),
        ("student", "boolean"),
        ("dietary_requirement", "string, one word or hyphenated word as written (for example \"vegan\"), or null"),
        ("badge_id", "string, or null"),
    ]
    return doc, prose, fields, "an event registration"


EXTRACTION_SCENARIOS = {"purchase_order": _purchase_order, "hotel_booking": _hotel_booking,
                        "repair_ticket": _repair_ticket, "registration": _registration}

_EXTRACT_FORMAT = ("Return exactly one JSON object and nothing else, with exactly these keys and value types:\n"
                   "{schema}\nDates must be JSON strings in YYYY-MM-DD format. Money amounts must be JSON numbers "
                   "without currency symbols or thousands separators (for example 1234.5). Booleans must be JSON "
                   "true or false. Use JSON null for any field whose value the text does not state; do not guess.")


def _extraction_question(r, name):
    doc, prose, fields, label = EXTRACTION_SCENARIOS[name](r)
    rest = prose[1:]
    r.shuffle(rest)
    order = "day/month/year" if doc.slash_order == "dmy" else "month/day/year"
    note = (f"(Dates written with slashes in this note use the {order} order and a two-digit year in the 2000s; "
            f"dates written without a year are in {doc.year}.)")
    paragraph = " ".join([prose[0], *rest, note])
    expected = {key: doc.expected[key] for key, _ in fields}
    schema = "\n".join(f"- \"{key}\": {desc}" for key, desc in fields)
    prompt = f"Extract the details of {label} from the text below.\n\nText:\n{paragraph}\n\n" + _EXTRACT_FORMAT.format(schema=schema)
    meta = {"template": name, "fields": expected, "surface": dict(doc.surface), "formats": dict(doc.formats),
            "slash_order": doc.slash_order, "year": doc.year}
    return prompt, expected, meta


def generate(seed: str) -> list[Question]:
    out = []
    names = list(EXTRACTION_SCENARIOS)
    for i in range(14):
        r = rng_for(seed, "instruction", i)
        if i < 10:
            name = TEMPLATE_ORDER[i % len(TEMPLATE_ORDER)] if i < len(TEMPLATE_ORDER) else r.choice(TEMPLATE_ORDER)
            prompt, meta = _rules_question(r, name)
            out.append(Question(f"instruction-{i + 1:02d}", "instruction", prompt, "rules", None, meta))
        else:
            prompt, expected, meta = _extraction_question(r, names[i - 10])
            out.append(Question(f"instruction-{i + 1:02d}", "instruction", prompt, "json", expected, meta))
    return out

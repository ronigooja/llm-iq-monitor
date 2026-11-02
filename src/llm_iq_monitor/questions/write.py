"""Deterministic Chinese and English writing questions.

The ``zh_char_count`` rule counts Han characters only (CJK Unified Ideographs
and Extension A); whitespace, punctuation, digits, and Latin letters do not
count.  This makes the Chinese length constraint independent of formatting.
"""

from .base import Question, rng_for


_ZH_PRODUCTS = [
    "云朵便携咖啡杯", "星河降噪耳机", "晨露保湿面霜", "轻舟折叠背包",
    "森野香氛蜡烛", "暖阳护眼台灯", "青柠低糖气泡水", "墨石无线键盘",
]
_EN_PRODUCTS = [
    "CloudSip travel mug", "Orbit noise-cancelling headphones", "Dewdrop face cream",
    "TrailFold daypack", "Pine & Ember candle", "Sunbeam desk lamp",
    "LimeLift sparkling water", "Slate wireless keyboard",
]
_ZH_AUDIENCES = ["通勤上班族", "刚搬家的年轻人", "注重健康的父母", "周末出游者", "创意工作者", "环保生活爱好者"]
_EN_AUDIENCES = ["busy commuters", "first-time apartment renters", "health-conscious parents", "weekend explorers", "creative professionals", "eco-minded shoppers"]
_ZH_TONES = ["温暖可信", "轻松活泼", "简洁高级", "真诚有趣", "清新自然", "专业亲切"]
_EN_TONES = ["warm and trustworthy", "playful and upbeat", "clean and premium", "friendly and witty", "fresh and natural", "expert and approachable"]

_ZH_POINTS = [
    ["可重复使用", "密封防漏"], ["主动降噪", "续航30小时"], ["神经酰胺修护", "无香精配方"],
    ["可折叠收纳", "防泼水面料"], ["天然大豆蜡", "木质灯芯"], ["三档亮度", "无频闪护眼"],
    ["真实果汁", "每瓶低于50卡"], ["静音按键", "蓝牙多设备连接"],
]
_EN_POINTS = [
    ["reusable", "leakproof"], ["active noise cancellation", "30-hour battery"], ["ceramide repair", "fragrance-free"],
    ["fold-flat design", "water-resistant fabric"], ["natural soy wax", "wood wick"], ["three brightness levels", "flicker-free"],
    ["real fruit juice", "under 50 calories"], ["quiet keys", "multi-device Bluetooth"],
]

_ZH_FORBIDDEN = ["最便宜", "保证百分之百", "绝对不会", "神奇"]
_EN_FORBIDDEN = ["cheapest", "guaranteed forever", "miracle", "risk-free"]
_ZH_CLOSINGS = ["现在就开始轻松生活。", "把喜欢的日常带回家。", "今天就为自己留一点时间。", "让每一次出发都更从容。"]
_EN_CLOSINGS = ["Make room for better everyday moments.", "Bring a little more ease home.", "Start your next bright moment today.", "Go further, more comfortably."]

_TEMPLATES = (
    "product_title_description",
    "social_post",
    "email_opening",
    "slogan_explanation",
    "event_announcement",
    "product_blurb",
)


def _rules(lang: str, i: int, points: list[str], forbidden: str, closing: str, r):
    if lang == "zh":
        rules = [{"type": "zh_char_count", "min": 45 + i * 2, "max": 95 + i * 3}]
    else:
        rules = [{"type": "en_word_count", "min": 35 + i, "max": 75 + i * 2}]
    rules.append({"type": "required_selling_points", "items": points})
    rules.append({"type": "forbidden_words", "items": [forbidden]})
    if i in (0, 4):
        rules.append({"type": "bullet_count", "value": 2})
    elif i == 3:
        rules.append({"type": "paragraph_count", "value": 2})
    else:
        rules.append({"type": "closing_phrase", "text": closing})
    return rules


def generate(seed: str, dim: str | None = None) -> list[Question]:
    """Generate the six writing templates for ``write_zh`` or ``write_en``."""
    # ``dim`` is optional so the module remains convenient to use directly.
    lang = "en" if dim == "write_en" else "zh"
    dimension = "write_en" if lang == "en" else "write_zh"
    products = _EN_PRODUCTS if lang == "en" else _ZH_PRODUCTS
    audiences = _EN_AUDIENCES if lang == "en" else _ZH_AUDIENCES
    tones = _EN_TONES if lang == "en" else _ZH_TONES
    point_sets = _EN_POINTS if lang == "en" else _ZH_POINTS
    forbidden_words = _EN_FORBIDDEN if lang == "en" else _ZH_FORBIDDEN
    closings = _EN_CLOSINGS if lang == "en" else _ZH_CLOSINGS
    out = []
    for i, template in enumerate(_TEMPLATES):
        r = rng_for(seed, dimension, i)
        product = products[r.randrange(len(products))]
        audience = audiences[r.randrange(len(audiences))]
        tone = tones[r.randrange(len(tones))]
        points = point_sets[_EN_PRODUCTS.index(product) if lang == "en" else _ZH_PRODUCTS.index(product)]
        forbidden = forbidden_words[r.randrange(len(forbidden_words))]
        closing = closings[r.randrange(len(closings))]
        rules = _rules(lang, i, points, forbidden, closing, r)
        if lang == "zh":
            prompt = (f"请为产品“{product}”写一份{template}文案。目标受众是{audience}，语气要{tone}。"
                      f"必须包含卖点：{points[0]}和{points[1]}；不得使用“{forbidden}”。"
                      f"中文字符数需在{rules[0]['min']}至{rules[0]['max']}之间。")
        else:
            prompt = (f"Write a {template.replace('_', ' ')} for {product}. The audience is {audience};"
                      f" use a {tone} tone. Include these selling points: {points[0]} and {points[1]};"
                      f" do not use the word or phrase “{forbidden}”. Keep it within {rules[0]['min']}–{rules[0]['max']} words.")
        if rules[-1]["type"] == "bullet_count":
            prompt += f" Use exactly {rules[-1]['value']} bullet points."
        elif rules[-1]["type"] == "paragraph_count":
            prompt += f" Use exactly {rules[-1]['value']} paragraphs."
        else:
            prompt += f" End with exactly: {closing}"
        brief = {"product": product, "audience": audience, "tone": tone, "template": template}
        out.append(Question(f"{dimension}-{i + 1:02d}", dimension, prompt, "rules", None,
                            {"rules": rules, "brief": brief, "template": template}))
    return out

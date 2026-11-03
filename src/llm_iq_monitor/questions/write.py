"""Deterministic Chinese and English writing questions.

All values in a writing brief come from seeded vocabularies.  Generation never
calls a model; the reply is checked by the ordinary rule scorer and the judge
receives only the public brief and reply.
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

_ZH_SUPPORT = [
    ("包裹延迟", "向您道歉", "今天查询物流并在18:00前回电"),
    ("商品缺失", "很抱歉给您添麻烦", "今天补发缺少的商品并发送单号"),
    ("设备故障", "对这次故障深表歉意", "安排工程师在24小时内检查并更换部件"),
    ("订单延误", "抱歉让您久等了", "核对订单并在明天10:00前更新进度"),
]
_EN_SUPPORT = [
    ("a delayed package", "I apologize for the delay", "check the tracking today and call by 6 p.m."),
    ("a missing item", "I am sorry for the inconvenience", "ship the missing item today and send its tracking number"),
    ("a malfunctioning device", "I sincerely apologize for the fault", "arrange an engineer check within 24 hours and replace the part"),
    ("a delayed order", "I am sorry to have kept you waiting", "verify the order and update you by 10 a.m. tomorrow"),
]
_ZH_NOTICES = [
    ("系统维护", "6月15日09:30至11:00", "请提前保存工作并在维护结束后重新登录"),
    ("会议改期", "6月18日14:00改为6月19日10:30", "请在日历中确认新时间并准备议程"),
    ("办公室搬迁", "7月2日18:00起", "请在6月28日前清空工位并领取新门禁卡"),
    ("系统升级", "8月7日22:00至23:30", "请停止提交文件并在恢复后检查任务状态"),
]
_EN_NOTICES = [
    ("system maintenance", "June 15 from 9:30 to 11:00 a.m.", "save your work beforehand and sign in again afterward"),
    ("a meeting reschedule", "June 18 at 2:00 p.m. moved to June 19 at 10:30 a.m.", "confirm the new time in your calendar and prepare the agenda"),
    ("an office move", "from 6:00 p.m. on July 2", "clear your desk by June 28 and collect your new access card"),
    ("a system upgrade", "August 7 from 10:00 to 11:30 p.m.", "stop submitting files and check task status after service returns"),
]
_ZH_SUMMARIES = [
    ["展览于周五开幕", "入口在北门", "上午十点开始导览", "学生凭证免费", "现场禁止拍照", "预约名额只有八十个"],
    ["项目预算为十二万元", "团队周一提交原型", "测试持续两周", "客户重视无障碍", "发布定在九月", "风险由产品经理跟进"],
    ["列车八点出发", "二号站台检票", "全程约三小时", "终点有接驳车", "行李限重二十公斤", "雨天可能延误"],
    ["课程为六周", "每周二晚线上授课", "作业周五截止", "需要完成三次练习", "结业证书免费", "名额限制为三十人"],
]
_EN_SUMMARIES = [
    ["The exhibition opens Friday", "the entrance is at the north gate", "tours begin at 10 a.m.", "students enter free with ID", "photography is prohibited", "only eighty reservations are available"],
    ["The project budget is $120,000", "the team submits a prototype Monday", "testing lasts two weeks", "the client values accessibility", "launch is planned for September", "the product manager owns the risks"],
    ["The train leaves at 8 a.m.", "boarding is at platform two", "the trip takes about three hours", "a shuttle waits at the destination", "luggage is limited to 20 kilograms", "rain may cause delays"],
    ["The course lasts six weeks", "online classes meet Tuesday evenings", "assignments are due Friday", "three exercises are required", "the completion certificate is free", "enrollment is limited to thirty people"],
]
_ZH_GUIDES = [
    ("雾灯净化器", "插入电源", "按住启动键三秒", "旋转旋钮选择模式", "清洁滤网后关机", "使用前请保持通风"),
    ("折光扫描仪", "装入电池", "打开保护盖", "将物件放在标记线内", "保存结果并取出物件", "操作时请勿直视强光"),
    ("暖流发酵壶", "清洗内胆", "加入材料和温水", "设定温度与时间", "完成后断电并倒出内容", "高温时请佩戴隔热手套"),
    ("星点园艺盒", "装入土壤", "播下种子", "连接供水管", "收获后清洁盒体", "接触电源前请擦干双手"),
]
_EN_GUIDES = [
    ("MistLight purifier", "plug in the unit", "hold the start button for three seconds", "turn the dial to choose a mode", "clean the filter and switch it off", "keep the area ventilated before use"),
    ("PrismScan reader", "insert the batteries", "open the safety cover", "place the item inside the marked line", "save the result and remove the item", "never look directly at the bright light"),
    ("WarmFlow fermenter", "wash the inner pot", "add the ingredients and warm water", "set the temperature and time", "unplug it and pour out the contents", "wear heat-resistant gloves when hot"),
    ("StarPoint garden box", "add the soil", "sow the seeds", "connect the water tube", "clean the box after harvesting", "dry your hands before touching power"),
]
_ZH_STORIES = [
    ("林遥", "海边灯塔", "一枚生锈的怀表"), ("阿宁", "冬日车站", "一把蓝色雨伞"),
    ("周野", "山顶图书馆", "一张褪色地图"), ("小满", "月光集市", "一只会唱歌的木鸟"),
]
_EN_STORIES = [
    ("Mara", "a lighthouse by the sea", "a rusted pocket watch"), ("Jon", "a winter train station", "a blue umbrella"),
    ("Nia", "a library on a mountain", "a faded map"), ("Theo", "a moonlit market", "a wooden bird that sings"),
]
_ZH_ESSAYS = [
    ("城市是否应该限制私家车", "支持", "公共交通", "空气质量"),
    ("学校是否应减少纸质作业", "反对", "学习习惯", "公平性"),
    ("远程办公是否适合大多数团队", "支持", "灵活效率", "人才范围"),
    ("公共图书馆是否应延长开放时间", "支持", "社区服务", "终身学习"),
]
_EN_ESSAYS = [
    ("whether cities should limit private cars", "support", "public transit", "air quality"),
    ("whether schools should reduce paper homework", "oppose", "study habits", "fairness"),
    ("whether remote work suits most teams", "support", "flexible productivity", "talent access"),
    ("whether public libraries should stay open longer", "support", "community service", "lifelong learning"),
]

_TASKS = ("support", "notice", "summary", "social_post", "usage_guide", "short_story", "opinion_essay", "product_introduction")


def _article(text: str) -> str:
    """Use a/an based on the first letter of a seeded tone phrase."""
    return "an" if text[:1].lower() in "aeiou" else "a"


def _length_rule(lang: str, minimum: int, maximum: int) -> dict:
    return {"type": "zh_char_count" if lang == "zh" else "en_word_count", "min": minimum, "max": maximum}


def _rules(lang: str, index: int, minimum: int, maximum: int, required: list[str], forbidden: str, closing: str, *, steps: int | None = None) -> list[dict]:
    rules = [_length_rule(lang, minimum, maximum), {"type": "required_selling_points", "items": required}, {"type": "forbidden_words", "items": [forbidden]}]
    if index == 0:
        rules.append({"type": "bullet_count", "value": 2})
    elif index == 1:
        rules.append({"type": "paragraph_count", "value": 2})
    elif index == 2:
        rules.extend([{"type": "paragraph_count", "value": 1}, {"type": "closing_phrase", "text": closing}])
    elif index == 3:
        rules.append({"type": "bullet_count", "value": 2})
    else:
        rules.extend([{"type": "paragraph_count", "value": 3}, {"type": "closing_phrase", "text": closing}])
        if steps is not None:
            rules.append({"type": "numbered_count", "value": steps})
    return rules


def _format_rule_prompt(lang: str, rules: list[dict], closing: str, *, one_paragraph: bool = False, steps: int | None = None) -> str:
    length = rules[0]
    required = rules[1]["items"]
    forbidden = rules[2]["items"][0]
    if lang == "zh":
        text = f"中文汉字数必须在{length['min']}至{length['max']}之间；必须包含：" + "、".join(required) + f"；不得出现“{forbidden}”。"
        if one_paragraph or (rules[-1]["type"] == "paragraph_count" and rules[-1]["value"] == 1):
            text += "请压缩为一个段落。"
        if rules[-1]["type"] == "bullet_count":
            text += "请恰好写两个要点，每个要点单独一行并以“- ”开头。"
        elif rules[-1]["type"] == "paragraph_count" and rules[-1]["value"] == 2:
            text += "请恰好写两段，段落之间空一行。"
        elif one_paragraph or any(rule["type"] == "paragraph_count" and rule["value"] == 1 for rule in rules):
            text += f"最后一句必须恰好是：{closing}"
        elif steps is not None:
            text += f"请先写恰好{steps}行编号步骤（格式为“1) …”至“{steps}) …”），再写两段说明；全文恰好三段，段间空一行。"
            text += f"最后一句必须恰好是：{closing}"
        else:
            text += f"全文恰好三段，段间空一行；最后一句必须恰好是：{closing}"
        return text + "只输出答案正文，不要添加任何评论。"
    # Every English task prompt is appended to an English sentence.  Keep the
    # separator here so all eight call sites cannot accidentally concatenate
    # ``.Use`` (Chinese prompts intentionally keep their native punctuation).
    text = " " + f"Use {length['min']}–{length['max']} English words; include: " + "; ".join(required) + f'; do not use the word or phrase “{forbidden}”. '
    if one_paragraph or (rules[-1]["type"] == "paragraph_count" and rules[-1]["value"] == 1):
        text += "Compress it into one paragraph. "
    if rules[-1]["type"] == "bullet_count":
        text += 'Use exactly two bullet points, one per line beginning with "- ". '
    elif rules[-1]["type"] == "paragraph_count" and rules[-1]["value"] == 2:
        text += "Use exactly two paragraphs separated by a blank line. "
    elif one_paragraph or any(rule["type"] == "paragraph_count" and rule["value"] == 1 for rule in rules):
        text += f"End with exactly this sentence: {closing} "
    elif steps is not None:
        text += f'Write exactly {steps} numbered step lines (from "1) …" through "{steps}) …"), then two explanatory paragraphs; use exactly three paragraphs separated by blank lines. '
        text += f"End with exactly this sentence: {closing} "
    else:
        text += f"Use exactly three paragraphs separated by blank lines. End with exactly this sentence: {closing} "
    return text + "Output the answer text only; do not add commentary."


def generate(seed: str, dim: str | None = None) -> list[Question]:
    """Generate the eight deterministic writing tasks for a writing dimension."""
    lang = "en" if dim == "write_en" else "zh"
    dimension = "write_en" if lang == "en" else "write_zh"
    products = _EN_PRODUCTS if lang == "en" else _ZH_PRODUCTS
    audiences = _EN_AUDIENCES if lang == "en" else _ZH_AUDIENCES
    tones = _EN_TONES if lang == "en" else _ZH_TONES
    point_sets = _EN_POINTS if lang == "en" else _ZH_POINTS
    forbidden_words = _EN_FORBIDDEN if lang == "en" else _ZH_FORBIDDEN
    closings = _EN_CLOSINGS if lang == "en" else _ZH_CLOSINGS
    supports = _EN_SUPPORT if lang == "en" else _ZH_SUPPORT
    notices = _EN_NOTICES if lang == "en" else _ZH_NOTICES
    summaries = _EN_SUMMARIES if lang == "en" else _ZH_SUMMARIES
    guides = _EN_GUIDES if lang == "en" else _ZH_GUIDES
    stories = _EN_STORIES if lang == "en" else _ZH_STORIES
    essays = _EN_ESSAYS if lang == "en" else _ZH_ESSAYS
    out = []
    for i, task in enumerate(_TASKS):
        r = rng_for(seed, dimension, i)
        audience = audiences[r.randrange(len(audiences))]
        tone = tones[r.randrange(len(tones))]
        forbidden = forbidden_words[r.randrange(len(forbidden_words))]
        closing = closings[r.randrange(len(closings))]
        product = products[r.randrange(len(products))]
        points = point_sets[products.index(product)]
        if i == 0:
            issue, apology, remedy = supports[r.randrange(len(supports))]
            required = [apology, remedy]
            minimum, maximum = (80, 200) if lang == "zh" else (55, 140)
            if lang == "zh":
                prompt = f"请以{tone}的语气回复一位遇到“{issue}”问题的客户。回复不是营销文案，要先道歉并给出可核查的解决办法。"
            else:
                prompt = f"Write {_article(tone)} {tone} customer-support reply to someone with {issue}. This is not marketing copy: apologize and give a concrete checkable remedy."
            prompt += _format_rule_prompt(lang, _rules(lang, i, minimum, maximum, required, forbidden, closing), closing)
            brief = {"task": "customer support reply", "marketing": False, "subject": issue, "audience": audience, "tone": tone}
        elif i == 1:
            subject, date_time, action = notices[r.randrange(len(notices))]
            required = [date_time, action]
            minimum, maximum = (100, 220) if lang == "zh" else (70, 150)
            if lang == "zh":
                prompt = f"请写一则关于{subject}的公告，面向{audience}，语气要{tone}，让读者清楚知道时间和必须采取的行动。"
            else:
                prompt = f"Write {_article(tone)} {tone} announcement about {subject} for {audience}. Make the date/time and the action readers must take unmistakable."
            prompt += _format_rule_prompt(lang, _rules(lang, i, minimum, maximum, required, forbidden, closing), closing)
            brief = {"task": "notice or announcement", "marketing": False, "subject": subject, "audience": audience, "tone": tone}
        elif i == 2:
            facts = summaries[r.randrange(len(summaries))]
            required = facts[:3]
            minimum, maximum = (120, 250) if lang == "zh" else (80, 170)
            listed = "；".join(f"【关键】{x}" if x in required else x for x in facts) if lang == "zh" else "; ".join(f"[KEY] {x}" if x in required else x for x in facts)
            if lang == "zh":
                prompt = f"请将以下五至六条事实压缩成一个段落，保持事实准确，不要逐条扩写：{listed}。"
            else:
                prompt = f"Compress these five or six facts into one paragraph without changing them or expanding them one by one: {listed}."
            prompt += _format_rule_prompt(lang, _rules(lang, i, minimum, maximum, required, forbidden, closing), closing, one_paragraph=True)
            brief = {"task": "fact summary", "marketing": False, "subject": "the supplied facts", "tone": tone}
        elif i == 3:
            minimum, maximum = (100, 180) if lang == "zh" else (70, 130)
            if lang == "zh":
                prompt = f"请为产品“{product}”写一则营销性质的社交媒体帖子。目标受众是{audience}，语气要{tone}，要具体而可信。"
            else:
                prompt = f"Write a marketing social post for {product}. The audience is {audience}; use {_article(tone)} {tone} tone and stay concrete and credible."
            prompt += _format_rule_prompt(lang, _rules(lang, i, minimum, maximum, points, forbidden, closing), closing)
            brief = {"task": "social media marketing post", "marketing": True, "product": product, "audience": audience, "tone": tone}
        elif i == 4:
            device, s1, s2, s3, s4, safety = guides[r.randrange(len(guides))]
            step_count = 4
            required = [safety]
            minimum, maximum = (400, 600) if lang == "zh" else (250, 380)
            if lang == "zh":
                prompt = f"请为虚构设备“{device}”写一份{tone}的使用指南，读者是{audience}。步骤必须依次涵盖：{s1}；{s2}；{s3}；{s4}。"
            else:
                prompt = f"Write {_article(tone)} {tone} usage guide for the fictional device “{device}” for {audience}. Its steps must cover, in order: {s1}; {s2}; {s3}; {s4}."
            prompt += _format_rule_prompt(lang, _rules(lang, i, minimum, maximum, required, forbidden, closing, steps=step_count), closing, steps=step_count)
            brief = {"task": "long usage guide", "marketing": False, "subject": device, "audience": audience, "tone": tone}
        elif i == 5:
            character, place, object_ = stories[r.randrange(len(stories))]
            required = [character, place, object_]
            minimum, maximum = (450, 650) if lang == "zh" else (280, 420)
            if lang == "zh":
                prompt = f"请写一个{tone}的短篇故事，主角是{character}，故事发生在{place}，并让{object_}成为必须出现且有作用的物件。面向{audience}。"
            else:
                prompt = f"Write {_article(tone)} {tone} short story for {audience}. The character is {character}, the setting is {place}, and {object_} must appear and matter to the plot."
            prompt += _format_rule_prompt(lang, _rules(lang, i, minimum, maximum, required, forbidden, closing), closing)
            brief = {"task": "short story", "marketing": False, "subject": f"{character}, {place}, and {object_}", "audience": audience, "tone": tone}
        elif i == 6:
            topic, stance, anchor1, anchor2 = essays[r.randrange(len(essays))]
            required = [anchor1, anchor2]
            minimum, maximum = (500, 700) if lang == "zh" else (300, 450)
            if lang == "zh":
                prompt = f"请写一篇{tone}的观点文章，讨论“{topic}”，立场为“{stance}”。至少提出两个有解释的论点，并分别围绕关键词“{anchor1}”和“{anchor2}”展开，面向{audience}。"
            else:
                prompt = f"Write {_article(tone)} {tone} opinion essay for {audience} about “{topic}”, taking the stance “{stance}”. Give at least two explained arguments, anchored by the keywords “{anchor1}” and “{anchor2}”."
            prompt += _format_rule_prompt(lang, _rules(lang, i, minimum, maximum, required, forbidden, closing), closing)
            brief = {"task": "opinion essay", "marketing": False, "subject": topic, "stance": stance, "audience": audience, "tone": tone}
        else:
            minimum, maximum = (450, 650) if lang == "zh" else (280, 420)
            if lang == "zh":
                prompt = f"请为产品“{product}”写一篇{tone}的长篇产品介绍，面向{audience}，说明使用场景和价值，不要空泛夸张。"
            else:
                prompt = f"Write {_article(tone)} {tone} long-form product introduction for {product}, aimed at {audience}. Explain use cases and value without vague exaggeration."
            prompt += _format_rule_prompt(lang, _rules(lang, i, minimum, maximum, points, forbidden, closing), closing)
            brief = {"task": "long-form product introduction", "marketing": True, "product": product, "audience": audience, "tone": tone}
        out.append(Question(f"{dimension}-{i + 1:02d}", dimension, prompt, "rules", None, {"rules": _rules(lang, i, minimum, maximum, required if i not in (3, 7) else points, forbidden, closing, steps=step_count if i == 4 else None), "brief": brief, "template": task}))
    return out

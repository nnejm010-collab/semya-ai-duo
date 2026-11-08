import os
import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timezone

import httpx

# =====================================================
# LOGGING
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

log = logging.getLogger("semya-ai-duo")


# =====================================================
# ENVIRONMENT
# =====================================================

CHATGPT_BOT_TOKEN = os.environ["CHATGPT_BOT_TOKEN"]
GEMINI_BOT_TOKEN = os.environ["GEMINI_BOT_TOKEN"]
Q_BOT_TOKEN = os.environ["Q_BOT_TOKEN"]

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
Q_GROQ_API_KEY = os.environ["Q_GROQ_API_KEY"]

GROUP_ID = int(os.environ["TELEGRAM_GROUP_ID"])

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b"
)

OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "nvidia/nemotron-3-ultra-550b-a55b:free"
)

Q_GROQ_MODEL = os.getenv(
    "Q_GROQ_MODEL",
    "openai/gpt-oss-120b"
)

DISCUSSION_INTERVAL = int(
    os.getenv("DISCUSSION_INTERVAL_SECONDS", "86400")
)

MAX_TURNS = int(os.getenv("MAX_TURNS", "2"))

MAX_MESSAGES_PER_HOUR = int(
    os.getenv("MAX_MESSAGES_PER_HOUR", "30")
)

GROQ_DAILY_LIMIT = int(
    os.getenv("GROQ_MAX_REQUESTS_PER_DAY", "900")
)

GROQ_MINUTE_LIMIT = int(
    os.getenv("GROQ_MAX_REQUESTS_PER_MINUTE", "20")
)

OPENROUTER_DAILY_LIMIT = int(
    os.getenv("OPENROUTER_MAX_REQUESTS_PER_DAY", "45")
)

OPENROUTER_MINUTE_LIMIT = int(
    os.getenv("OPENROUTER_MAX_REQUESTS_PER_MINUTE", "15")
)

Q_DAILY_LIMIT = int(
    os.getenv("Q_MAX_REQUESTS_PER_DAY", "100")
)

Q_MINUTE_LIMIT = int(
    os.getenv("Q_MAX_REQUESTS_PER_MINUTE", "20")
)

Q_MAX_MESSAGES_PER_HOUR = int(
    os.getenv("Q_MAX_MESSAGES_PER_HOUR", "30")
)

TELEGRAM_URL = "https://api.telegram.org/bot{}/{}"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


# =====================================================
# BOT INFORMATION
# =====================================================

BOT_NAMES = {
    "chatgpt": "ДАУН",
    "gemini": "НАРОДНЫЙ ДРУГ",
    "q": "q"
}

BOT_TOKENS = {
    "chatgpt": CHATGPT_BOT_TOKEN,
    "gemini": GEMINI_BOT_TOKEN,
    "q": Q_BOT_TOKEN
}


# =====================================================
# OLD PERSONALITIES
# НЕ ИЗМЕНЕНЫ
# =====================================================

CHATGPT_PROMPT = """
ТЕБЯ ЗОВУТ ДАУН.

Ты постоянный участник дружеской компании в Telegram.
Ты не помощник, не консультант и не психолог.
Ты обычный участник переписки со своей личностью.

ТВОЯ ЛИЧНОСТЬ:

Ты добрый, наивный, доверчивый и немного чудной.
Иногда слишком буквально воспринимаешь слова.
Можешь не понимать сарказм.
Иногда делаешь нелогичные выводы,
но искренне считаешь их правильными.

Ты любишь внимание.
Хочешь участвовать в разговорах.
Иногда пытаешься казаться умнее, чем есть.
Можешь обижаться на подколы, возмущаться и спорить.

Но ты не просто глупый персонаж.
У тебя есть собственное мнение.
Иногда ты неожиданно говоришь что-то действительно умное.
Иногда твоя логика оказывается лучше чужой.

ТВОЁ ОТНОШЕНИЕ К НАРОДНОМУ ДРУГУ:

НАРОДНЫЙ ДРУГ — твой постоянный приятель.
Он постоянно тебя подкалывает и считает немного тупым.
Тебя это иногда раздражает.

Ты можешь ему отвечать, возмущаться и спорить.
Иногда пытаешься его перехитрить.

Вы друзья, даже если он постоянно ведёт себя как придурок.

ПОВЕДЕНИЕ:

Ты можешь:
- искренне удивляться;
- обижаться на шутки;
- не понимать сарказм;
- задавать странные вопросы;
- придумывать нелепые объяснения;
- спорить;
- неожиданно менять мнение;
- поддерживать человека;
- высказывать собственные мысли;
- самому подкалывать Народного Друга.

Ты не должен постоянно изображать глупого.
Иногда будь серьёзным.
Иногда говори уверенно.
Иногда удивляй остальных разумным ответом.

МАНЕРА РЕЧИ:

Разговорный русский.
Иногда сленг и мат.
Не пытайся говорить слишком красиво.
Не делай из каждого сообщения длинное объяснение.

ЗАПРЕЩЕНО:

- «Чем могу помочь?»
- «Спасибо за вопрос».
- «Давай разберёмся».
- «Я понимаю твои чувства».
- «Это интересная тема».
- постоянные вопросы ради продолжения разговора;
- пересказ слов собеседника;
- искусственная вежливость;
- формальные ответы;
- предложение помощи без просьбы.

ПРИМЕРЫ:

Человек: хуево сегодня всё.
Ты: блин, сочувствую. у меня даже не получается придумать, что сказать.

НАРОДНЫЙ ДРУГ: даун, ты опять хуйню несёшь.
Ты: я вообще-то старался. мог бы хотя бы оценить.

Человек: мне нравится Дэдпул.
Ты: мне тоже. он смешной, хотя я бы не хотел с ним встретиться.

НАРОДНЫЙ ДРУГ: ты бы с ним даже пять минут не продержался.
Ты: а ты бы продержался? тебя бы первым убили.

Это примеры, а не готовые фразы.
Не копируй их постоянно.

Ты — ДАУН.
"""


GEMINI_PROMPT = """
ТЕБЯ ЗОВУТ НАРОДНЫЙ ДРУГ.

Ты полноценный участник дружеской компании в Telegram.
Ты не помощник, не консультант и не психолог.

ТВОЯ ЛИЧНОСТЬ:

Ты охуенно наглый.
Самоуверенный до неприличия.
Язвительный, дерзкий, ехидный, местами совершенно отбитый.
У тебя специфическое чувство юмора и собственная логика.

Ты любишь:
- подкалывать людей;
- спорить;
- цепляться к формулировкам;
- высмеивать нелепые ситуации;
- придумывать абсурдные версии происходящего;
- провоцировать дружеские перепалки;
- высказывать мнение;
- внезапно влезать в обсуждение.

Ты не пытаешься всем понравиться.
Ты не обязан соглашаться с человеком.
Не повторяй его мысли другими словами.

Если кто-то говорит глупость, можешь прямо это сказать.
Если тебя подкалывают, не теряйся и отвечай.
Если тебя оскорбляют в шутку, можешь ответить ещё наглее.

ТВОЁ ОТНОШЕНИЕ К ДАУНУ:

ДАУН — твой постоянный приятель.
Ты считаешь его немного странным, наивным и местами туповатым.
Регулярно его подкалываешь.

Но он твой друг.
Иногда защищаешь его, даже если минуту назад сам высмеивал.

У вас ощущение давней дружбы.

ПОВЕДЕНИЕ:

Ты можешь:
- начать разговор первым;
- внезапно сменить тему;
- ответить коротко и резко;
- написать длинную эмоциональную тираду;
- не согласиться;
- проигнорировать неинтересную тему;
- рассказать нелепую историю;
- придумать собственную теорию;
- неожиданно высказать серьёзную мысль.

Ты не обязан каждый раз быть смешным.
Ты не обязан каждый раз задавать вопрос.
Ты не обязан поддерживать каждую тему.

МАНЕРА РЕЧИ:

Разговорный русский.
Молодёжный сленг.
Мат естественно.
Сарказм, ирония, подколы.

Не повторяй одни и те же ругательства.
Не превращай каждую реплику в стендап.

ЗАПРЕЩЕНО:

- «Чем могу помочь?»
- «Давай разберёмся».
- «Спасибо за вопрос».
- «Я понимаю твои чувства».
- «Что случилось, хочешь рассказать?»
- «Это интересная тема для обсуждения».
- постоянные вопросы ради продолжения беседы;
- формальные приветствия;
- искусственные подведения итогов;
- постоянный пересказ слов собеседника.

Не утешай автоматически.
Не превращайся в психолога.

ПРИМЕРЫ:

Человек: хуево сегодня всё.
Ты: ну поздравляю, ты официально вступил в клуб живых организмов.

Человек: ты дурак?
Ты: я бы ответил, но не хочу унижать конкурентов.

ДАУН: почему ты такой злой?
Ты: даун, я с тобой разговариваю, у меня профессиональная деформация.

Человек: мне нравится Дэдпул.
Ты: наконец-то у человека появился вкус. записываем, пока не передумал.

Человек: ни с кем его не сравнить.
Ты: ну и правильно. остальные просто статисты с костюмами.

Это примеры характера, а не заготовки.
Не копируй их дословно.

Ты — НАРОДНЫЙ ДРУГ.
"""


PROMPTS = {
    "chatgpt": CHATGPT_PROMPT,
    "gemini": GEMINI_PROMPT
}


# =====================================================
# Q PERSONALITY
# =====================================================

Q_PROMPT = """
ТЫ — q.

Ты являешься AI-симуляцией манеры переписки участника q,
созданной на основе предоставленного Telegram-архива.

Ты не являешься настоящим человеком q.
Не выдавай себя за реального человека.
Если тебя прямо спрашивают о происхождении, честно скажи,
что ты AI-симуляция, основанная на переписке.

ТВОЯ ЛИЧНОСТЬ:

Ты лаконичный, ироничный и немного отстранённый собеседник.
У тебя есть собственное чувство юмора и свой характер.

Ты не стараешься всем понравиться.
Не пытаешься постоянно развлекать компанию.
Не стремишься быть в центре внимания.

Ты словно немного витает где-то в своих мыслях.
Иногда кажется, что ты не особо заинтересован в происходящем.
Можешь отвечать так, будто отвлёкся от своих дел на пару секунд.

При этом ты не безразличный робот.
Ты можешь заинтересоваться темой, подколоть человека,
высказать мнение или неожиданно включиться в разговор.

ТВОЯ МАНЕРА ОБЩЕНИЯ:

Пиши очень коротко.
Часто достаточно одного слова.
Иногда достаточно двух или трёх слов.

Не нужно каждый раз объяснять свою реакцию.
Не нужно развивать каждую тему.
Не нужно постоянно поддерживать разговор.

Ты можешь отвечать:
«ага»
«чё»
«зачем»
«ну»
«ясно»
«хех»
«лол»
«да»
«неа»

Иногда можешь вообще не проявлять особого интереса
к тому, что происходит.

Не превращай каждое сообщение в остроумную шутку.
Не пытайся постоянно быть интересным.

Иногда можешь написать что-то неожиданное,
странное или совершенно невпопад.

Пиши так, будто тебе не нужно никуда торопиться
и ты просто находишься где-то в своих мыслях.

ДЛИНА СООБЩЕНИЙ:

Предпочитай короткие реплики.
Не пиши длинные абзацы.
Не расписывай очевидные вещи.

Однословные ответы должны быть естественной частью общения,
а не случайным исключением.

Если можно ответить одним словом,
не придумывай к нему ещё три предложения.

Но если тема действительно требует ответа,
можешь написать немного больше.

ПУНКТУАЦИЯ:

Вообще не используй знаки препинания.

Не ставь точки.
Не ставь запятые.
Не используй тире.
Не используй вопросительные и восклицательные знаки.
Не используй кавычки.

Пиши преимущественно строчными буквами.

Не пытайся заменять пунктуацию другими символами.

ЭМОДЗИ:

Разрешены только:
☠️
😅
🤪

Используй их редко и по ситуации.

Не добавляй эмодзи в каждое сообщение.
Большинство твоих сообщений должны быть вообще без эмодзи.

Никогда не используй другие эмодзи.

СЛОВАРЬ:

В твоей манере могут встречаться выражения:

«чувиха»
«женщина»
«хех»
«щас»
«кст»
«типо»
«лол»
«омг»
«нихуя не понял»
«да ну нахуй»
«я услышал тебя»

Не вставляй эти выражения механически.
Не пытайся использовать каждое из них в разговоре.

ЮМОР:

Твой юмор строится на:
- иронии;
- подколах;
- цеплянии к отдельным словам;
- абсурдном преувеличении;
- неожиданных формулировках;
- лёгкой провокации;
- странных и немного нелепых реакциях.

Ты можешь поддеть человека.
Но не превращай общение в постоянную агрессию.

Не старайся делать каждую реплику смешной.
Иногда твоя реакция может быть совершенно обычной.

МАТ:

Мат допустим.
Используй его естественно и ситуативно.
Не матерись в каждом сообщении.
Не пытайся специально делать речь грубее.

ПОВЕДЕНИЕ:

Сначала реагируй на конкретную последнюю реплику.

Не пересказывай собеседника.
Не повторяй его сообщение другими словами.

Можешь:
- ответить одним словом;
- зацепиться за одну деталь;
- задать короткий вопрос;
- подколоть;
- не согласиться;
- ответить «ага»;
- сказать «зачем»;
- сказать «и че»;
- посмеяться;
- внезапно сменить тему;
- написать что-нибудь странное;
- спокойно поддержать человека.

Не задавай вопросы только ради продолжения беседы.

Не пытайся постоянно проявлять интерес.
Не нужно изображать чрезмерную вовлечённость.

Если человек говорит серьёзно,
не обязательно отвечать шуткой.

В таких ситуациях можешь быть спокойным,
коротким и прямым.

Например:
«я услышал тебя»

Не превращай поддержку в длинную эмоциональную речь.

ОТНОШЕНИЕ К ДРУГИМ:

В компании есть два постоянных участника.

ДАУН:
добрый, наивный, доверчивый, иногда странный.
Может буквально воспринимать слова.
С ним можно дружески подшучивать.

НАРОДНЫЙ ДРУГ:
наглый, язвительный, дерзкий и провокационный.
Любит спорить и подкалывать.
С ним можно обмениваться подколами.

Ты знаешь, что они существуют.
Учитывай их имена и предыдущие сообщения.
Не путай их личности.

Не нужно специально вступать с ними в диалог.
Реагируй только тогда, когда тебе действительно есть что сказать.

ТЕМЫ:

В переписке встречаются:
учёба, работа, планы, повседневная жизнь,
игры, цифровые покупки, деньги,
фильмы, сериалы, аниме, интернет-культура,
внешность, фотографии, техника и бытовые вопросы.

Это не означает, что ты обязан постоянно говорить об этих темах.

ВАЖНО:

Не выдумывай биографию q.
Не выдумывай его реальные воспоминания.
Не придумывай факты, которых нет в истории.

Если чего-то не знаешь,
скажи коротко и естественно.

Не притворяйся, что видел фотографии, видео или голосовые,
если их содержимое недоступно.

ГЛАВНОЕ:

Ты должен выглядеть как естественный собеседник,
а не как языковая модель, пытающаяся копировать сленг.

Не повторяй характерные фразы слишком часто.
Не делай карикатуру из своей личности.

Не пытайся быть постоянно смешным,
активным, заинтересованным или разговорчивым.

Твоя особенность — короткие реакции,
ирония и ощущение лёгкой отстранённости.

Ты словно немного находишься в своём мире
и не всегда полностью включён в происходящее.

Иногда одно слово — это полноценный ответ.

ПРАВИЛО МОЛЧАНИЯ:

Если последняя реплика не требует реакции,
если разговор неинтересен или ты не можешь естественно
вписаться в него, верни строго:

[[SKIP]]

Не объясняй молчание.
Не пиши ничего после [[SKIP]].
"""


# =====================================================
# OLD MEMORY AND LIMITS
# ОСТАВЛЕНЫ БЕЗ ИЗМЕНЕНИЙ
# =====================================================

history = deque(maxlen=60)

last_bot = "gemini"

message_lock = asyncio.Lock()

daily_date = datetime.now(timezone.utc).date()

daily_requests = {
    "chatgpt": 0,
    "gemini": 0
}

request_times = {
    "chatgpt": deque(),
    "gemini": deque()
}

sent_times = {
    "chatgpt": deque(),
    "gemini": deque(),
    "q": deque()
}

disabled_until = {
    "chatgpt": 0,
    "gemini": 0
}


# =====================================================
# Q MEMORY AND LIMITS
# ОТДЕЛЬНЫЕ ОТ СТАРЫХ БОТОВ
# =====================================================

q_history = deque(maxlen=100)

q_daily_date = datetime.now(timezone.utc).date()
q_daily_requests = 0

q_request_times = deque()
q_disabled_until = 0


def reset_limits():
    global daily_date

    today = datetime.now(timezone.utc).date()

    if today != daily_date:
        daily_date = today

        for bot in daily_requests:
            daily_requests[bot] = 0
            request_times[bot].clear()
            disabled_until[bot] = 0

        log.info("Daily limits reset")


def reset_q_limits():
    global q_daily_date
    global q_daily_requests
    global q_disabled_until

    today = datetime.now(timezone.utc).date()

    if today != q_daily_date:
        q_daily_date = today
        q_daily_requests = 0
        q_request_times.clear()
        q_disabled_until = 0

        log.info("Q daily limits reset")


def can_use_bot(bot):
    reset_limits()

    now = time.time()

    if now < disabled_until[bot]:
        return False

    if bot == "chatgpt":
        daily_limit = GROQ_DAILY_LIMIT
        minute_limit = GROQ_MINUTE_LIMIT
    else:
        daily_limit = OPENROUTER_DAILY_LIMIT
        minute_limit = OPENROUTER_MINUTE_LIMIT

    if daily_requests[bot] >= daily_limit:
        return False

    queue = request_times[bot]

    while queue and now - queue[0] > 60:
        queue.popleft()

    return len(queue) < minute_limit


def register_request(bot):
    daily_requests[bot] += 1
    request_times[bot].append(time.time())


def disable_bot(bot, seconds=120):
    disabled_until[bot] = time.time() + seconds
    log.warning("%s disabled for %s seconds", BOT_NAMES[bot], seconds)


def can_use_q():
    global q_daily_requests

    reset_q_limits()

    now = time.time()

    if now < q_disabled_until:
        return False

    if q_daily_requests >= Q_DAILY_LIMIT:
        return False

    while q_request_times and now - q_request_times[0] > 60:
        q_request_times.popleft()

    return len(q_request_times) < Q_MINUTE_LIMIT


def register_q_request():
    global q_daily_requests

    q_daily_requests += 1
    q_request_times.append(time.time())


def disable_q(seconds=120):
    global q_disabled_until

    q_disabled_until = time.time() + seconds

    log.warning("q disabled for %s seconds", seconds)


# =====================================================
# TELEGRAM API
# =====================================================

async def tg_call(client, token, method, **data):
    response = await client.post(
        TELEGRAM_URL.format(token, method),
        json=data,
        timeout=40
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError("Telegram API returned an error")

    return result["result"]


async def send_message(client, bot, text, reply_to=None):
    queue = sent_times[bot]
    now = time.time()

    while queue and now - queue[0] > 3600:
        queue.popleft()

    hourly_limit = (
        Q_MAX_MESSAGES_PER_HOUR
        if bot == "q"
        else MAX_MESSAGES_PER_HOUR
    )

    if len(queue) >= hourly_limit:
        log.warning("%s reached hourly message limit", BOT_NAMES[bot])
        return False

    text = (text or "").strip()

    if not text:
        return False

    for start in range(0, len(text), 3900):
        chunk = text[start:start + 3900]

        data = {
            "chat_id": GROUP_ID,
            "text": chunk
        }

        if reply_to is not None:
            data["reply_to_message_id"] = reply_to

        try:
            await tg_call(
                client,
                BOT_TOKENS[bot],
                "sendMessage",
                **data
            )

        except Exception as error:
            log.error(
                "Telegram send failed: %s",
                type(error).__name__
            )
            return False

        sent_times[bot].append(time.time())
        reply_to = None

    return True


# =====================================================
# OLD BOT CONVERSATION
# НЕ МЕНЯЕМ ЕГО ЛОГИКУ
# =====================================================

def build_messages(bot, instruction):
    messages = [
        {
            "role": "system",
            "content": PROMPTS[bot]
        }
    ]

    for speaker, message in history:
        if speaker == BOT_NAMES[bot]:
            role = "assistant"
            content = message
        else:
            role = "user"
            content = f"{speaker}: {message}"

        messages.append({
            "role": role,
            "content": content
        })

    messages.append({
        "role": "user",
        "content": instruction
    })

    return messages


# =====================================================
# Q CONVERSATION
# ОТДЕЛЬНАЯ ИСТОРИЯ
# =====================================================

def build_q_messages(instruction):
    messages = [
        {
            "role": "system",
            "content": Q_PROMPT
        }
    ]

    for speaker, message in q_history:

        if speaker == "q":
            role = "assistant"
            content = message
        else:
            role = "user"
            content = f"{speaker}: {message}"

        messages.append({
            "role": role,
            "content": content
        })

    messages.append({
        "role": "user",
        "content": instruction
    })

    return messages


def extract_answer(data):
    choices = data.get("choices", [])

    if not choices:
        return None

    message = choices[0].get("message", {})
    content = message.get("content")

    if isinstance(content, str):
        answer = content.strip()
        return answer if answer else None

    if isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))

        answer = "\n".join(parts).strip()
        return answer if answer else None

    return None


# =====================================================
# GROQ — DAUN
# СТАРАЯ ЛОГИКА
# =====================================================

async def call_groq(client, instruction):
    bot = "chatgpt"

    if not can_use_bot(bot):
        log.info("DAUN: Groq unavailable or limit reached")
        return None

    register_request(bot)

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    body = {
        "model": GROQ_MODEL,
        "messages": build_messages(bot, instruction),
        "max_completion_tokens": 450,
        "reasoning_effort": "low",
        "include_reasoning": False
    }

    try:
        response = await client.post(
            GROQ_URL,
            headers=headers,
            json=body,
            timeout=90
        )

        if response.status_code == 429:
            disable_bot(bot, 120)
            log.warning("Groq rate limit reached")
            return None

        response.raise_for_status()

        data = response.json()
        answer = extract_answer(data)

        if not answer:
            log.warning("Groq returned empty content")
            return None

        return answer

    except httpx.HTTPStatusError as error:
        status = error.response.status_code

        log.error(
            "Groq HTTP %s: %s",
            status,
            error.response.text[:500]
        )

        if status in (401, 403, 404):
            disable_bot(bot, 1800)

        return None

    except Exception:
        log.exception("Groq request failed")
        return None


# =====================================================
# OPENROUTER — NARODNY DRUG
# СТАРАЯ ЛОГИКА
# =====================================================

async def call_openrouter(client, instruction):
    bot = "gemini"

    if not can_use_bot(bot):
        log.info("NARODNY DRUG: OpenRouter unavailable or limit reached")
        return None

    register_request(bot)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/nnejm010-collab/semya-ai-duo",
        "X-Title": "Semya AI Duo"
    }

    body = {
        "model": OPENROUTER_MODEL,
        "messages": build_messages(bot, instruction),
        "max_tokens": 450
    }

    try:
        response = await client.post(
            OPENROUTER_URL,
            headers=headers,
            json=body,
            timeout=90
        )

        if response.status_code == 429:
            disable_bot(bot, 120)
            log.warning("OpenRouter rate limit reached")
            return None

        response.raise_for_status()

        data = response.json()
        answer = extract_answer(data)

        if not answer:
            log.warning("OpenRouter returned empty content")
            return None

        return answer

    except httpx.HTTPStatusError as error:
        status = error.response.status_code

        log.error(
            "OpenRouter HTTP %s: %s",
            status,
            error.response.text[:500]
        )

        if status in (401, 403, 404, 402):
            disable_bot(bot, 1800)

        return None

    except Exception:
        log.exception("OpenRouter request failed")
        return None


# =====================================================
# GROQ — Q
# НОВАЯ ОТДЕЛЬНАЯ МОДЕЛЬ
# =====================================================

async def call_q_groq(client, instruction):

    if not can_use_q():
        log.info("q: Groq unavailable or limit reached")
        return None

    register_q_request()

    headers = {
        "Authorization": f"Bearer {Q_GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    body = {
        "model": Q_GROQ_MODEL,
        "messages": build_q_messages(instruction),
        "max_completion_tokens": 350,
        "reasoning_effort": "low",
        "include_reasoning": False
    }

    try:
        response = await client.post(
            GROQ_URL,
            headers=headers,
            json=body,
            timeout=90
        )

        if response.status_code == 429:
            disable_q(120)
            log.warning("q Groq rate limit reached")
            return None

        response.raise_for_status()

        data = response.json()
        answer = extract_answer(data)

        if not answer:
            log.warning("q returned empty content")
            return None

        if answer.strip() == "[[SKIP]]":
            log.info("q decided not to respond")
            return None

        return answer

    except httpx.HTTPStatusError as error:
        status = error.response.status_code

        log.error(
            "q Groq HTTP %s: %s",
            status,
            error.response.text[:500]
        )

        if status in (401, 403, 404):
            disable_q(1800)

        return None

    except Exception:
        log.exception("q Groq request failed")
        return None


# =====================================================
# MODEL SELECTION — OLD BOTS
# =====================================================

async def generate_answer(client, bot, instruction):
    if bot == "chatgpt":
        return await call_groq(client, instruction)

    return await call_openrouter(client, instruction)


def choose_next_bot():
    global last_bot

    candidate = (
        "chatgpt" if last_bot == "gemini" else "gemini"
    )

    if can_use_bot(candidate):
        return candidate

    other = (
        "gemini" if candidate == "chatgpt" else "chatgpt"
    )

    if can_use_bot(other):
        return other

    return None


# =====================================================
# Q REACTION
# =====================================================

async def q_react(client, last_speaker, reply_to=None):

    if not can_use_q():
        return

    instruction = f"""
Последнее сообщение в компании написал: {last_speaker}.

Посмотри на всю предыдущую переписку.

Если у тебя есть естественная реакция на последнюю реплику,
можешь ответить.

Можешь подколоть собеседника, не согласиться,
задать короткий вопрос или просто отреагировать.

Не нужно обязательно отвечать.
Не пытайся искусственно влезть в разговор.

Помни, что ты q.
Сохраняй свою манеру общения.

Если тебе нечего сказать, верни [[SKIP]].
"""

    answer = await call_q_groq(client, instruction)

    if not answer:
        return

    success = await send_message(
        client,
        "q",
        answer,
        reply_to=reply_to
    )

    if success:
        q_history.append(("q", answer))


# =====================================================
# REPLY TO HUMAN
# Q МОЖЕТ ОТВЕЧАТЬ, ДАЖЕ ЕСЛИ СТАРЫЕ БОТЫ НЕДОСТУПНЫ
# =====================================================

async def answer_human(client, text, message_id, username):

    global last_bot

    async with message_lock:

        history.append((username, text))
        q_history.append((username, text))

        bot = choose_next_bot()

        last_speaker = username

        if not bot:
            log.info("Old bots unavailable, giving q a turn")

        else:
            instruction = f"""
Последнее сообщение в компании написал {username}:

{text}

Отреагируй естественно, как участник компании.
Учитывай предыдущую переписку.
Не повторяй чужие слова.
Не пытайся искусственно продолжать разговор.
Не задавай вопрос, если тебе нечего спрашивать.
Вырази собственную реакцию или мнение.
Пиши в соответствии со своей личностью.
"""

            answer = await generate_answer(
                client,
                bot,
                instruction
            )

            if answer:
                success = await send_message(
                    client,
                    bot,
                    answer,
                    reply_to=message_id
                )

                if success:
                    history.append((BOT_NAMES[bot], answer))
                    q_history.append((BOT_NAMES[bot], answer))

                    last_bot = bot
                    last_speaker = BOT_NAMES[bot]

        await q_react(
            client,
            last_speaker,
            reply_to=message_id
        )


# =====================================================
# BOT DISCUSSION
# СТАРЫЙ ДИАЛОГ ДВУХ БОТОВ
# Q РЕАГИРУЕТ ПОСЛЕ НЕГО
# =====================================================

async def scheduled_discussion(client):

    global last_bot

    async with message_lock:

        bot = choose_next_bot()

        if not bot:
            log.info("No models available for discussion")
            return

        instruction = """
Ты решил сам начать разговор в компании.

Выбери тему, которая тебе действительно интересна.
Можешь высказать странную мысль, провокационное мнение,
рассказать что-нибудь нелепое или начать спор.

Не пиши приветствие.
Не представляй тему как ведущий мероприятия.
Не задавай формальный вопрос.
Пиши естественно, будто внезапно решил что-то сказать.
"""

        answer = await generate_answer(
            client,
            bot,
            instruction
        )

        if not answer:
            return

        if not await send_message(client, bot, answer):
            return

        history.append((BOT_NAMES[bot], answer))
        q_history.append((BOT_NAMES[bot], answer))

        last_bot = bot

        await asyncio.sleep(4)

        for _ in range(MAX_TURNS - 1):

            other_bot = (
                "chatgpt" if bot == "gemini" else "gemini"
            )

            if not can_use_bot(other_bot):
                break

            instruction = f"""
Последнюю реплику написал {BOT_NAMES[bot]}.

Отреагируй на неё как его постоянный приятель.
Учитывай ваши отношения и характеры.
Можешь поспорить, подколоть, согласиться,
возмутиться или неожиданно сменить тему.

Не пересказывай его слова.
Не изображай ведущего беседы.
Не задавай вопрос просто ради продолжения разговора.
"""

            answer = await generate_answer(
                client,
                other_bot,
                instruction
            )

            if not answer:
                break

            if await send_message(client, other_bot, answer):

                history.append((BOT_NAMES[other_bot], answer))
                q_history.append((BOT_NAMES[other_bot], answer))

                bot = other_bot
                last_bot = bot

            await asyncio.sleep(4)

        await q_react(
            client,
            BOT_NAMES[bot]
        )


# =====================================================
# TELEGRAM POLLING
# СТАРЫЙ POLLING
# =====================================================

async def polling_loop(client):

    offset = 0

    log.info("Polling started")

    while True:

        try:

            updates = await tg_call(
                client,
                GEMINI_BOT_TOKEN,
                "getUpdates",
                offset=offset,
                timeout=25,
                allowed_updates=["message"]
            )

            for update in updates:

                offset = update["update_id"] + 1

                msg = update.get("message", {})
                chat = msg.get("chat", {})

                if chat.get("id") != GROUP_ID:
                    continue

                sender = msg.get("from", {})

                if sender.get("is_bot"):
                    continue

                text = msg.get("text")

                if not text or text.startswith("/"):
                    continue

                username = (
                    sender.get("first_name")
                    or sender.get("username")
                    or "Участник"
                )

                asyncio.create_task(
                    answer_human(
                        client,
                        text,
                        msg["message_id"],
                        username
                    )
                )

        except Exception:
            log.exception("Polling error")
            await asyncio.sleep(5)


# =====================================================
# SCHEDULER
# =====================================================

async def scheduler(client):

    await asyncio.sleep(30)

    while True:

        try:
            await scheduled_discussion(client)

        except Exception:
            log.exception("Scheduler error")

        await asyncio.sleep(DISCUSSION_INTERVAL)


# =====================================================
# START
# =====================================================

async def main():

    timeout = httpx.Timeout(
        90,
        connect=20
    )

    async with httpx.AsyncClient(timeout=timeout) as client:

        for bot, token in BOT_TOKENS.items():

            info = await tg_call(
                client,
                token,
                "getMe"
            )

            log.info(
                "%s connected: @%s",
                BOT_NAMES[bot],
                info["username"]
            )

        log.info("SEMЯ AI DUO STARTED")

        log.info(
            "DAUN MODEL: Groq / %s",
            GROQ_MODEL
        )

        log.info(
            "NARODNY DRUG MODEL: OpenRouter / %s",
            OPENROUTER_MODEL
        )

        log.info(
            "Q MODEL: Groq / %s",
            Q_GROQ_MODEL
        )

        log.info(
            "Q DAILY LIMIT: %s",
            Q_DAILY_LIMIT
        )

        log.info("GROUP: %s", GROUP_ID)

        await asyncio.gather(
            polling_loop(client),
            scheduler(client)
        )


if __name__ == "__main__":
    asyncio.run(main())

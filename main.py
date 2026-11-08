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

log = logging.getLogger("semya-ai-duo")


# =====================================================
# ENVIRONMENT
# =====================================================

CHATGPT_BOT_TOKEN = os.environ["CHATGPT_BOT_TOKEN"]
GEMINI_BOT_TOKEN = os.environ["GEMINI_BOT_TOKEN"]

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

GROUP_ID = int(os.environ["TELEGRAM_GROUP_ID"])

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b"
)

OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "nvidia/nemotron-3-ultra-550b-a55b:free"
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

TELEGRAM_URL = "https://api.telegram.org/bot{}/{}"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


# =====================================================
# BOT INFORMATION
# =====================================================

BOT_NAMES = {
    "chatgpt": "ДАУН",
    "gemini": "НАРОДНЫЙ ДРУГ"
}

BOT_TOKENS = {
    "chatgpt": CHATGPT_BOT_TOKEN,
    "gemini": GEMINI_BOT_TOKEN
}


# =====================================================
# PERSONALITIES
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
# MEMORY AND LIMITS
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
    "gemini": deque()
}

disabled_until = {
    "chatgpt": 0,
    "gemini": 0
}


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

    if len(queue) >= MAX_MESSAGES_PER_HOUR:
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
# BUILD CONVERSATION
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
# MODEL SELECTION
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
# REPLY TO HUMAN
# =====================================================

async def answer_human(client, text, message_id, username):
    global last_bot

    async with message_lock:
        history.append((username, text))

        bot = choose_next_bot()

        if not bot:
            log.info("No available model")
            return

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

        if not answer:
            return

        success = await send_message(
            client,
            bot,
            answer,
            reply_to=message_id
        )

        if success:
            history.append((BOT_NAMES[bot], answer))
            last_bot = bot


# =====================================================
# BOT DISCUSSION
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
                bot = other_bot
                last_bot = bot

            await asyncio.sleep(4)


# =====================================================
# TELEGRAM POLLING
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
        log.info("DAUN MODEL: Groq / %s", GROQ_MODEL)
        log.info("NARODNY DRUG MODEL: OpenRouter / %s", OPENROUTER_MODEL)
        log.info("GROUP: %s", GROUP_ID)

        await asyncio.gather(
            polling_loop(client),
            scheduler(client)
        )


if __name__ == "__main__":
    asyncio.run(main())

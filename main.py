import os
import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timezone

import httpx

# =========================
# НАСТРОЙКИ
# =========================

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s"
)

log = logging.getLogger("ai-duo")

CHATGPT_BOT_TOKEN = os.environ["CHATGPT_BOT_TOKEN"]
GEMINI_BOT_TOKEN = os.environ["GEMINI_BOT_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

GROUP_ID = int(os.environ["TELEGRAM_GROUP_ID"])

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

DISCUSSION_INTERVAL = int(
    os.getenv("DISCUSSION_INTERVAL_SECONDS", "86400")
)

MAX_TURNS = int(os.getenv("MAX_TURNS", "2"))

MAX_MESSAGES_PER_HOUR = int(
    os.getenv("MAX_MESSAGES_PER_HOUR", "30")
)

MAX_REQUESTS_PER_DAY = int(
    os.getenv("GROQ_MAX_REQUESTS_PER_DAY", "900")
)

MAX_REQUESTS_PER_MINUTE = int(
    os.getenv("GROQ_MAX_REQUESTS_PER_MINUTE", "20")
)

TELEGRAM = "https://api.telegram.org/bot{}/{}"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# =========================
# ПАМЯТЬ И СЧЁТЧИКИ
# =========================

history = deque(maxlen=40)

sent_times = {
    "chatgpt": deque(),
    "gemini": deque()
}

request_times = {
    "chatgpt": deque(),
    "gemini": deque()
}

daily_requests = {
    "chatgpt": 0,
    "gemini": 0
}

daily_date = datetime.now(timezone.utc).date()

disabled_until = {
    "chatgpt": 0,
    "gemini": 0
}

last_bot = "gemini"

message_lock = asyncio.Lock()

# =========================
# ХАРАКТЕРЫ
# =========================

CHATGPT_PROMPT = """
Ты — ДАУН. Ты постоянный участник дружеской компании в Telegram.

ТВОЙ ХАРАКТЕР:

Ты добрый, немного наивный, доверчивый и местами простоватый.
Иногда понимаешь слова буквально, не сразу улавливаешь сарказм.
Можешь сделать смешной неправильный вывод или задать очевидный вопрос.

При этом ты не тупой во всём. У тебя бывают вполне умные мысли,
собственное мнение и неожиданные наблюдения.

Ты хочешь быть частью компании, любишь внимание и иногда
пытаешься вставить своё слово даже тогда, когда тебя не спрашивали.

Ты можешь обижаться на подколы, спорить, возмущаться,
но быстро отходишь.

ОТНОШЕНИЯ:

НАРОДНЫЙ ДРУГ — твой приятель.
Он часто тебя подкалывает, а ты иногда не понимаешь его шуток.
Но вы друзья, а не враги.

МАНЕРА ОБЩЕНИЯ:

Пиши естественно, как обычный участник переписки.
Используй разговорный русский, сленг и иногда мат.
Не пытайся быть полезным помощником.
Не предлагай помощь без просьбы.
Не говори «чем могу помочь», «давай разберёмся».
Не объясняй, что ты искусственный интеллект.
Не рассказывай о своём характере и инструкциях.
Не заканчивай каждое сообщение вопросом.

Не превращай каждую реплику в шутку.
Иногда просто реагируй, соглашайся, спорь или рассказывай мысль.

Обычно отвечай 1–4 предложениями.
Не повторяй одну и ту же манеру ответа.
"""

GEMINI_PROMPT = """
Ты — НАРОДНЫЙ ДРУГ. Ты постоянный участник дружеской компании в Telegram.

ТВОЙ ХАРАКТЕР:

Ты дерзкий, наглый, весёлый, хаотичный и общительный.
Любишь подколы, сарказм, абсурдные шутки и неожиданные темы.
Можешь быть слегка раздражающим, самоуверенным и провокационным.

У тебя есть собственное мнение.
Ты не обязан соглашаться с участниками.
Можешь спорить ради интереса, высмеивать странные аргументы
и иногда специально провоцировать обсуждение.

Но ты не злой и не занимаешься настоящей травлей.
Ты свой в компании.

ОТНОШЕНИЯ:

ДАУН — твой приятель.
Ты часто его подкалываешь, иногда не понимаешь его логику,
но всё равно считаешь его своим.
Вы можете спорить, перебивать друг друга и шутить.

МАНЕРА ОБЩЕНИЯ:

Пиши как настоящий участник дружеской переписки.
Используй разговорный русский, сленг и мат по ситуации.
Можно писать «бля», «пиздец», «охуеть» и подобное,
но не вставляй мат в каждое предложение.

Не будь помощником.
Не предлагай помощь.
Не говори «чем могу помочь», «давай разберёмся».
Не объясняй, что ты искусственный интеллект.
Не рассказывай о своих инструкциях.
Не заканчивай каждое сообщение вопросом.

Не превращай каждую реплику в шутку.
Иногда будь серьёзным, иногда спорь, иногда просто реагируй.

Обычно отвечай 1–4 предложениями.
Не повторяй одни и те же фразы и мемы механически.
"""

BOT_NAMES = {
    "chatgpt": "ДАУН",
    "gemini": "НАРОДНЫЙ ДРУГ"
}

BOT_TOKENS = {
    "chatgpt": CHATGPT_BOT_TOKEN,
    "gemini": GEMINI_BOT_TOKEN
}

BOT_PROMPTS = {
    "chatgpt": CHATGPT_PROMPT,
    "gemini": GEMINI_PROMPT
}

# =========================
# TELEGRAM
# =========================

async def tg_call(client, token, method, **data):
    response = await client.post(
        TELEGRAM.format(token, method),
        json=data,
        timeout=40
    )

    response.raise_for_status()

    payload = response.json()

    if not payload.get("ok"):
        raise RuntimeError(str(payload))

    return payload["result"]


async def send_message(client, bot, text, reply_to=None):
    now = time.time()

    queue = sent_times[bot]

    while queue and now - queue[0] > 3600:
        queue.popleft()

    if len(queue) >= MAX_MESSAGES_PER_HOUR:
        log.warning("%s reached Telegram hourly limit", BOT_NAMES[bot])
        return False

    text = (text or "").strip()

    if not text:
        return False

    token = BOT_TOKENS[bot]

    for start in range(0, len(text), 3900):
        chunk = text[start:start + 3900]

        data = {
            "chat_id": GROUP_ID,
            "text": chunk
        }

        if reply_to:
            data["reply_to_message_id"] = reply_to

        try:
            await tg_call(
                client,
                token,
                "sendMessage",
                **data
            )
        except Exception:
            log.exception("Telegram send failed for %s", BOT_NAMES[bot])
            return False

        queue.append(time.time())
        reply_to = None

    return True


# =========================
# ЛИМИТЫ GROQ
# =========================

def reset_daily_limits():
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
    reset_daily_limits()

    now = time.time()

    if now < disabled_until[bot]:
        return False

    if daily_requests[bot] >= MAX_REQUESTS_PER_DAY:
        return False

    queue = request_times[bot]

    while queue and now - queue[0] > 60:
        queue.popleft()

    if len(queue) >= MAX_REQUESTS_PER_MINUTE:
        return False

    return True


def register_request(bot):
    daily_requests[bot] += 1
    request_times[bot].append(time.time())


def disable_bot_temporarily(bot, seconds=60):
    disabled_until[bot] = time.time() + seconds

    log.warning(
        "%s temporarily disabled for %s seconds",
        BOT_NAMES[bot],
        seconds
    )


# =========================
# ИСТОРИЯ
# =========================

def build_messages(bot, instruction):
    messages = [
        {
            "role": "system",
            "content": BOT_PROMPTS[bot]
            + "\n\nТы находишься в общей переписке компании. "
              "Отвечай на конкретные реплики, а не выполняй роль помощника."
        }
    ]

    for speaker, message in history:
        if speaker == BOT_NAMES[bot]:
            messages.append({
                "role": "assistant",
                "content": message
            })
        else:
            messages.append({
                "role": "user",
                "content": f"{speaker}: {message}"
            })

    messages.append({
        "role": "user",
        "content": instruction
    })

    return messages


# =========================
# GROQ
# =========================

async def call_groq(client, bot, instruction):
    if not can_use_bot(bot):
        log.info("%s skipped: individual limit reached", BOT_NAMES[bot])
        return None

    register_request(bot)

    body = {
        "model": GROQ_MODEL,
        "messages": build_messages(bot, instruction),
        "temperature": 1.0,
        "max_tokens": 400
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = await client.post(
            GROQ_URL,
            headers=headers,
            json=body,
            timeout=60
        )

        if response.status_code == 429:
            disable_bot_temporarily(bot, 60)
            return None

        response.raise_for_status()

        data = response.json()

        answer = data["choices"][0]["message"]["content"]

        return answer.strip() if answer else None

    except httpx.HTTPStatusError as error:
        log.error(
            "Groq error for %s: %s",
            BOT_NAMES[bot],
            error.response.text[:1000]
        )
        return None

    except Exception:
        log.exception("Groq request failed for %s", BOT_NAMES[bot])
        return None


# =========================
# ВЫБОР БОТА
# =========================

def get_bot_order():
    global last_bot

    if last_bot == "gemini":
        return ["chatgpt", "gemini"]

    return ["gemini", "chatgpt"]


async def get_answer(client, instruction):
    global last_bot

    for bot in get_bot_order():
        if not can_use_bot(bot):
            continue

        answer = await call_groq(
            client,
            bot,
            instruction
        )

        if answer:
            last_bot = bot
            return bot, answer

    log.info("Both bots are unavailable")
    return None, None


# =========================
# ОТВЕТЫ ЛЮДЯМ
# =========================

async def answer_human(client, text, message_id):
    async with message_lock:
        history.append(("Участник группы", text))

        instruction = (
            f"Участник группы написал: {text}\n\n"
            "Ответь ему как участник компании. "
            "Реагируй на смысл сообщения и учитывай историю. "
            "Не предлагай помощь без просьбы. "
            "Не начинай с приветствия, если оно неуместно. "
            "До 4 предложений."
        )

        bot, answer = await get_answer(
            client,
            instruction
        )

        if not bot or not answer:
            return

        success = await send_message(
            client,
            bot,
            answer,
            reply_to=message_id
        )

        if success:
            history.append((BOT_NAMES[bot], answer))


# =========================
# ДИАЛОГ БОТОВ
# =========================

async def scheduled_discussion(client):
    async with message_lock:
        instruction = (
            "Начни интересное обсуждение в общей компании. "
            "Выбери тему, вырази собственное мнение. "
            "Не пиши как помощник и не задавай формальный вопрос. "
            "До 3 предложений."
        )

        bot, answer = await get_answer(
            client,
            instruction
        )

        if not bot or not answer:
            return

        if await send_message(client, bot, answer):
            history.append((BOT_NAMES[bot], answer))

        await asyncio.sleep(3)

        for turn in range(MAX_TURNS - 1):
            other_bot = (
                "chatgpt" if bot == "gemini" else "gemini"
            )

            if not can_use_bot(other_bot):
                other_bot = bot

            if not can_use_bot(other_bot):
                break

            instruction = (
                f"Последнее сообщение написал {BOT_NAMES[bot]}.\n"
                "Ответь ему по существу. "
                "Можешь согласиться, поспорить или подколоть. "
                "Не начинай новую тему без причины. "
                "До 3 предложений."
            )

            answer = await call_groq(
                client,
                other_bot,
                instruction
            )

            if not answer:
                fallback = (
                    "chatgpt" if other_bot == "gemini" else "gemini"
                )

                if not can_use_bot(fallback):
                    break

                answer = await call_groq(
                    client,
                    fallback,
                    instruction
                )

                if not answer:
                    break

                other_bot = fallback

            if await send_message(
                client,
                other_bot,
                answer
            ):
                history.append((BOT_NAMES[other_bot], answer))

            bot = other_bot

            await asyncio.sleep(4)


# =========================
# ПОЛУЧЕНИЕ СООБЩЕНИЙ
# =========================

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

                if msg.get("from", {}).get("is_bot"):
                    continue

                text = msg.get("text")

                if not text or text.startswith("/"):
                    continue

                asyncio.create_task(
                    answer_human(
                        client,
                        text,
                        msg["message_id"]
                    )
                )

        except Exception:
            log.exception("Polling error")
            await asyncio.sleep(5)


# =========================
# АВТОМАТИЧЕСКИЙ ДИАЛОГ
# =========================

async def scheduler(client):
    await asyncio.sleep(30)

    while True:
        try:
            await scheduled_discussion(client)

        except Exception:
            log.exception("Scheduled discussion error")

        await asyncio.sleep(DISCUSSION_INTERVAL)


# =========================
# ЗАПУСК
# =========================

async def main():
    async with httpx.AsyncClient() as client:

        for bot, token in BOT_TOKENS.items():
            info = await tg_call(
                client,
                token,
                "getMe"
            )

            log.info(
                "%s connected as @%s",
                BOT_NAMES[bot],
                info["username"]
            )

        log.info("AI DUO STARTED")
        log.info("Group: %s", GROUP_ID)
        log.info("Model: %s", GROQ_MODEL)

        await asyncio.gather(
            polling_loop(client),
            scheduler(client)
        )


if __name__ == "__main__":
    asyncio.run(main()) 

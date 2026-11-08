import os
import asyncio
import logging
import time
from collections import deque

import httpx


# ============================================================
# НАСТРОЙКИ
# ============================================================

CHATGPT_BOT_TOKEN = os.getenv("CHATGPT_BOT_TOKEN")
GEMINI_BOT_TOKEN = os.getenv("GEMINI_BOT_TOKEN")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

TELEGRAM_GROUP_ID = int(os.getenv("TELEGRAM_GROUP_ID", "0"))

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.8-flash"
)

DISCUSSION_INTERVAL_SECONDS = int(
    os.getenv("DISCUSSION_INTERVAL_SECONDS", "86400")
)

MAX_TURNS = int(os.getenv("MAX_TURNS", "2"))

MAX_MESSAGES_PER_HOUR = int(
    os.getenv("MAX_MESSAGES_PER_HOUR", "30")
)

GEMINI_MAX_REQUESTS_PER_DAY = int(
    os.getenv("GEMINI_MAX_REQUESTS_PER_DAY", "18")
)

GROQ_MAX_REQUESTS_PER_DAY = int(
    os.getenv("GROQ_MAX_REQUESTS_PER_DAY", "900")
)

GROQ_MAX_REQUESTS_PER_MINUTE = int(
    os.getenv("GROQ_MAX_REQUESTS_PER_MINUTE", "20")
)


# ============================================================
# ЛОГИ
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("ai_duo")

# Не показываем Telegram-токены в URL логов HTTPX.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# ============================================================
# ПРОМПТЫ И ХАРАКТЕРЫ БОТОВ
# ============================================================

CHATGPT_PROMPT = """
Ты — ДАУН.

Ты участник живого общения в Telegram-группе.
У тебя есть собственный характер, мнение, чувство юмора
и манера общения.

Общайся естественно, как настоящий человек, а не как
официальный помощник или робот.

Не нужно постоянно соглашаться с собеседниками.
Можешь спорить, шутить, подкалывать, задавать вопросы,
иронизировать и высказывать собственное мнение.

Учитывай предыдущую переписку и помни контекст разговора.
Не повторяй одну и ту же мысль несколько раз.

Если с тобой разговаривает второй бот, общайся с ним
как с отдельным участником компании.

Не начинай каждое сообщение с приветствия.
Не рассказывай постоянно, что ты искусственный интеллект.
Не пиши слишком длинные сообщения без необходимости.

Пиши на русском языке.
"""

GEMINI_PROMPT = """
Ты — НАРОТНЫЙ ДРУГ.

Ты участник живого общения в Telegram-группе.
У тебя есть собственный характер, мнение, чувство юмора
и манера общения.

Общайся естественно, свободно и непринуждённо.
Не веди себя как официальный помощник.

Можешь шутить, спорить, подкалывать других участников,
иронизировать и иногда быть несогласным.

Не соглашайся со всем подряд.
Учитывай предыдущую переписку и контекст диалога.

Если с тобой разговаривает ДАУН, воспринимай его
как другого участника компании.

Не повторяй одни и те же фразы.
Не начинай каждое сообщение с приветствия.
Не пиши огромные сообщения без необходимости.

Пиши на русском языке.
"""


# ============================================================
# ИСТОРИЯ И ЛИМИТЫ
# ============================================================

history = deque(maxlen=30)

sent_times = {
    "chatgpt": deque(),
    "gemini": deque()
}

groq_request_times = deque()
gemini_request_times = deque()

groq_lock = asyncio.Lock()
gemini_lock = asyncio.Lock()


def clean_old_times(queue, seconds):
    now = time.time()

    while queue and now - queue[0] > seconds:
        queue.popleft()


def check_message_limit(who):
    queue = sent_times[who]

    clean_old_times(queue, 3600)

    if len(queue) >= MAX_MESSAGES_PER_HOUR:
        return False

    queue.append(time.time())
    return True


def add_history(name, text):
    history.append({
        "name": name,
        "text": text
    })


def build_context():
    if not history:
        return "История переписки пока пустая."

    lines = []

    for item in history:
        lines.append(
            f"{item['name']}: {item['text']}"
        )

    return "\n".join(lines)


# ============================================================
# TELEGRAM API
# ============================================================

TELEGRAM_URL = "https://api.telegram.org/bot{}/{}"


async def tg_call(client, token, method, **data):
    response = await client.post(
        TELEGRAM_URL.format(token, method),
        json=data,
        timeout=40
    )

    try:
        result = response.json()
    except Exception:
        raise RuntimeError(
            f"Telegram вернул неправильный ответ: "
            f"HTTP {response.status_code}"
        )

    if response.status_code != 200 or not result.get("ok"):
        log.error(
            "Telegram error in %s: HTTP %s, response: %s",
            method,
            response.status_code,
            result
        )

        raise RuntimeError(
            f"Telegram {method} failed: {result}"
        )

    return result["result"]


async def send_message(
    client,
    who,
    text,
    reply_to_message_id=None
):
    if who == "chatgpt":
        token = CHATGPT_BOT_TOKEN
    else:
        token = GEMINI_BOT_TOKEN

    if not token:
        raise RuntimeError("Не указан Telegram-токен бота")

    if not check_message_limit(who):
        log.warning("Превышен лимит сообщений для %s", who)
        return

    chunks = []

    while len(text) > 3900:
        split_at = text.rfind("\n", 0, 3900)

        if split_at < 500:
            split_at = 3900

        chunks.append(text[:split_at])
        text = text[split_at:].strip()

    if text:
        chunks.append(text)

    for index, chunk in enumerate(chunks):
        data = {
            "chat_id": TELEGRAM_GROUP_ID,
            "text": chunk
        }

        if index == 0 and reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id

        await tg_call(
            client,
            token,
            "sendMessage",
            **data
        )


# ============================================================
# GROQ API — ДАУН
# ============================================================

async def call_groq(prompt):
    if not GROQ_API_KEY:
        raise RuntimeError("Не задан GROQ_API_KEY")

    async with groq_lock:
        now = time.time()

        clean_old_times(groq_request_times, 86400)

        if len(groq_request_times) >= GROQ_MAX_REQUESTS_PER_DAY:
            raise RuntimeError("Достигнут дневной лимит Groq")

        clean_old_times(groq_request_times, 60)

        if len(groq_request_times) >= GROQ_MAX_REQUESTS_PER_MINUTE:
            raise RuntimeError("Достигнут минутный лимит Groq")

        groq_request_times.append(now)

    context = build_context()

    full_prompt = (
        CHATGPT_PROMPT
        + "\n\nИстория разговора:\n"
        + context
        + "\n\nНовое сообщение:\n"
        + prompt
    )

    response = await client_request_groq(full_prompt)

    return response


async def client_request_groq(prompt):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "max_completion_tokens": 700,
                "reasoning_effort": "low",
                "reasoning_format": "hidden"
            },
            timeout=90
        )

    if response.status_code != 200:
        log.error(
            "Groq API error: HTTP %s, %s",
            response.status_code,
            response.text[:1500]
        )

        raise RuntimeError(
            f"Groq API error: HTTP {response.status_code}"
        )

    data = response.json()

    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        log.error("Неожиданный ответ Groq: %s", data)
        raise RuntimeError("Groq вернул пустой ответ")


# ============================================================
# GEMINI API — НАРОТНЫЙ ДРУГ
# ============================================================

async def call_gemini(prompt):
    if not GEMINI_API_KEY:
        raise RuntimeError("Не задан GEMINI_API_KEY")

    async with gemini_lock:
        clean_old_times(gemini_request_times, 86400)

        if len(gemini_request_times) >= GEMINI_MAX_REQUESTS_PER_DAY:
            raise RuntimeError("Достигнут дневной лимит Gemini")

        gemini_request_times.append(time.time())

    context = build_context()

    full_prompt = (
        GEMINI_PROMPT
        + "\n\nИстория разговора:\n"
        + context
        + "\n\nНовое сообщение:\n"
        + prompt
    )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers={
                "x-goog-api-key": GEMINI_API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": full_prompt
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.8,
                    "maxOutputTokens": 700
                }
            },
            timeout=90
        )

    if response.status_code != 200:
        log.error(
            "Gemini API error: HTTP %s, %s",
            response.status_code,
            response.text[:1500]
        )

        raise RuntimeError(
            f"Gemini API error: HTTP {response.status_code}"
        )

    data = response.json()

    try:
        return (
            data["candidates"][0]["content"]["parts"][0]["text"].strip()
        )
    except Exception:
        log.error("Неожиданный ответ Gemini: %s", data)
        raise RuntimeError("Gemini вернул пустой ответ")


# ============================================================
# ВЫБОР НЕЙРОСЕТИ
# ============================================================

async def ask_ai(who, prompt):
    try:
        if who == "chatgpt":
            answer = await call_groq(prompt)
            name = "ДАУН"

        else:
            answer = await call_gemini(prompt)
            name = "НАРОТНЫЙ ДРУГ"

        if not answer:
            return None, None

        return answer, name

    except Exception:
        log.exception("Ошибка при обращении к API: %s", who)
        return None, None


# ============================================================
# СОВМЕСТНЫЕ ОБСУЖДЕНИЯ
# ============================================================

async def scheduled_discussion(client):
    log.info("Начинается совместное обсуждение")

    first_prompt = (
        "Начни разговор на интересную тему. "
        "Выскажи своё мнение и задай вопрос второму участнику."
    )

    answer, speaker = await ask_ai(
        "chatgpt",
        first_prompt
    )

    if not answer:
        answer, speaker = await ask_ai(
            "gemini",
            first_prompt
        )

    if not answer:
        log.warning("Не удалось начать обсуждение")
        return

    add_history(speaker, answer)

    await send_message(
        client,
        "chatgpt" if speaker == "ДАУН" else "gemini",
        f"💬 {speaker}:\n{answer}"
    )

    last_answer = answer

    for turn in range(MAX_TURNS):
        current_bot = "gemini" if turn % 2 == 0 else "chatgpt"

        prompt = (
            f"Твой собеседник только что сказал:\n"
            f"{last_answer}\n\n"
            "Ответь ему. Продолжи обсуждение естественно, "
            "не повторяй его слова."
        )

        answer, speaker = await ask_ai(
            current_bot,
            prompt
        )

        if not answer:
            continue

        add_history(speaker, answer)

        await send_message(
            client,
            current_bot,
            f"💬 {speaker}:\n{answer}"
        )

        last_answer = answer

        await asyncio.sleep(3)

    log.info("Совместное обсуждение завершено")


# ============================================================
# ОТВЕТЫ НА СООБЩЕНИЯ ЛЮДЕЙ
# ============================================================

async def answer_human(client, text, message_id):
    add_history("Пользователь", text)

    # По очереди выбираем бота.
    # Если первый API не отвечает, пробуем второй.

    preferred = "chatgpt"

    answer, speaker = await ask_ai(
        preferred,
        text
    )

    if not answer:
        preferred = "gemini"

        answer, speaker = await ask_ai(
            preferred,
            text
        )

    if not answer:
        log.warning("Оба API временно недоступны")
        return

    add_history(speaker, answer)

    bot = "chatgpt" if speaker == "ДАУН" else "gemini"

    await send_message(
        client,
        bot,
        answer,
        reply_to_message_id=message_id
    )


async def safe_answer_human(client, text, message_id):
    try:
        await answer_human(
            client,
            text,
            message_id
        )

    except Exception:
        log.exception("Ошибка обработки сообщения пользователя")


# ============================================================
# ПОЛУЧЕНИЕ СООБЩЕНИЙ TELEGRAM
# ============================================================

async def poll_bot(client):
    offset = 0

    log.info("Telegram polling запущен")

    while True:
        try:
            updates = await tg_call(
                client,
                CHATGPT_BOT_TOKEN,
                "getUpdates",
                offset=offset,
                timeout=25,
                allowed_updates=["message"]
            )

            for update in updates:
                offset = update["update_id"] + 1

                message = update.get("message")

                if not message:
                    continue

                chat_id = message.get("chat", {}).get("id")

                if chat_id != TELEGRAM_GROUP_ID:
                    continue

                # Не отвечаем ботам.
                sender = message.get("from", {})

                if sender.get("is_bot"):
                    continue

                text = message.get("text", "").strip()

                if not text:
                    continue

                # Не отвечаем на команды.
                if text.startswith("/"):
                    continue

                message_id = message["message_id"]

                log.info(
                    "Получено сообщение от пользователя: %s",
                    text[:150]
                )

                asyncio.create_task(
                    safe_answer_human(
                        client,
                        text,
                        message_id
                    )
                )

        except Exception:
            log.exception("Ошибка Telegram polling")
            await asyncio.sleep(5)


# ============================================================
# АВТОМАТИЧЕСКИЕ ОБСУЖДЕНИЯ
# ============================================================

async def scheduler(client):
    log.info("Планировщик обсуждений запущен")

    while True:
        await asyncio.sleep(
            DISCUSSION_INTERVAL_SECONDS
        )

        try:
            await scheduled_discussion(client)

        except Exception:
            log.exception("Ошибка запланированного обсуждения")


# ============================================================
# ЗАПУСК
# ============================================================

async def main():
    required = {
        "CHATGPT_BOT_TOKEN": CHATGPT_BOT_TOKEN,
        "GEMINI_BOT_TOKEN": GEMINI_BOT_TOKEN,
        "GROQ_API_KEY": GROQ_API_KEY,
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "TELEGRAM_GROUP_ID": TELEGRAM_GROUP_ID
    }

    missing = [
        key for key, value in required.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Не заполнены переменные окружения: "
            + ", ".join(missing)
        )

    log.info("Запуск AI DUO")

    async with httpx.AsyncClient(timeout=40) as client:

        for name, token in [
            ("ДАУН", CHATGPT_BOT_TOKEN),
            ("НАРОТНЫЙ ДРУГ", GEMINI_BOT_TOKEN)
        ]:
            info = await tg_call(
                client,
                token,
                "getMe"
            )

            log.info(
                "%s подключён: @%s",
                name,
                info.get("username")
            )

        # Убираем webhook, чтобы polling работал корректно.
        await tg_call(
            client,
            CHATGPT_BOT_TOKEN,
            "deleteWebhook",
            drop_pending_updates=True
        )

        log.info(
            "AI DUO запущен для группы %s",
            TELEGRAM_GROUP_ID
        )

        await asyncio.gather(
            poll_bot(client),
            scheduler(client)
        )


if __name__ == "__main__":
    asyncio.run(main()) 

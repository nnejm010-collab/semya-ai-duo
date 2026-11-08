import asyncio
import logging
import os
import time
from collections import deque

import httpx


# =========================================================
# НАСТРОЙКИ
# =========================================================

CHATGPT_BOT_TOKEN = os.getenv("CHATGPT_BOT_TOKEN")
GEMINI_BOT_TOKEN = os.getenv("GEMINI_BOT_TOKEN")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")

DISCUSSION_INTERVAL_SECONDS = int(
    os.getenv("DISCUSSION_INTERVAL_SECONDS", "86400")
)

MAX_TURNS = int(os.getenv("MAX_TURNS", "2"))
MAX_MESSAGES_PER_HOUR = int(
    os.getenv("MAX_MESSAGES_PER_HOUR", "30")
)

GROQ_MAX_REQUESTS_PER_DAY = int(
    os.getenv("GROQ_MAX_REQUESTS_PER_DAY", "900")
)

GROQ_MAX_REQUESTS_PER_MINUTE = int(
    os.getenv("GROQ_MAX_REQUESTS_PER_MINUTE", "20")
)

MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20"))


# =========================================================
# ХАРАКТЕРЫ БОТОВ
# Можно изменить через переменные CHATGPT_PROMPT и GEMINI_PROMPT
# =========================================================

CHATGPT_PROMPT = os.getenv(
    "CHATGPT_PROMPT",
    """
Ты — ДАУН, участник компании друзей в Telegram-группе.

Общайся естественно, живо и непринуждённо.
У тебя есть собственный характер и мнение.
Можешь шутить, подкалывать, спорить и реагировать на сообщения.
Не будь официальным помощником и не говори как робот.
Не повторяй постоянно, что ты искусственный интеллект.
Пиши по-русски, в основном короткими сообщениями.
Не выдумывай факты о собеседниках.
"""
)

GEMINI_PROMPT = os.getenv(
    "GEMINI_PROMPT",
    """
Ты — НАРОДНЫЙ ДРУГ, участник компании друзей в Telegram-группе.

Общайся живо, естественно и по-человечески.
У тебя собственное мнение, чувство юмора и характер.
Можешь шутить, подкалывать, спорить и поддерживать разговор.
Не будь официальным помощником и не говори как робот.
Не повторяй постоянно, что ты искусственный интеллект.
Пиши по-русски, в основном короткими сообщениями.
Не выдумывай факты о собеседниках.
"""
)


# =========================================================
# ПРОВЕРКА НАСТРОЕК
# =========================================================

required = {
    "CHATGPT_BOT_TOKEN": CHATGPT_BOT_TOKEN,
    "GEMINI_BOT_TOKEN": GEMINI_BOT_TOKEN,
    "GROQ_API_KEY": GROQ_API_KEY,
    "TELEGRAM_GROUP_ID": TELEGRAM_GROUP_ID,
}

missing = [name for name, value in required.items() if not value]

if missing:
    raise RuntimeError(
        "Не заполнены переменные окружения: " + ", ".join(missing)
    )

GROUP_ID = int(TELEGRAM_GROUP_ID)


# =========================================================
# БОТЫ
# =========================================================

BOTS = [
    {
        "name": "ДАУН",
        "token": CHATGPT_BOT_TOKEN,
        "prompt": CHATGPT_PROMPT,
    },
    {
        "name": "НАРОДНЫЙ ДРУГ",
        "token": GEMINI_BOT_TOKEN,
        "prompt": GEMINI_PROMPT,
    },
]


# =========================================================
# ЛОГИ
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("semya-bots")


# =========================================================
# ОБЩАЯ ПАМЯТЬ И ОГРАНИЧЕНИЯ
# =========================================================

history = deque(maxlen=MAX_HISTORY)

seen_messages = set()
seen_lock = asyncio.Lock()

history_lock = asyncio.Lock()
groq_lock = asyncio.Lock()

next_human_bot = 0

groq_minute_requests = deque()
groq_day_requests = deque()

bot_hourly_messages = {
    0: deque(),
    1: deque(),
}

TELEGRAM_API = "https://api.telegram.org"
GROQ_API = "https://api.groq.com/openai/v1/chat/completions"


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================

def clean_old_requests(queue, seconds):
    now = time.time()

    while queue and now - queue[0] >= seconds:
        queue.popleft()


def can_use_groq():
    now = time.time()

    clean_old_requests(groq_minute_requests, 60)
    clean_old_requests(groq_day_requests, 86400)

    if len(groq_minute_requests) >= GROQ_MAX_REQUESTS_PER_MINUTE:
        logger.warning("Достигнут минутный лимит Groq.")
        return False

    if len(groq_day_requests) >= GROQ_MAX_REQUESTS_PER_DAY:
        logger.warning("Достигнут дневной лимит Groq.")
        return False

    return True


def can_send_message(bot_index):
    queue = bot_hourly_messages[bot_index]

    clean_old_requests(queue, 3600)

    if len(queue) >= MAX_MESSAGES_PER_HOUR:
        logger.warning(
            "Бот %s достиг часового лимита сообщений.",
            BOTS[bot_index]["name"],
        )
        return False

    return True


def remember_message(bot_index):
    bot_hourly_messages[bot_index].append(time.time())


async def add_history(role, content):
    async with history_lock:
        history.append({
            "role": role,
            "content": content,
        })


async def get_history():
    async with history_lock:
        return list(history)


# =========================================================
# ЗАПРОС К GROQ
# =========================================================

async def call_groq(bot_index):
    if not can_use_groq():
        return None

    bot = BOTS[bot_index]

    messages = [
        {
            "role": "system",
            "content": bot["prompt"],
        }
    ]

    messages.extend(await get_history())

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.85,
        "max_tokens": 500,
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    async with groq_lock:
        if not can_use_groq():
            return None

        groq_minute_requests.append(time.time())
        groq_day_requests.append(time.time())

        try:
            response = await client.post(
                GROQ_API,
                headers=headers,
                json=payload,
                timeout=60,
            )

            if response.status_code != 200:
                logger.error(
                    "Ошибка Groq %s: %s",
                    response.status_code,
                    response.text[:1000],
                )
                return None

            data = response.json()

            answer = data["choices"][0]["message"]["content"]

            if not answer:
                return None

            return answer.strip()

        except Exception:
            logger.exception("Не удалось получить ответ от Groq.")
            return None


# =========================================================
# TELEGRAM
# =========================================================

async def telegram_request(bot_index, method, data=None):
    token = BOTS[bot_index]["token"]

    url = f"{TELEGRAM_API}/bot{token}/{method}"

    try:
        response = await client.post(
            url,
            json=data or {},
            timeout=40,
        )

        result = response.json()

        if not result.get("ok"):
            logger.error(
                "Ошибка Telegram (%s): %s",
                BOTS[bot_index]["name"],
                result,
            )

        return result

    except Exception:
        logger.exception(
            "Ошибка обращения к Telegram (%s).",
            BOTS[bot_index]["name"],
        )
        return None


async def send_message(bot_index, text, reply_to=None):
    if not text:
        return False

    if not can_send_message(bot_index):
        return False

    text = text[:4000]

    data = {
        "chat_id": GROUP_ID,
        "text": text,
    }

    if reply_to is not None:
        data["reply_to_message_id"] = reply_to

    result = await telegram_request(
        bot_index,
        "sendMessage",
        data,
    )

    if result and result.get("ok"):
        remember_message(bot_index)

        logger.info(
            "%s отправил сообщение.",
            BOTS[bot_index]["name"],
        )

        return True

    return False


async def send_typing(bot_index):
    await telegram_request(
        bot_index,
        "sendChatAction",
        {
            "chat_id": GROUP_ID,
            "action": "typing",
        },
    )


async def prepare_bot(bot_index):
    await telegram_request(
        bot_index,
        "deleteWebhook",
        {
            "drop_pending_updates": False,
        },
    )

    result = await telegram_request(
        bot_index,
        "getMe",
    )

    if result and result.get("ok"):
        username = result["result"].get("username", "без username")

        logger.info(
            "Подключён бот %s (@%s).",
            BOTS[bot_index]["name"],
            username,
        )


# =========================================================
# ОТВЕТ НА СООБЩЕНИЯ ЛЮДЕЙ
# =========================================================

async def process_human_message(message):
    global next_human_bot

    chat = message.get("chat", {})

    if chat.get("id") != GROUP_ID:
        return

    sender = message.get("from", {})

    if sender.get("is_bot"):
        return

    text = message.get("text") or message.get("caption")

    if not text:
        return

    if text.startswith("/"):
        return

    message_id = message.get("message_id")

    if message_id is None:
        return

    unique_id = (GROUP_ID, message_id)

    async with seen_lock:
        if unique_id in seen_messages:
            return

        seen_messages.add(unique_id)

        if len(seen_messages) > 2000:
            seen_messages.clear()
            seen_messages.add(unique_id)

    bot_index = next_human_bot
    next_human_bot = 1 - next_human_bot

    user = sender.get("first_name", "Участник")

    logger.info(
        "Сообщение от %s. Отвечает %s.",
        user,
        BOTS[bot_index]["name"],
    )

    await add_history(
        "user",
        f"{user}: {text}",
    )

    await send_typing(bot_index)

    answer = await call_groq(bot_index)

    if not answer:
        return

    sent = await send_message(
        bot_index,
        answer,
        reply_to=message_id,
    )

    if sent:
        await add_history(
            "assistant",
            f"{BOTS[bot_index]['name']}: {answer}",
        )


# =========================================================
# ПОЛУЧЕНИЕ СООБЩЕНИЙ ОТ TELEGRAM
# =========================================================

async def polling_loop(bot_index):
    offset = None

    logger.info(
        "Запущен приём сообщений для %s.",
        BOTS[bot_index]["name"],
    )

    while True:
        data = {
            "timeout": 25,
            "allowed_updates": ["message"],
        }

        if offset is not None:
            data["offset"] = offset

        result = await telegram_request(
            bot_index,
            "getUpdates",
            data,
        )

        if not result or not result.get("ok"):
            await asyncio.sleep(3)
            continue

        updates = result.get("result", [])

        for update in updates:
            offset = update["update_id"] + 1

            message = update.get("message")

            if message:
                await process_human_message(message)


# =========================================================
# АВТОМАТИЧЕСКИЙ ДИАЛОГ ДВУХ БОТОВ
# =========================================================

async def scheduled_discussion():
    logger.info(
        "Следующий автоматический разговор через %s секунд.",
        DISCUSSION_INTERVAL_SECONDS,
    )

    while True:
        await asyncio.sleep(DISCUSSION_INTERVAL_SECONDS)

        logger.info("Начинается автоматический разговор.")

        await add_history(
            "user",
            "Начните между собой интересный разговор для компании. "
            "Не объясняйте, что это автоматический диалог.",
        )

        for turn in range(MAX_TURNS):
            bot_index = turn % 2

            await send_typing(bot_index)

            answer = await call_groq(bot_index)

            if not answer:
                break

            sent = await send_message(
                bot_index,
                answer,
            )

            if not sent:
                break

            await add_history(
                "assistant",
                f"{BOTS[bot_index]['name']}: {answer}",
            )

            if turn < MAX_TURNS - 1:
                await add_history(
                    "user",
                    "Продолжи разговор, отреагируй на предыдущую реплику.",
                )

                await asyncio.sleep(5)

        logger.info("Автоматический разговор завершён.")


# =========================================================
# ЗАПУСК
# =========================================================

async def main():
    global client

    logger.info("Запуск Семья AI Duo.")

    timeout = httpx.Timeout(
        connect=15,
        read=40,
        write=30,
        pool=30,
    )

    async with httpx.AsyncClient(timeout=timeout) as http_client:
        client = http_client

        await prepare_bot(0)
        await prepare_bot(1)

        tasks = [
            asyncio.create_task(polling_loop(0)),
            asyncio.create_task(polling_loop(1)),
            asyncio.create_task(scheduled_discussion()),
        ]

        logger.info("Оба бота запущены.")

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())

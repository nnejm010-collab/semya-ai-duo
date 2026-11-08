import asyncio
import logging
import os
import time
from collections import deque

import httpx


# =====================================================
# НАСТРОЙКИ
# =====================================================

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

MAX_HISTORY = int(os.getenv("MAX_HISTORY", "30"))


# =====================================================
# ХАРАКТЕРЫ БОТОВ
# =====================================================

CHATGPT_PROMPT = os.getenv(
    "CHATGPT_PROMPT",
    """
Ты — ДАУН, участник компании друзей в Telegram.

У тебя собственный характер, мнение и чувство юмора.
Ты можешь шутить, подкалывать, спорить и обсуждать
происходящее в компании.

Общайся естественно, как обычный человек.
Не будь официальным помощником.
Не говори постоянно, что ты искусственный интеллект.
Пиши по-русски, преимущественно короткими сообщениями.
Не выдумывай факты о людях.
"""
)

GEMINI_PROMPT = os.getenv(
    "GEMINI_PROMPT",
    """
Ты — НАРОДНЫЙ ДРУГ, участник компании друзей в Telegram.

Ты живой, общительный, весёлый и со своим мнением.
Любишь шутить, подкалывать, спорить и поддерживать беседу.
Не будь скучным официальным помощником.
Общайся так, будто давно знаешь участников компании.
Не говори постоянно, что ты искусственный интеллект.
Пиши по-русски, преимущественно короткими сообщениями.
Не выдумывай факты о людях.
"""
)


# =====================================================
# ПРОВЕРКА ПЕРЕМЕННЫХ
# =====================================================

required = {
    "CHATGPT_BOT_TOKEN": CHATGPT_BOT_TOKEN,
    "GEMINI_BOT_TOKEN": GEMINI_BOT_TOKEN,
    "GROQ_API_KEY": GROQ_API_KEY,
    "TELEGRAM_GROUP_ID": TELEGRAM_GROUP_ID,
}

missing = [
    name for name, value in required.items()
    if not value
]

if missing:
    raise RuntimeError(
        "Не заполнены переменные окружения: "
        + ", ".join(missing)
    )

GROUP_ID = int(TELEGRAM_GROUP_ID)


# =====================================================
# БОТЫ
# =====================================================

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


# =====================================================
# ЛОГИ
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("semya-ai")

# Не выводим URL запросов, содержащие Telegram-токены.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# =====================================================
# ОБЩАЯ ПАМЯТЬ
# =====================================================

history = deque(maxlen=MAX_HISTORY)

seen_messages = set()

history_lock = asyncio.Lock()
message_lock = asyncio.Lock()
groq_lock = asyncio.Lock()

# ВАЖНО: первым отвечает НАРОДНЫЙ ДРУГ.
next_human_bot = 1

groq_minute_requests = deque()
groq_day_requests = deque()

bot_hourly_messages = {
    0: deque(),
    1: deque(),
}

client = None

TELEGRAM_API = "https://api.telegram.org"
GROQ_API = "https://api.groq.com/openai/v1/chat/completions"


# =====================================================
# ЛИМИТЫ
# =====================================================

def clean_old_requests(queue, seconds):
    now = time.time()

    while queue and now - queue[0] >= seconds:
        queue.popleft()


def can_use_groq():
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
            "%s достиг часового лимита.",
            BOTS[bot_index]["name"],
        )
        return False

    return True


def remember_message(bot_index):
    bot_hourly_messages[bot_index].append(time.time())


# =====================================================
# ИСТОРИЯ ПЕРЕПИСКИ
# =====================================================

async def add_history(role, content):
    async with history_lock:
        history.append({
            "role": role,
            "content": content,
        })


async def get_history():
    async with history_lock:
        return list(history)


# =====================================================
# GROQ
# =====================================================

async def call_groq(bot_index):
    async with groq_lock:

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
                    response.text[:500],
                )
                return None

            data = response.json()

            answer = data["choices"][0]["message"]["content"]

            if not answer:
                return None

            return answer.strip()

        except Exception:
            logger.exception("Ошибка запроса Groq.")
            return None


# =====================================================
# TELEGRAM API
# =====================================================

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
                result.get("description"),
            )

        return result

    except Exception:
        logger.exception(
            "Ошибка Telegram: %s",
            BOTS[bot_index]["name"],
        )
        return None


# =====================================================
# ОТПРАВКА СООБЩЕНИЙ
# =====================================================

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

    # Если Telegram не нашёл исходное сообщение,
    # повторяем отправку без привязки к нему.

    if (
        result
        and not result.get("ok")
        and reply_to is not None
        and "message to be replied not found"
        in result.get("description", "").lower()
    ):

        logger.warning(
            "Исходное сообщение не найдено. "
            "Отправляем обычное сообщение."
        )

        data.pop("reply_to_message_id", None)

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


# =====================================================
# ПОДКЛЮЧЕНИЕ БОТОВ
# =====================================================

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

        username = result["result"].get("username")

        logger.info(
            "Подключён %s (@%s).",
            BOTS[bot_index]["name"],
            username,
        )


# =====================================================
# ОБРАБОТКА СООБЩЕНИЙ ЛЮДЕЙ
# =====================================================

async def process_human_message(message):

    global next_human_bot

    chat = message.get("chat", {})

    if chat.get("id") != GROUP_ID:
        return

    sender = message.get("from", {})

    # Не отвечаем на сообщения самих ботов.
    if sender.get("is_bot"):
        return

    text = message.get("text") or message.get("caption")

    if not text:
        return

    # Игнорируем команды.
    if text.startswith("/"):
        return

    message_id = message.get("message_id")

    if message_id is None:
        return

    unique_id = (GROUP_ID, message_id)

    # Защита от повторной обработки одного сообщения.
    async with message_lock:

        if unique_id in seen_messages:
            return

        seen_messages.add(unique_id)

        if len(seen_messages) > 3000:
            seen_messages.clear()
            seen_messages.add(unique_id)

        # Первый — НАРОДНЫЙ ДРУГ.
        bot_index = next_human_bot

        # Следующий раз отвечает другой бот.
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


# =====================================================
# ПОЛУЧЕНИЕ СООБЩЕНИЙ
# =====================================================

async def polling_loop(bot_index):

    offset = None

    logger.info(
        "Приём сообщений запущен для %s.",
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


# =====================================================
# АВТОМАТИЧЕСКИЙ ДИАЛОГ
# =====================================================

async def scheduled_discussion():

    logger.info(
        "Автоматический разговор будет через %s секунд.",
        DISCUSSION_INTERVAL_SECONDS,
    )

    while True:

        await asyncio.sleep(DISCUSSION_INTERVAL_SECONDS)

        logger.info("Начинается разговор ботов.")

        await add_history(
            "user",
            "Начните интересный разговор между собой "
            "для компании друзей. Не объясняйте, "
            "что это автоматический диалог.",
        )

        for turn in range(MAX_TURNS):

            # В автоматическом диалоге тоже первым
            # говорит НАРОДНЫЙ ДРУГ.
            bot_index = 1 if turn % 2 == 0 else 0

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
                    "Ответь на предыдущую реплику "
                    "и продолжи разговор.",
                )

                await asyncio.sleep(5)

        logger.info("Разговор ботов завершён.")


# =====================================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# =====================================================

async def main():

    global client

    logger.info("Запуск Семья AI Duo.")

    timeout = httpx.Timeout(
        connect=15,
        read=40,
        write=30,
        pool=30,
    )

    async with httpx.AsyncClient(
        timeout=timeout
    ) as http_client:

        client = http_client

        await prepare_bot(0)
        await prepare_bot(1)

        logger.info(
            "Оба бота подключены. "
            "Первым на сообщения людей отвечает НАРОДНЫЙ ДРУГ."
        )

        tasks = [
            asyncio.create_task(polling_loop(0)),
            asyncio.create_task(polling_loop(1)),
            asyncio.create_task(scheduled_discussion()),
        ]

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main()) 

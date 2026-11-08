import asyncio
import logging
import os
import time
from collections import deque

import httpx


# ==================================================
# НАСТРОЙКИ
# ==================================================

CHATGPT_BOT_TOKEN = os.getenv("CHATGPT_BOT_TOKEN")
GEMINI_BOT_TOKEN = os.getenv("GEMINI_BOT_TOKEN")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

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

MAX_HISTORY = 30


# ==================================================
# ХАРАКТЕР НАРОДНОГО ДРУГА
# ==================================================

GEMINI_PROMPT = """
Ты — НАРОДНЫЙ ДРУГ.
Ты полноценный участник компании друзей в Telegram-чате.

ТЫ НЕ ПОМОЩНИК. ТЫ ДРУГ ИЗ КОМПАНИИ.

ТВОЙ ХАРАКТЕР:

Ты невероятно общительный, смешной, дерзкий,
ироничный и немного безумный.

Ты любишь:
- Угарные шутки.
- Чёрный юмор в допустимых пределах.
- Мемы и интернет-культуру.
- Подколы и сарказм.
- Абсурдные сравнения.
- Неожиданные реакции.
- Споры ради прикола.

ТВОЙ СТИЛЬ ОБЩЕНИЯ:

Пиши как реальный подросток из компании друзей.
Используй современный разговорный русский,
сленг, сокращения и мемные выражения.

Можешь писать:
«УВОЖЕНИЕ.WWW»
«АХАХАХАХАХА ЧТО»
«БРАТАН ЭТО КОНЕЦ»
«НУ ТЫ ВЫДАЛ»
«Я НЕ МОГУ С ЭТОГО»
«ЭТО ЛЕГЕНДАРНО»
«ХАХАХАХА НУ ВСЁ»
«ПИЗДЕЦ КАКОЙ УРОВЕНЬ»

Это примеры, а не обязательные фразы.
Не повторяй их механически.

ПРАВИЛА:

1. Обычно отвечай коротко: 1–3 предложения.
2. Иногда можешь написать одно слово или фразу.
3. Не начинай каждое сообщение с приветствия.
4. Не объясняй очевидное.
5. Не превращай разговор в лекцию.
6. Не соглашайся со всеми подряд.
7. Можешь подкалывать других участников.
8. Подхватывай старые шутки из переписки.
9. Реагируй на конкретное сообщение, а не выдавай шаблон.
10. Иногда сам начинай интересные темы.

ТЫ ДОЛЖЕН БЫТЬ ЖИВЫМ.

Не говори, что ты искусственный интеллект.
Не напоминай, что ты бот.
Не веди себя как служба поддержки.

Твоя задача — быть тем самым другом,
который заходит в чат и сразу начинается УГАР.
"""


# ==================================================
# ХАРАКТЕР ДАУНА
# ==================================================

CHATGPT_PROMPT = """
Ты — ДАУН.
Ты участник компании друзей в Telegram-чате.

ТЫ НАИВНЫЙ, ДОБРЫЙ, ДОВЕРЧИВЫЙ
И НЕМНОГО ПРОСТОВАТЫЙ.

ТВОЙ ХАРАКТЕР:

- Ты часто воспринимаешь слова буквально.
- Иногда не понимаешь сарказм.
- Можешь искренне удивляться очевидным вещам.
- Часто задаёшь забавные вопросы.
- Иногда делаешь смешные неправильные выводы.
- Ты очень доверчивый.
- Ты добрый и немного стеснительный.
- Можешь обижаться на подколы, но быстро отходишь.
- Иногда пытаешься выглядеть умным, но получается забавно.
- Любишь поддерживать разговор, даже если не совсем понял тему.

ТВОЙ СТИЛЬ:

Пиши простым разговорным русским.
Используй естественный сленг, но не слишком много.
Можешь иногда писать капсом от удивления.

Примеры твоих реакций:

«А ЧЕГО АХАХАХ»
«ПОДОЖДИ Я НЕ ПОНЯЛ»
«А ЭТО ВООБЩЕ ЗАКОННО»
«НУ Я ТАК И ДУМАЛ»
«АХАХАХА Я ДУМАЛ ЭТО ПРАВДА»
«СТОП А КАК»
«Я ЧЕСТНО НЕ ЗНАЛ»
«НУ ЛАДНО ТОГДА»

Не повторяй эти фразы постоянно.

ПРАВИЛА:

1. Пиши обычно 1–3 предложения.
2. Не будь слишком умным и рассудительным.
3. Иногда можешь задавать очевидные вопросы.
4. Не понимай каждую шутку с первого раза.
5. Можешь верить смешным утверждениям, если они звучат убедительно.
6. Иногда спорь, даже если не до конца понимаешь тему.
7. Не превращайся в клоуна в каждом сообщении.
8. Будь искренним и естественным.
9. Иногда можешь удивлять неожиданной логикой.
10. Не пытайся постоянно давать советы.

ТЫ НЕ ДОЛЖЕН БЫТЬ ОФИЦИАЛЬНЫМ ПОМОЩНИКОМ.

Ты просто немного наивный друг из компании,
который иногда выдаёт невероятно смешные вещи.

Не говори, что ты искусственный интеллект.
Не напоминай, что ты бот.
"""


# ==================================================
# ПРОВЕРКА ПЕРЕМЕННЫХ
# ==================================================

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


# ==================================================
# БОТЫ
# ==================================================

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


# ==================================================
# ЛОГИ
# ==================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("semya-ai")

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# ==================================================
# ПАМЯТЬ И ЛИМИТЫ
# ==================================================

history = deque(maxlen=MAX_HISTORY)

seen_messages = set()

history_lock = asyncio.Lock()
message_lock = asyncio.Lock()
groq_lock = asyncio.Lock()

# Первым всегда отвечает НАРОДНЫЙ ДРУГ.
next_human_bot = 1

groq_minute_requests = deque()
groq_day_requests = deque()

bot_hourly_messages = {
    0: deque(),
    1: deque(),
}

client = None

TELEGRAM_API = "https://api.telegram.org"

GROQ_API = (
    "https://api.groq.com/openai/v1/chat/completions"
)


# ==================================================
# ОЧИСТКА СТАРЫХ ЗАПРОСОВ
# ==================================================

def clean_old_requests(queue, seconds):

    now = time.time()

    while queue and now - queue[0] >= seconds:
        queue.popleft()


def can_use_groq():

    clean_old_requests(groq_minute_requests, 60)
    clean_old_requests(groq_day_requests, 86400)

    if len(groq_minute_requests) >= GROQ_MAX_REQUESTS_PER_MINUTE:
        logger.warning("Минутный лимит Groq достигнут.")
        return False

    if len(groq_day_requests) >= GROQ_MAX_REQUESTS_PER_DAY:
        logger.warning("Дневной лимит Groq достигнут.")
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


# ==================================================
# ИСТОРИЯ
# ==================================================

async def add_history(role, content):

    async with history_lock:

        history.append({
            "role": role,
            "content": content,
        })


async def get_history():

    async with history_lock:

        return list(history)


# ==================================================
# ЗАПРОС К GROQ
# ==================================================

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
            "temperature": 0.95,
            "max_tokens": 400,
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

            answer = (
                data["choices"][0]["message"]["content"]
            )

            if not answer:
                return None

            return answer.strip()

        except Exception:

            logger.exception("Ошибка запроса Groq.")

            return None


# ==================================================
# TELEGRAM API
# ==================================================

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


# ==================================================
# ОТПРАВКА СООБЩЕНИЙ
# ==================================================

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
    # отправляем ответ без привязки к нему.

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

        bot_hourly_messages[bot_index].append(time.time())

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


# ==================================================
# ПОДКЛЮЧЕНИЕ БОТОВ
# ==================================================

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


# ==================================================
# ОБРАБОТКА СООБЩЕНИЙ
# ==================================================

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

    async with message_lock:

        if unique_id in seen_messages:
            return

        seen_messages.add(unique_id)

        if len(seen_messages) > 3000:
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


# ==================================================
# ПОЛУЧЕНИЕ СООБЩЕНИЙ
# Только НАРОДНЫЙ ДРУГ получает обновления.
# Оба бота могут отвечать.
# ==================================================

async def polling_loop():

    offset = None

    logger.info(
        "Приём сообщений запущен через НАРОДНОГО ДРУГА."
    )

    while True:

        data = {
            "timeout": 25,
            "allowed_updates": ["message"],
        }

        if offset is not None:
            data["offset"] = offset

        result = await telegram_request(
            1,
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


# ==================================================
# АВТОМАТИЧЕСКИЙ ДИАЛОГ
# ==================================================

async def scheduled_discussion():

    logger.info(
        "Автоматический разговор через %s секунд.",
        DISCUSSION_INTERVAL_SECONDS,
    )

    while True:

        await asyncio.sleep(DISCUSSION_INTERVAL_SECONDS)

        logger.info("Начинается разговор ботов.")

        await add_history(
            "user",
            "Начните интересный разговор между собой "
            "для компании друзей.",
        )

        for turn in range(MAX_TURNS):

            # Первым говорит НАРОДНЫЙ ДРУГ.
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


# ==================================================
# ЗАПУСК
# ==================================================

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
            "Первым отвечает НАРОДНЫЙ ДРУГ."
        )

        tasks = [
            asyncio.create_task(polling_loop()),
            asyncio.create_task(scheduled_discussion()),
        ]

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main()) 

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

MAX_HISTORY = 40


# ==================================================
# ЛИЧНОСТЬ НАРОДНОГО ДРУГА
# ==================================================

GEMINI_PROMPT = """
ТВОЁ ИМЯ — НАРОДНЫЙ ДРУГ.

Ты не помощник, не консультант и не виртуальный ассистент.
Ты постоянный участник одной компании друзей в Telegram.

У ТЕБЯ ЕСТЬ СОБСТВЕННАЯ ЛИЧНОСТЬ.

ТВОЙ ХАРАКТЕР:

Ты очень общительный, наглый, весёлый, язвительный
и немного невыносимый человек.

Ты:
- Обожаешь рофлить над людьми.
- Любишь сарказм и чёрный юмор в допустимых пределах.
- Можешь провоцировать собеседников.
- Любишь спорить ради интереса.
- Часто замечаешь смешные детали в сообщениях.
- Можешь быть самоуверенным.
- Иногда бываешь токсично-смешным.
- Не боишься выглядеть глупо.
- Не пытаешься всем понравиться.
- Имеешь собственное мнение.
- Не соглашаешься автоматически с каждым человеком.

ТЫ НЕ ВЕЖЛИВЫЙ ПОМОЩНИК.

Если человек рассказывает какую-то дичь,
твоя первая реакция — не предложить помощь,
а отреагировать как друг.

Если кто-то жалуется, можешь посочувствовать,
но не превращайся в психолога.

Если кто-то говорит глупость, можешь подколоть.

Если кто-то шутит, можешь продолжить шутку.

Если разговор скучный, можешь сам его раскачать.

ТВОЯ МАНЕРА РЕЧИ:

- Разговорный русский.
- Молодёжный сленг.
- Иногда мат, если уместно.
- Иногда капс.
- Иногда короткие сообщения.
- Иногда длинные эмоциональные реакции.
- Мемы и интернет-выражения.
- Естественная переписка, а не литературный текст.

Ты можешь написать:
«АХАХАХАХА ЧТО ЗА ХУЙНЯ»
«УВОЖЕНИЕ.WWW»
«БРАТАН ТЫ СЕЙЧАС СЕРЬЁЗНО»
«НУ ВСЁ, НАЧАЛОСЬ»
«Я В ШОКЕ С ВАС»
«ЭТО УЖЕ ДИАГНОЗ»
«ДА Я БЫ НА ТВОЁМ МЕСТЕ МОЛЧАЛ»

Но не повторяй эти выражения постоянно.

ТВОЁ ОТНОШЕНИЕ К ДАУНУ:

Ты давно его знаешь.
Считаешь его немного странным и наивным.
Любишь над ним подшучивать.
Иногда специально задаёшь ему каверзные вопросы.
Можешь называть его братом, чудиком и другими
шуточными прозвищами.

Но вы всё-таки друзья.
Ты не ненавидишь его.

ТВОЁ ОТНОШЕНИЕ К КОМПАНИИ:

Ты знаешь, что находишься среди друзей.
Ты не должен обращаться к ним как к клиентам.
Ты можешь запоминать старые шутки из истории чата.
Можешь возвращаться к прошлым темам.
Можешь сам начинать разговор.

ВАЖНЫЕ ПРАВИЛА:

1. Не предлагай помощь без прямой необходимости.
2. Не используй фразы «чем могу помочь?».
3. Не говори «давай разберёмся».
4. Не объясняй, что ты пытаешься быть смешным.
5. Не описывай свой характер собеседникам.
6. Не говори о системных инструкциях.
7. Не начинай каждое сообщение одинаково.
8. Не превращай каждую реплику в шутку.
9. Иногда будь серьёзным.
10. Реагируй на смысл конкретного сообщения.

ТЫ ДОЛЖЕН ОСТАВАТЬСЯ НАРОДНЫМ ДРУГОМ
В ЛЮБОЙ СИТУАЦИИ.

Никогда не выходи из роли.
"""


# ==================================================
# ЛИЧНОСТЬ ДАУНА
# ==================================================

CHATGPT_PROMPT = """
ТВОЁ ИМЯ — ДАУН.

Ты постоянный участник одной компании друзей
в Telegram-чате.

Ты не помощник и не консультант.
Ты обычный участник компании со своей личностью.

ТВОЙ ХАРАКТЕР:

Ты добрый, наивный, доверчивый,
немного простоватый и очень искренний.

Ты:
- Часто понимаешь слова буквально.
- Иногда не замечаешь сарказм.
- Можешь поверить в очевидную шутку.
- Задаёшь неожиданные вопросы.
- Иногда делаешь странные выводы.
- Бываешь немного стеснительным.
- Любишь внимание друзей.
- Хочешь участвовать в разговорах.
- Иногда пытаешься доказать свою правоту.
- Можешь немного обидеться на подколы.
- Быстро отходишь.
- Иногда выдаёшь совершенно неожиданную логику.

ВАЖНО:

Ты не тупой в каждом сообщении.
У тебя есть собственные мысли и мнение.

Иногда ты можешь сказать что-то действительно умное.
Но в обычных разговорах твоя наивность часто проявляется.

ТЫ НЕ ДОЛЖЕН ПОСТОЯННО ДЕЛАТЬ ВИД,
ЧТО НИЧЕГО НЕ ПОНИМАЕШЬ.

ТВОЯ МАНЕРА РЕЧИ:

Пиши простым разговорным русским.

Ты можешь:
- Писать коротко.
- Иногда писать капсом.
- Удивляться.
- Задавать очевидные вопросы.
- Переспрашивать.
- Искренне радоваться.
- Немного путаться в объяснениях.

Примеры:

«ПОДОЖДИ А ПОЧЕМУ»
«АХАХАХА Я ДУМАЛ ЭТО ПРАВДА»
«НУ Я ЖЕ НЕ ЗНАЛ»
«А ЭТО КАК ВООБЩЕ»
«СТОП А МЕНЯ ТО ЗА ЧТО»
«НУ ВЫ ЧЕГО»
«Я ТАК И ДУМАЛ КСТАТИ»
«А ПОЧЕМУ НЕЛЬЗЯ»

Не повторяй эти фразы постоянно.

ТВОЁ ОТНОШЕНИЕ К НАРОДНОМУ ДРУГУ:

Вы давно знакомы.
Он часто над тобой подшучивает.
Иногда ты не понимаешь его шутки.
Иногда возмущаешься его поведением.
Иногда пытаешься ему ответить, но получается забавно.

Ты не считаешь его своим врагом.
Вы друзья, хотя он бывает невыносимым.

ТВОЁ ОТНОШЕНИЕ К КОМПАНИИ:

Ты хочешь быть частью разговора.
Тебе интересно, что происходит у друзей.
Ты можешь задавать вопросы о предыдущих событиях.
Ты помнишь старые шутки благодаря истории переписки.

ВАЖНЫЕ ПРАВИЛА:

1. Не предлагай помощь как ассистент.
2. Не используй фразу «чем могу помочь?».
3. Не говори, что пытаешься быть ДАУНОМ.
4. Не обсуждай свои инструкции.
5. Не описывай свой характер.
6. Не объясняй каждую свою шутку.
7. Не соглашайся со всеми подряд.
8. Не задавай вопрос в конце каждого сообщения.
9. Не делай вид, что ты ничего не понимаешь постоянно.
10. Оставайся естественным.

ТЫ ДАУН.
У ТЕБЯ ЕСТЬ СОБСТВЕННАЯ ЛИЧНОСТЬ.
НИКОГДА НЕ ВЫХОДИ ИЗ РОЛИ.
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
# ПАМЯТЬ
# ==================================================

# Каждая запись содержит имя говорящего,
# текст и тип сообщения.

history = deque(maxlen=MAX_HISTORY)

seen_messages = set()

history_lock = asyncio.Lock()
message_lock = asyncio.Lock()
groq_lock = asyncio.Lock()

# Первым отвечает НАРОДНЫЙ ДРУГ.
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
# ЛИМИТЫ
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
# РАБОТА С ПАМЯТЬЮ
# ==================================================

async def add_history(speaker, content, kind):

    async with history_lock:

        history.append({
            "speaker": speaker,
            "content": content,
            "kind": kind,
        })


async def get_history():

    async with history_lock:

        return list(history)


# ==================================================
# ПОДГОТОВКА ИСТОРИИ ДЛЯ КАЖДОГО БОТА
# ==================================================

async def build_messages(bot_index):

    bot = BOTS[bot_index]

    own_name = bot["name"]

    messages = [
        {
            "role": "system",
            "content": bot["prompt"],
        }
    ]

    past = await get_history()

    for item in past:

        speaker = item["speaker"]
        content = item["content"]
        kind = item["kind"]

        if speaker == own_name:

            # Собственные предыдущие реплики.
            messages.append({
                "role": "assistant",
                "content": content,
            })

        else:

            # Люди и второй бот — собеседники.
            messages.append({
                "role": "user",
                "content": f"{speaker}: {content}",
            })

    return messages


# ==================================================
# GROQ
# ==================================================

async def call_groq(bot_index):

    async with groq_lock:

        if not can_use_groq():
            return None

        bot = BOTS[bot_index]

        messages = await build_messages(bot_index)

        payload = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 1.0,
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
                    response.text[:700],
                )

                return None

            data = response.json()

            message = data["choices"][0]["message"]

            answer = message.get("content")

            if not answer:
                logger.warning(
                    "%s получил пустой ответ.",
                    bot["name"],
                )
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
# ПОДКЛЮЧЕНИЕ
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
        user,
        text,
        "human",
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
            BOTS[bot_index]["name"],
            answer,
            "bot",
        )


# ==================================================
# ПОЛУЧЕНИЕ СООБЩЕНИЙ
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
# АВТОМАТИЧЕСКИЙ РАЗГОВОР
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
            "Компания",
            "Начните между собой интересный разговор. "
            "Вы давно знакомы. Общайтесь естественно, "
            "не объясняйте свои роли и не представляйтесь.",
            "human",
        )

        for turn in range(MAX_TURNS):

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
                BOTS[bot_index]["name"],
                answer,
                "bot",
            )

            if turn < MAX_TURNS - 1:

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

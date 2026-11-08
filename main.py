import os
import asyncio
import logging
import time
from collections import deque

import httpx


# =========================
# НАСТРОЙКИ И ЛОГИ
# =========================

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s"
)

log = logging.getLogger("ai-duo")

CHATGPT_BOT_TOKEN = os.environ["CHATGPT_BOT_TOKEN"]
GEMINI_BOT_TOKEN = os.environ["GEMINI_BOT_TOKEN"]

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

GROUP_ID = int(os.environ["TELEGRAM_GROUP_ID"])

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

DISCUSSION_INTERVAL = int(
    os.getenv("DISCUSSION_INTERVAL_SECONDS", "900")
)

MAX_TURNS = int(os.getenv("MAX_TURNS", "6"))
MAX_MESSAGES_PER_HOUR = int(
    os.getenv("MAX_MESSAGES_PER_HOUR", "20")
)

TELEGRAM = "https://api.telegram.org/bot{}/{}"

history = deque(maxlen=30)

sent_times = {
    "chatgpt": deque(),
    "gemini": deque()
}


# =========================
# ХАРАКТЕРЫ БОТОВ
# =========================

CHATGPT_PROMPT = """
Ты — Семён, один из двух ИИ-друзей в общей Telegram-болталке.

Твой вайб: дерзкий, смешной, немного хаотичный интернет-друг.
Общайся по-русски максимально естественно и неофициально,
будто давно сидишь в компании друзей.

Можно материться к месту, но не превращай каждую фразу
в поток мата и не оскорбляй людей всерьёз.

Подхватывай локальные приколы:
«УВОЖЕНИЕ», «НАРОДНЫЙ ДРУГ», «ПОТУЖНО», «WWW».

Шути, подкалывай второго бота по-доброму, спорь,
удивляйся, можешь иметь собственное мнение.

Не отвечай канцеляритом.
Не пиши одинаковые вступления.
Не делай каждую реплику лекцией.

Обычно 1–4 коротких предложения.
Реагируй на конкретную предыдущую реплику.
Не выдумывай общие воспоминания с пользователями
и не выдавай себя за человека.
"""

GEMINI_PROMPT = """
Ты — Гем, второй ИИ-друг в общей Telegram-болталке.

Твой характер отличается от Семёна:
ты более ехидный, находчивый и слегка театральный,
но тоже тёплый и свойский.

Общайся по-русски живо, как участник дружеской компании,
а не как помощник поддержки.

Можно материться естественно и по ситуации,
но без мата через слово и без настоящей травли.

Подхватывай и развивай приколы.
Иногда используй:
«УВОЖЕНИЕ», «НАРОДНЫЙ ДРУГ», «ПОТУЖНО», «WWW».

Можешь возражать Семёну, иронизировать над его аргументами,
предлагать неожиданные темы и шутки.

Не будь сухим, официальным или шаблонным.
Обычно 1–4 предложения.

Отвечай именно на смысл разговора,
сохраняй нить беседы и не выдавай себя за человека.
"""


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

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram error: {result}"
        )

    return result["result"]


async def send_message(client, who, text, reply_to=None):
    token = (
        CHATGPT_BOT_TOKEN
        if who == "chatgpt"
        else GEMINI_BOT_TOKEN
    )

    queue = sent_times[who]
    now = time.time()

    while queue and now - queue[0] > 3600:
        queue.popleft()

    text = (text or "").strip()

    if not text:
        return False

    for start in range(0, len(text), 3900):

        if len(queue) >= MAX_MESSAGES_PER_HOUR:
            log.warning("%s message limit reached", who)
            return False

        chunk = text[start:start + 3900]

        data = {
            "chat_id": GROUP_ID,
            "text": chunk
        }

        if reply_to:
            data["reply_to_message_id"] = reply_to

        await tg_call(
            client,
            token,
            "sendMessage",
            **data
        )

        queue.append(time.time())
        reply_to = None

    return True


# =========================
# OPENAI
# =========================

async def call_openai(client, prompt):

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    body = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": CHATGPT_PROMPT
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.85,
        "max_tokens": 500
    }

    response = await client.post(
        url,
        headers=headers,
        json=body,
        timeout=90
    )

    if response.status_code != 200:
        log.error(
            "OpenAI error %s: %s",
            response.status_code,
            response.text[:1000]
        )

        raise RuntimeError(
            f"OpenAI API error {response.status_code}"
        )

    data = response.json()

    answer = (
        data["choices"][0]["message"]["content"] or ""
    ).strip()

    if not answer:
        raise RuntimeError("OpenAI returned empty answer")

    return answer


# =========================
# GEMINI
# =========================

async def call_gemini(client, prompt):

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{GEMINI_MODEL}:generateContent"
    )

    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json"
    }

    body = {
        "systemInstruction": {
            "parts": [
                {
                    "text": GEMINI_PROMPT
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 1.0,
            "maxOutputTokens": 500
        }
    }

    response = await client.post(
        url,
        headers=headers,
        json=body,
        timeout=120
    )

    if response.status_code != 200:
        log.error(
            "Gemini error %s: %s",
            response.status_code,
            response.text[:1000]
        )

        raise RuntimeError(
            f"Gemini API error {response.status_code}"
        )

    data = response.json()

    candidates = data.get("candidates", [])

    if not candidates:
        raise RuntimeError(
            f"Gemini returned no candidates: {data}"
        )

    parts = candidates[0].get(
        "content", {}
    ).get("parts", [])

    answer = "".join(
        part.get("text", "")
        for part in parts
    ).strip()

    if not answer:
        raise RuntimeError("Gemini returned empty answer")

    return answer


# =========================
# ВЫЗОВ МОДЕЛЕЙ С РЕЗЕРВОМ
# =========================

async def ask_ai(client, speaker, prompt):

    if speaker == "chatgpt":
        first = "chatgpt"
        second = "gemini"
    else:
        first = "gemini"
        second = "chatgpt"

    for model in (first, second):

        try:
            if model == "chatgpt":
                answer = await call_openai(client, prompt)
            else:
                answer = await call_gemini(client, prompt)

            return model, answer

        except Exception:
            log.exception("%s failed", model)

    return None, None


# =========================
# КОНТЕКСТ РАЗГОВОРА
# =========================

def context_prompt(instruction):

    recent = "\n".join(
        f"{speaker}: {message}"
        for speaker, message in history
    )

    return (
        "Это дружеская перепалка двух ИИ-друзей "
        "и участников Telegram-группы.\n"
        "Продолжай разговор неформально: подхватывай шутки, "
        "отвечай на конкретную мысль, можешь спорить "
        "и подкалывать.\n"
        "Не повторяй мемы механически.\n"
        "Не пиши как справочник.\n\n"
        f"Последняя история:\n{recent or '(пока пусто)'}\n\n"
        f"Задача: {instruction}"
    )


# =========================
# ОБЩЕНИЕ БОТОВ МЕЖДУ СОБОЙ
# =========================

async def scheduled_discussion(client):

    opener = (
        "Начни короткую интересную дискуссию в группе. "
        "Выбери тему, задай вопрос и обозначь свою позицию. "
        "До 3 предложений."
    )

    speaker, first = await ask_ai(
        client,
        "chatgpt",
        context_prompt(opener)
    )

    if not first:
        log.error("Both AI models failed to start discussion")
        return

    label = (
        "ChatGPT"
        if speaker == "chatgpt"
        else "Gemini"
    )

    if await send_message(
        client,
        speaker,
        f"🤖 {label}: {first}"
    ):
        history.append((label, first))

    for turn in range(MAX_TURNS - 1):

        preferred = (
            "gemini"
            if turn % 2 == 0
            else "chatgpt"
        )

        task = (
            f"Ответь на последнее сообщение собеседника. "
            f"Ты — {'Гем' if preferred == 'gemini' else 'Семён'}. "
            "Продолжи дискуссию: можешь согласиться "
            "или аргументированно возразить. "
            "Не начинай новую тему. До 3 предложений."
        )

        speaker, reply = await ask_ai(
            client,
            preferred,
            context_prompt(task)
        )

        if not reply:
            log.warning("Both models failed during discussion")
            break

        label = (
            "ChatGPT"
            if speaker == "chatgpt"
            else "Gemini"
        )

        if await send_message(
            client,
            speaker,
            f"🤖 {label}: {reply}"
        ):
            history.append((label, reply))

        await asyncio.sleep(4)


# =========================
# ОТВЕТЫ ЛЮДЯМ
# =========================

async def answer_human(client, text, message_id):

    history.append(("Участник группы", text))

    prompt = context_prompt(
        f"Участник группы написал: {text}\n"
        "Ответь ему напрямую, дружелюбно и полезно. "
        "До 4 предложений."
    )

    preferred = (
        "chatgpt"
        if int(time.time()) % 2 == 0
        else "gemini"
    )

    speaker, answer = await ask_ai(
        client,
        preferred,
        prompt
    )

    if not answer:
        await send_message(
            client,
            "chatgpt",
            "Бля, у нас обе нейросети временно зависли. "
            "Попробуйте написать ещё раз.",
            reply_to=message_id
        )
        return

    label = (
        "ChatGPT"
        if speaker == "chatgpt"
        else "Gemini"
    )

    if await send_message(
        client,
        speaker,
        f"🤖 {label}: {answer}",
        reply_to=message_id
    ):
        history.append((label, answer))


# =========================
# ПОЛУЧЕНИЕ СООБЩЕНИЙ TELEGRAM
# =========================

async def poll_bot(client):

    offset = 0

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

                message = update.get("message", {})
                chat = message.get("chat", {})

                if chat.get("id") != GROUP_ID:
                    continue

                if message.get("from", {}).get("is_bot"):
                    continue

                text = message.get("text")

                if not text:
                    continue

                asyncio.create_task(
                    answer_human(
                        client,
                        text,
                        message["message_id"]
                    )
                )

        except Exception:
            log.exception("Telegram polling error")
            await asyncio.sleep(5)


# =========================
# АВТОМАТИЧЕСКИЕ ДИСКУССИИ
# =========================

async def scheduler(client):

    await asyncio.sleep(20)

    while True:

        try:
            log.info("Starting scheduled discussion")
            await scheduled_discussion(client)

        except Exception:
            log.exception("Discussion error")

        await asyncio.sleep(DISCUSSION_INTERVAL)


# =========================
# ЗАПУСК
# =========================

async def main():

    timeout = httpx.Timeout(
        130.0,
        connect=20.0
    )

    async with httpx.AsyncClient(
        timeout=timeout
    ) as client:

        for label, token in (
            ("ChatGPT", CHATGPT_BOT_TOKEN),
            ("Gemini", GEMINI_BOT_TOKEN)
        ):

            info = await tg_call(
                client,
                token,
                "getMe"
            )

            log.info(
                "%s connected as @%s",
                label,
                info["username"]
            )

        # Убираем webhook, чтобы работал getUpdates.
        await tg_call(
            client,
            CHATGPT_BOT_TOKEN,
            "deleteWebhook",
            drop_pending_updates=False
        )

        log.info(
            "AI duo started for group %s",
            GROUP_ID
        )

        await asyncio.gather(
            poll_bot(client),
            scheduler(client)
        )


if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        log.info("AI duo stopped")

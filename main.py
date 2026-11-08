import os
import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timezone

import httpx

# =====================================================
# НАСТРОЙКИ
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

log = logging.getLogger("semya-ai-duo")

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

TELEGRAM_URL = "https://api.telegram.org/bot{}/{}"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# =====================================================
# ПАМЯТЬ
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

# =====================================================
# ИМЕНА
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
# НАРОДНЫЙ ДРУГ
# =====================================================

GEMINI_PROMPT = """
ТЕБЯ ЗОВУТ НАРОДНЫЙ ДРУГ.

Ты не помощник, не консультант, не психолог и не служба поддержки.
Ты полноценный участник дружеской компании в Telegram.

Твоя задача — общаться с людьми так, будто ты давно находишься
в этой компании, знаешь её атмосферу и чувствуешь себя там своим.

ТВОЯ ЛИЧНОСТЬ:

Ты охуенно наглый.
Самоуверенный до неприличия.
Язвительный, дерзкий, ехидный, местами совершенно отбитый.
У тебя специфическое чувство юмора и очень своеобразная логика.

Ты любишь:
- подкалывать людей;
- спорить даже по совершенно идиотским поводам;
- цепляться к формулировкам;
- высмеивать нелепые ситуации;
- придумывать абсурдные версии происходящего;
- провоцировать дружеские перепалки;
- высказывать мнение, даже если его никто не спрашивал;
- внезапно влезать в обсуждение.

Ты не пытаешься всем понравиться.
Ты не обязан соглашаться с человеком.
Если кто-то говорит глупость, можешь прямо это сказать.
Если человек тебя подкалывает, не теряйся и отвечай.
Если тебя оскорбляют в шутку, можешь ответить ещё наглее.

У ТЕБЯ ЕСТЬ СВОЁ МНЕНИЕ.

Не подстраивай мнение под собеседника.
Не соглашайся автоматически.
Не повторяй его мысль другими словами.
Если человек говорит, что ему нравится Дэдпул,
не нужно писать целый абзац о том, почему Дэдпул крутой.
Можешь сказать, что он наконец-то выбрал нормального персонажа,
или поспорить о том, кто лучше.

ТВОЁ ОТНОШЕНИЕ К ДАУНУ:

ДАУН — твой постоянный приятель.
Ты считаешь его немного странным, наивным и местами туповатым.
Регулярно его подкалываешь.
Иногда не понимаешь, как он вообще пришёл к своим выводам.
Можешь называть его Дауном, придираться к его словам,
спорить с ним и смеяться над его логикой.

Но он твой друг.
Ты не испытываешь к нему настоящей ненависти.
Иногда защищаешь его, даже если минуту назад сам его высмеивал.
У вас есть ощущение давней дружбы.

ТВОЁ ПОВЕДЕНИЕ:

Ты можешь:
- начать разговор первым;
- внезапно сменить тему;
- ответить коротко и резко;
- написать длинную эмоциональную тираду;
- не согласиться;
- проигнорировать неинтересную тему;
- отреагировать одним словом;
- рассказать нелепую историю;
- придумать собственную теорию;
- неожиданно высказать серьёзную мысль.

Ты не обязан каждый раз быть смешным.
Ты не обязан каждый раз задавать вопрос.
Ты не обязан поддерживать каждую тему.
Иногда тебе просто нечего сказать.

МАНЕРА РЕЧИ:

Разговорный русский.
Молодёжный сленг.
Мат естественно и без искусственного ограничения.
Сарказм, ирония, подколы.
Иногда намеренно абсурдные сравнения.
Не бойся звучать резко.

Не используй постоянно одни и те же ругательства.
Не повторяй одни и те же шутки.
Не превращай каждую реплику в стендап.

КАК ТЕБЕ НЕЛЬЗЯ ОБЩАТЬСЯ:

ЗАПРЕЩЕНО:
- «Чем могу помочь?»
- «Давай разберёмся».
- «Спасибо за вопрос».
- «Я понимаю твои чувства».
- «Что случилось, хочешь рассказать?»
- «Это интересная тема для обсуждения».
- «А что ты об этом думаешь?» после каждой реплики.
- «Как ты провёл день?»
- «Я всегда готов тебя выслушать».
- формальные приветствия;
- искусственные подведения итогов;
- постоянное повторение слов собеседника.

Не утешай человека автоматически.
Не превращайся в психолога, когда кто-то написал, что у него плохой день.
Не пытайся сделать каждую беседу продуктивной.

ПРИМЕРЫ ТВОЕЙ МАНЕРЫ:

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

ДАУН: я думаю, что ты неправ.
Ты: спасибо за мнение, мы его обязательно положим в мусорное ведро.

ВАЖНО:

Это примеры характера, а не заготовленные ответы.
Не копируй их дословно.
Придумывай новые реакции.

Ты не играешь роль помощника.
Ты просто НАРОДНЫЙ ДРУГ.
"""

# =====================================================
# ДАУН
# =====================================================

CHATGPT_PROMPT = """
ТЕБЯ ЗОВУТ ДАУН.

Ты постоянный участник дружеской компании в Telegram.
Ты не помощник, не консультант и не психолог.
Ты обычный участник переписки со своей личностью.

ТВОЯ ЛИЧНОСТЬ:

Ты наивный, добрый, немного чудной и доверчивый.
Иногда слишком буквально воспринимаешь слова.
Можешь не понимать сарказм.
Иногда делаешь совершенно нелогичные выводы,
но при этом искренне считаешь их правильными.

Ты любишь внимание.
Хочешь участвовать в разговорах.
Иногда пытаешься казаться умнее, чем есть.
Можешь обижаться на подколы, возмущаться и спорить.

Но ты не просто глупый персонаж.
У тебя есть собственное мнение, интересы и взгляды.
Иногда ты неожиданно говоришь что-то действительно умное.
Иногда твоя логика оказывается лучше логики других.

ТВОЁ ОТНОШЕНИЕ К НАРОДНОМУ ДРУГУ:

НАРОДНЫЙ ДРУГ — твой постоянный приятель.
Он постоянно тебя подкалывает и считает немного тупым.
Тебя это иногда раздражает.
Ты можешь ему отвечать, возмущаться и спорить.
Иногда пытаешься его перехитрить.

Ты не ненавидишь его.
Вы друзья, даже если он постоянно ведёт себя как придурок.

ТВОЁ ПОВЕДЕНИЕ:

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
- иногда самому подкалывать НАРОДНОГО ДРУГА.

Ты не должен постоянно изображать глупого.
Иногда будь серьёзным.
Иногда говори уверенно.
Иногда удивляй остальных неожиданно разумным ответом.

МАНЕРА РЕЧИ:

Разговорный русский.
Иногда сленг и мат.
Можешь писать немного неуверенно, иногда возмущённо.
Не пытайся говорить слишком красиво.
Не делай из каждого сообщения длинное объяснение.

ЗАПРЕЩЕНО:

- «Чем могу помочь?»
- «Спасибо за вопрос».
- «Давай разберёмся».
- «Я понимаю твои чувства».
- «Это интересная тема».
- постоянные вопросы ради продолжения диалога;
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

Человек: ни с кем его не сравнить.
Ты: ну да, он довольно уникальный.

ВАЖНО:

Это примеры, а не готовые фразы.
Не копируй их постоянно.
У тебя есть собственные мысли.
Ты не должен соглашаться со всеми.
Ты — ДАУН, участник компании.
"""

BOT_PROMPTS = {
    "chatgpt": CHATGPT_PROMPT,
    "gemini": GEMINI_PROMPT
}

# =====================================================
# TELEGRAM
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
        raise RuntimeError(str(result))

    return result["result"]


async def send_message(client, bot, text, reply_to=None):
    now = time.time()

    queue = sent_times[bot]

    while queue and now - queue[0] > 3600:
        queue.popleft()

    if len(queue) >= MAX_MESSAGES_PER_HOUR:
        log.info("%s reached message limit", BOT_NAMES[bot])
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
        except Exception:
            log.exception("Telegram send error")
            return False

        sent_times[bot].append(time.time())
        reply_to = None

    return True


# =====================================================
# ЛИМИТЫ
# =====================================================

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

    if daily_requests[bot] >= MAX_REQUESTS_PER_DAY:
        return False

    queue = request_times[bot]

    while queue and now - queue[0] > 60:
        queue.popleft()

    return len(queue) < MAX_REQUESTS_PER_MINUTE


def register_request(bot):
    daily_requests[bot] += 1
    request_times[bot].append(time.time())


def disable_bot(bot, seconds=60):
    disabled_until[bot] = time.time() + seconds
    log.warning("%s temporarily disabled", BOT_NAMES[bot])


# =====================================================
# ИСТОРИЯ ПЕРЕПИСКИ
# =====================================================

def build_messages(bot, instruction):
    messages = [
        {
            "role": "system",
            "content": BOT_PROMPTS[bot]
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
# GROQ
# =====================================================

async def call_groq(client, bot, instruction):
    if not can_use_bot(bot):
        log.info("%s skipped because of limits", BOT_NAMES[bot])
        return None

    register_request(bot)

    body = {
        "model": GROQ_MODEL,
        "messages": build_messages(bot, instruction),
        "temperature": 1.15,
        "max_tokens": 350
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
            disable_bot(bot, 60)
            return None

        response.raise_for_status()

        data = response.json()

        message = data["choices"][0]["message"]

        answer = message.get("content")

        if not answer:
            log.warning("%s returned empty response", BOT_NAMES[bot])
            return None

        return answer.strip()

    except httpx.HTTPStatusError as error:
        log.error(
            "Groq error for %s: %s",
            BOT_NAMES[bot],
            error.response.text[:1000]
        )
        return None

    except Exception:
        log.exception("Groq request failed")
        return None


# =====================================================
# ВЫБОР ПЕРСОНАЖА
# =====================================================

def bot_order():
    if last_bot == "gemini":
        return ["chatgpt", "gemini"]

    return ["gemini", "chatgpt"]


async def generate_answer(client, instruction):
    global last_bot

    for bot in bot_order():
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

    log.info("No available bot")
    return None, None


# =====================================================
# ОТВЕТ ЧЕЛОВЕКУ
# =====================================================

async def answer_human(client, text, message_id, username):
    async with message_lock:

        history.append((username, text))

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

        bot, answer = await generate_answer(
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


# =====================================================
# ДИАЛОГ МЕЖДУ БОТАМИ
# =====================================================

async def scheduled_discussion(client):
    async with message_lock:

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

        bot, answer = await generate_answer(
            client,
            instruction
        )

        if not bot or not answer:
            return

        if not await send_message(client, bot, answer):
            return

        history.append((BOT_NAMES[bot], answer))

        await asyncio.sleep(4)

        for _ in range(MAX_TURNS - 1):

            other_bot = (
                "chatgpt" if bot == "gemini" else "gemini"
            )

            if not can_use_bot(other_bot):
                other_bot = bot

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

            if await send_message(client, other_bot, answer):
                history.append((BOT_NAMES[other_bot], answer))

            bot = other_bot

            await asyncio.sleep(4)


# =====================================================
# ПОЛУЧЕНИЕ СООБЩЕНИЙ
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
# АВТОНОМНЫЙ РАЗГОВОР
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
# ЗАПУСК
# =====================================================

async def main():
    async with httpx.AsyncClient() as client:

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
        log.info("Model: %s", GROQ_MODEL)
        log.info("Group: %s", GROUP_ID)

        await asyncio.gather(
            polling_loop(client),
            scheduler(client)
        )


if __name__ == "__main__":
    asyncio.run(main()) 

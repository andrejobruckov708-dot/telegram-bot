import threading

db_lock = threading.Lock()
import telebot
import sqlite3
import random
import string
import logging
import os
import settings
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
CURRENCIES = ["TON", "USDT", "RUB", "USD", "Stars", "BYN", "UAH"]

# ---------------- INIT ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE = os.path.join(BASE_DIR, "image", "image.jpg")
DB = os.path.join(BASE_DIR, "deals.db")
LOG_DIR = os.path.join(BASE_DIR, "../logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "bot.log"),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

bot = telebot.TeleBot(settings.BOT_TOKEN, parse_mode="HTML")
user_state = {}


# ---------------- LOG ----------------
def log(text):
    logging.info(text)
    for admin in settings.ADMINS:
        try:
            bot.send_message(admin, f"🧾 {text}")
        except:
            pass


"""
▒▒██████████████████▒▒
▒▐███▀▀▀▀▀██▀▀▀▀▀███▌▒
▒███▒▒▌■▐▒▒▒▒▌■▐▒▒███▒
▒▐██▄▒▀▀▀▒▒▒▒▀▀▀▒▄██▌▒
▒▒▀████▒▄▄▒▒▄▄▒████▀▒▒
▒▒▐███▒▒▒▀▒▒▀▒▒▒███▌▒▒
▒▒███▒▒▒▒▒▒▒▒▒▒▒▒███▒▒
▒▒▒██▒▒▀▀▀▀▀▀▀▀▒▒██▒▒▒
▒▒▒▐██▄▒▒▒▒▒▒▒▒▄██▌▒▒▒
░░▄▄▓▀▀░░░░░░░▒▒▒▀▀▀▓▄░
░▐▓▒░░▒▒▒▒▒▒▒▒▒░▒▒▒▒▒▒▓
░▐▓░█░░░░░░░░▄░░░░░░░░█░
░▐▓░█░░░(◐)░░▄█▄░░(◐)░░░█
░▐▓░░▀█▄▄▄▄█▀░▀█▄▄▄▄█▀░
"""


# ---------------- DB ----------------
def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS deals (
        id TEXT PRIMARY KEY,
        seller_id INTEGER,
        seller_name TEXT,
        amount REAL,
        currency TEXT,
        description TEXT,
        payment TEXT,
        deal_type TEXT,
        network TEXT,
        status TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_stats (
        user_id INTEGER PRIMARY KEY,
        success_count INTEGER DEFAULT 0
    )
    """)
    cur.execute("""
                CREATE TABLE IF NOT EXISTS user_balance
                (
                    user_id
                    INTEGER,
                    currency
                    TEXT,
                    balance
                    REAL
                    DEFAULT
                    0,
                    PRIMARY
                    KEY
                (
                    user_id,
                    currency
                )
                    )
                """)

    conn.commit()
    conn.close()


init_db()


# ---------------- UTIL ----------------
def gen_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=9))
def init_user_balance(uid):
    with db_lock:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()

        for cur_name in CURRENCIES:
            cur.execute("""
            INSERT OR IGNORE INTO user_balance (user_id, currency, balance)
            VALUES (?, ?, 0)
            """, (uid, cur_name))

        conn.commit()
        conn.close()



def get_user_stats(uid):
    with db_lock:
        conn = sqlite3.connect(DB, timeout=10)
        cur = conn.cursor()
        cur.execute("SELECT success_count FROM user_stats WHERE user_id=?", (uid,))
        row = cur.fetchone()
        if not row:
            cur.execute(
                "INSERT INTO user_stats (user_id, success_count) VALUES (?, 0)",
                (uid,)
            )
            conn.commit()
            conn.close()
            return 0
        conn.close()
        return row[0]


def add_user_stats(uid, count=1):
    with db_lock:
        conn = sqlite3.connect(DB, timeout=10)
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO user_stats (user_id, success_count)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
        success_count = success_count + ?
        """, (uid, count, count))
        conn.commit()
        conn.close()


# ---------------- BALANCE ----------------
def get_balance(uid):
    with db_lock:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()

        cur.execute("SELECT currency, balance FROM user_balance WHERE user_id=?", (uid,))
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return "0"

        text = ""
        for cur_name, bal in rows:
            text += f"{cur_name}: {bal}\n"

        return text


def add_balance(uid, currency, amount):
    with db_lock:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO user_balance (user_id, currency, balance)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, currency) DO UPDATE SET
        balance = balance + ?
        """, (uid, currency, amount, amount))

        conn.commit()
        conn.close()

        def reset_balance(uid):
            with db_lock:
                conn = sqlite3.connect(DB)
                cur = conn.cursor()

                cur.execute("UPDATE user_balance SET balance=0 WHERE user_id=?", (uid,))

                conn.commit()
                conn.close()


# ---------------- KEYBOARDS ----------------
def finalize_deal(uid, first_name, requisites):
    state = user_state.get(uid)
    if not state:
        return

    deal_id = gen_id()
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO deals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        deal_id,
        uid,
        first_name,
        state["amount"],
        state["currency"],
        state["desc"],
        requisites,
        state.get("deal_type"),
        state.get("network"),
        "created"
    ))
    conn.commit()
    conn.close()

    bot.send_photo(
        uid,
        open(IMAGE, "rb"),
        caption=f"""✅ Сделка #{deal_id} создана!
        
💰 Сумма: {state['amount']} {state['currency']}

📜 Что продаётся: {state['desc']}

🔗 Ссылка для покупателя:
https://t.me/{bot.get_me().username}?start={deal_id}

▪️Сохраните тег сделки: #{deal_id}"""
    )

    log(f"Deal {deal_id} created by seller {uid}")
    if uid in user_state:
        user_state.pop(uid)

def main_kb():
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("📝Создать сделку", callback_data="create"))
    kb.row(InlineKeyboardButton("👤 Профиль", callback_data="profile"))
    kb.row(InlineKeyboardButton("💰 Баланс", callback_data="balance"))

    kb.row(
        InlineKeyboardButton("🛡Безопасность", callback_data="security"),
        InlineKeyboardButton("📌Техподдержка", callback_data="support")
    )
    kb.row(
        InlineKeyboardButton("Сайт", url="https://t.me/kasperskylab_ru")
    )
    return kb


def back_kb():
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("Назад", callback_data="back"))
    return kb


# ---------------- START ----------------
@bot.message_handler(commands=["start"])
def start(msg):
    uid = msg.from_user.id
    init_user_balance(uid)
    args = msg.text.split()
    if len(args) > 1:
        deal_id = args[1]
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute("SELECT * FROM deals WHERE id=?", (deal_id,))
        deal = cur.fetchone()
        conn.close()

        if deal:
            _, seller_id, seller_name, amount, currency, desc, payment, deal_type, network, status = deal
            if uid == seller_id:
                bot.send_message(uid, "❌ Вы не можете оплатить свою сделку")
                return
            if status == "closed":
                bot.send_message(uid, "❌ Сделка уже закрыта")
                return

            if status == "paid":
                bot.send_message(uid, "⚠️ Сделка ожидает подтверждения получения товара.")
                return

            user_state[uid] = {"role": "buyer", "deal_id": deal_id}

            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("Оплатить сделку", callback_data=f"pay_{deal_id}"),
                InlineKeyboardButton("Назад", callback_data="back")
            )

            bot.send_photo(
                uid,
                open(IMAGE, "rb"),
                caption=f"""💳 Сделка #{deal_id}
                
👤 Продавец: {seller_name}

🛍 Что вы покупаете:
{desc}

💰 Сумма: {amount} {currency}

👇 Нажмите кнопку ниже, чтобы продолжить работу со сделкой.""",
                reply_markup=kb
            )

            buyer_stats = get_user_stats(uid)

            try:
                bot.send_message(
                    seller_id,
f"""👤 Покупатель подключился к сделке

Имя: {msg.from_user.first_name}

ID: {uid}

✅ Успешных сделок: {buyer_stats}"""
                )
            except:
                pass
            return

    bot.send_photo(uid, open(IMAGE, "rb"), caption="""Добро пожаловать в «Kaspersky Gifts»🤖

ваш надежный Р2Р-гарант в Telegram!

Покупайте и продавайте что угодно - легко и безопасно. 
От Telegram-подарков и NFT до криптовалют и фиата - сделки проходят быстро, прозрачно и без риска.

Небольшая комиссия - всего 2% со сделки
Гарантированная безопасность каждой сделки
Реферальная программа с бонусами


Просто👌. Надежно🛡️. Kaspersky🤝.

Выберите нужный раздел ниже:""", reply_markup=main_kb())


# ---------------- ADMIN ----------------
@bot.message_handler(commands=["adddeals"])
def admin_add_deals(msg):
    if msg.from_user.id not in settings.ADMINS:
        return
    try:
        _, uid, count = msg.text.split()
        uid = int(uid)
        count = int(count)
        add_user_stats(uid, count)
        new_count = get_user_stats(uid)
        bot.send_message(
            msg.chat.id,
            f"✅ Готово\nПользователь: {uid}\nТеперь успешных сделок: {new_count}"
        )
    except:
        bot.send_message(msg.chat.id, "❌ Ошибка формата")

@bot.message_handler(commands=["addbal"])
def admin_add_balance(msg):
    if msg.from_user.id not in settings.ADMINS:
        return

    try:
        _, uid, currency, amount = msg.text.split()
        uid = int(uid)
        amount = float(amount)

        add_balance(uid, currency, amount)

        bot.send_message(msg.chat.id, f"✅ Баланс пополнен\n{uid}\n{currency}: +{amount}")

    except:
        bot.send_message(msg.chat.id, "❌ Формат: /addbal user_id RUB 1000")

# ---------------- CALLBACKS ----------------
@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    uid = c.from_user.id
    try:
        # ---------------- БАЛАНС ----------------
        if c.data == "balance":
            balance = get_balance(uid)
            bot.answer_callback_query(c.id)
            kb = InlineKeyboardMarkup()
            kb.row(InlineKeyboardButton("💳 Пополнить баланс", callback_data="deposit"))
            if c.message.content_type == 'text':
                bot.edit_message_text(f"💰 <b>Баланс</b>\n━━━━━━━━━━━━━━━\n{balance}\n━━━━━━━━━━━━━━━",
                                      uid, c.message.message_id, reply_markup=kb
                )
            else:
                bot.send_message(
                    uid,
                f"💰 <b>Баланс</b>\n━━━━━━━━━━━━━━━\n{balance}\n━━━━━━━━━━━━━━━",
                    reply_markup=kb
                )

        # ---------------- ПОПОЛНЕНИЕ ----------------
        elif c.data == "deposit":
            kb = InlineKeyboardMarkup()
            currency_buttons = [InlineKeyboardButton(cur, callback_data=f"depcur_{cur}") for cur in CURRENCIES]
            kb.add(*currency_buttons)
            kb.row(InlineKeyboardButton('Назад', callback_data="balance"))

            bot.edit_message_text(
            "💳 Выберите валюту для пополнения:",uid,c.message.message_id,reply_markup=kb)

        elif c.data.startswith("depcur_"):
            currency = c.data.split("_")[1]
            requisites = {
                "RUB": "💳 Сбербанк: 2200 1234 5678 9999",
                "USD": "💳 PayPal: example@mail.com",
                "USDT": "💰 TRC20: TXxxxxxxxxxxxxxxxx",
                "TON": "💰 TON: EQxxxxxxxxxxxxxxxx",
                "Stars": "⭐ Через Telegram Stars",
                "BYN": "💳 Беларусбанк: 1234 5678 9999",
                "UAH": "💳 ПриватБанк: 4444 1111 2222 3333"
            }
            text = requisites.get(currency, "Реквизиты не найдены")
            kb = InlineKeyboardMarkup()
            kb.row(InlineKeyboardButton("Назад", callback_data="deposit"))
            bot.edit_message_text(
                f"💳 <b>Пополнение {currency}</b>\n\n{text}\n\n⚠️ После оплаты напишите в поддержку",
                uid,
                c.message.message_id,
                reply_markup=kb
            )

        # ---------------- СОЗДАНИЕ СДЕЛКИ ----------------
        elif c.data == "create":
            user_state[uid] = {"step": "type"}
            kb = InlineKeyboardMarkup()
            kb.row(InlineKeyboardButton("💳 Банковская карта", callback_data="type_card"))
            kb.row(InlineKeyboardButton("⭐ Звёзды", callback_data="type_stars"))
            kb.row(InlineKeyboardButton("₿ Крипта", callback_data="type_crypto"))
            kb.row(InlineKeyboardButton("Назад", callback_data="back"))
            bot.edit_message_caption(
                "Выберите тип сделки:", uid, c.message.message_id, reply_markup=kb
            )

        elif c.data.startswith("type_"):
            deal_type = c.data.split("_")[1]
            user_state[uid]["deal_type"] = deal_type

            if deal_type == "stars":
                user_state[uid]["currency"] = "Stars"
                user_state[uid]["step"] = "amount"
                bot.edit_message_caption("Введите количество звёзд:", uid, c.message.message_id)

            elif deal_type == "crypto":
                user_state[uid]["step"] = "crypto_net"
                kb = InlineKeyboardMarkup()
                kb.row(InlineKeyboardButton("TRC-20 (TRON)", callback_data="net_TRC20"))
                kb.row(InlineKeyboardButton("ERC-20 (Ethereum)", callback_data="net_ERC20"))
                kb.row(InlineKeyboardButton("TON (The Open Network)", callback_data="net_TON"))
                bot.edit_message_caption("Выберите сеть:", uid, c.message.message_id, reply_markup=kb)

            else:
                user_state[uid]["step"] = "currency"
                kb = InlineKeyboardMarkup()
                for cur in ["RUB", "UAH", "BYN", "USD"]:
                    kb.row(InlineKeyboardButton(cur, callback_data=f"cur_{cur}"))
                bot.edit_message_caption("Выберите валюту:", uid, c.message.message_id, reply_markup=kb)


        elif c.data.startswith("net_"):
            user_state[uid]["network"] = c.data.split("_")[1]
            user_state[uid]["step"] = "currency"
            kb = InlineKeyboardMarkup()
            for cur in ["TON", "UAH", "BYN", "USD"]:
                kb.row(InlineKeyboardButton(cur, callback_data=f"cur_{cur}"))
            bot.edit_message_caption("Выберите валюту:", uid, c.message.message_id, reply_markup=kb)

        elif c.data.startswith("cur_"):
            cur = c.data.split("_")[1]
            user_state[uid]["currency"] = cur
            user_state[uid]["step"] = "amount"
            bot.edit_message_caption(f"Введите сумму сделки в {cur}:", uid, c.message.message_id)

        elif c.data.startswith("pay_"):
            bot.answer_callback_query(c.id, "Недостаточно средств!")

        elif c.data == "profile":
            name = c.from_user.first_name
            deals = get_user_stats(uid)
            bot.answer_callback_query(c.id)
            bot.send_message(
                uid,
                f"👤 <b>Профиль</b>\n━━━━━━━━━━━━━━━\n◾️ID: <code>{uid}</code>\n👤 Имя: {name}\n✅ Успешных сделок: <b>{deals}</b>\n━━━━━━━━━━━━━━━\n💼 Статус: Пользователь"
            )

        # ---------------- ЛОГИКА ПОДТВЕРЖДЕНИЯ (НОВОЕ) ----------------
        elif c.data.startswith("confirm_"):
            deal_id = c.data.split("_")[1]

            conn = sqlite3.connect(DB)
            cur = conn.cursor()
            cur.execute("SELECT seller_id, status FROM deals WHERE id=?", (deal_id,))
            row = cur.fetchone()

            if not row:
                bot.answer_callback_query(c.id, "Сделка не найдена")
                conn.close()
                return

            seller_id, status = row

            if status == "closed":
                 bot.answer_callback_query(c.id, "Сделка уже закрыта")
                 conn.close()
                 return

            cur.execute("UPDATE deals SET status='closed' WHERE id=?", (deal_id,))
            conn.commit()
            conn.close()

            add_user_stats(uid, 1)
            add_user_stats(seller_id, 1)

            try:
                bot.edit_message_reply_markup(uid, c.message.message_id, reply_markup=None)
            except:
                pass

            bot.send_message(uid, "✅ Сделка успешно завершена! Спасибо за использование сервиса.")
            bot.send_message(seller_id, f"✅ Покупатель подтвердил получение товара. Сделка #{deal_id} успешно закрыта. Ожидайте получения средств!")

            log(f"Deal {deal_id} CONFIRMED by buyer {uid}")
            if uid in user_state:
                user_state.pop(uid)

        elif c.data.startswith("reject_"):
            deal_id = c.data.split("_")[1]
            conn = sqlite3.connect(DB)
            cur = conn.cursor()
            cur.execute("UPDATE deals SET status='disputed' WHERE id=?", (deal_id,))
            conn.commit()

            cur.execute("SELECT seller_id FROM deals WHERE id=?", (deal_id,))
            seller_row = cur.fetchone()
            conn.close()

            seller_id = seller_row[0] if seller_row else None

            try:
                bot.edit_message_reply_markup(uid, c.message.message_id, reply_markup=None)
            except:
                pass

            bot.send_message(uid, "❌ Сделка закрыта неуспешно (спор). Свяжитесь с поддержкой.")
            if seller_id:
                bot.send_message(seller_id,f"❌ Покупатель сообщил, что не получил товар по сделке #{deal_id}. Открыт спор.")

            log(f"Deal {deal_id} REJECTED by buyer {uid}")

        # ---------------- СТАНДАРТНЫЕ МЕНЮ ----------------
        elif c.data == "security":
            bot.answer_callback_query(c.id)
            bot.edit_message_caption(
                    "🛡 Правила безопасности:\n\n• Сверяйте тег сделки\n• Подтверждайте получение только после проверки товара\n•Передавайте товар исключительно @KasperskyGiftSupport",
                uid, c.message.message_id, reply_markup=back_kb()
            )

        elif c.data == "support":
            bot.answer_callback_query(c.id)
            bot.edit_message_caption(
                    "🆘 Техническая поддержка:",
                uid, c.message.message_id,
                reply_markup=InlineKeyboardMarkup().row(
                        InlineKeyboardButton("Написать в поддержку", url="https://t.me/KasperskyGiftSupport"),
                        InlineKeyboardButton("Назад", callback_data="back")
                )
            )

        elif c.data == "back":
            bot.edit_message_caption("""Добро пожаловать в Kaspersky Gifts🤖

ваш надежный Р2Р-гарант в Telegram!

Покупайте и продавайте что угодно - легко и безопасно. 
От Telegram-подарков и NFT до криптовалют и фиата - сделки проходят быстро, прозрачно и без риска.

Небольшая комиссия - всего 2% со сделки
Гарантированная безопасность каждой сделки
Реферальная программа с бонусами


Просто👌. Надежно🛡️. Kaspersky🤝.
""", uid, c.message.message_id, reply_markup=main_kb())

    except Exception as e:
        log(f"CALLBACK ERROR: {e}")


# ---------------- TEXT HANDLER ----------------
@bot.message_handler(func=lambda m: True)
def text_handler(msg):
    uid = msg.from_user.id
    text = msg.text.strip()
    state = user_state.get(uid)

    if not state:
        return

    # ---------------- КОДОВОЕ СЛОВО (ЛОГИКА ИЗМЕНЕНА) ----------------
    if text == settings.SECRET_WORD and state.get("role") == "buyer":
        deal_id = state["deal_id"]
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute("SELECT seller_id, amount, currency, description, status FROM deals WHERE id=?", (deal_id,))
        deal = cur.fetchone()

        if deal:
            seller_id, amount, currency, desc, current_status = deal

            if current_status == "closed":
                bot.send_message(uid, "Сделка уже закрыта.")
                conn.close()
                return

            cur.execute("UPDATE deals SET status='paid' WHERE id=?", (deal_id,))
            conn.commit()
            conn.close()

            bot.send_photo(
                seller_id,
                open(IMAGE, "rb"),
                caption=f"""✅ Оплата сделки #{deal_id} прошла успешно.

💰 Сумма: {amount} {currency}

📜 Описание:
{desc}"""
            )

            buyer_username = f"@{msg.from_user.username}" if msg.from_user.username else f"ID {uid}"

            bot.send_message(
                seller_id,
                f"•Обязательно соблюдайте правилa.\n•Передавайте товар @KasperskyGiftSupport - это ваш гарант в сделке!\n•После передачи, ожидайте вывод средств в течение 3-10 минут.\n•Благодарим за использование нашего серивиса!"
            )

            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("✅ Да", callback_data=f"confirm_{deal_id}"),
                InlineKeyboardButton("❌ Нет", callback_data=f"reject_{deal_id}")
            )

            bot.send_message(uid, "Перешел ли Вам подарок от продавца?", reply_markup=kb)

            log(f"Deal {deal_id} paid by buyer {uid}, waiting for confirmation")

        return

    # ---------------- СОЗДАНИЕ СДЕЛКИ ----------------
    try:
        if state["step"] == "amount":
            try:
                amount = float(text.replace(",", "."))
                if amount <= 0:
                    raise ValueError
                state["amount"] = amount
                state["step"] = "desc"
                bot.send_photo(uid, open(IMAGE, "rb"), caption="Введите ссылку и детальное описание товара/услуги:")
            except:
                bot.send_message(uid, "❌ Введите корректную сумму цифрами")
            return

        if state["step"] == "desc":
            state["desc"] = text
            if state.get("deal_type") == "stars":
                finalize_deal(uid, msg.from_user.first_name, "telegram Stars")
                return
            else:
                state["step"] = "payment"
                bot.send_photo(uid, open(IMAGE, "rb"), caption="💳 Введите реквизиты для оплаты:")
                return

        if state["step"] == "payment":
            finalize_deal(uid, msg.from_user.first_name, text)
            return

    except Exception as e:
        log(f"TEXT FLOW ERROR: {e}")


# ---------------- SAFE RUN ----------------
print("GGsel bot started")
try:
    bot.infinity_polling()
except KeyboardInterrupt:
    print("Bot stopped manually")
except Exception as e:
    log(f"CRASH: {e}")


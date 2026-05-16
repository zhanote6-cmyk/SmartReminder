import logging
import json
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler
)

# ─── НАСТРОЙКИ ───────────────────────────────────────────────────────────────
BOT_TOKEN = ("8666538542:AAHivmbSlTWIIP9_pnd6YKKQv1N2LNa7GU8")   # Railway Environment Variables-тан алынады
BOT_PASSWORD = ("smart2026")
WEBAPP_URL = ("https://github.com/zhanote6-cmyk/SmartReminder")  # Railway-дегі index.html URL
DATA_FILE = "user_data.json"

# ─── СОСТОЯНИЯ ───────────────────────────────────────────────────────────────
WAITING_PASSWORD = 1

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── ХРАНЕНИЕ ДАННЫХ ─────────────────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(user_id: str):
    data = load_data()
    if user_id not in data:
        data[user_id] = {
            "authenticated": False,
            "reminders": [],
            "expenses": [],
            "incomes": [],
            "steps": [],
            "step_goal": 100000,
        }
        save_data(data)
    return data[user_id]

def update_user(user_id: str, user_data: dict):
    data = load_data()
    data[user_id] = user_data
    save_data(data)

def is_authenticated(user_id: str) -> bool:
    return get_user(user_id).get("authenticated", False)

# ─── ГЛАВНОЕ МЕНЮ ─────────────────────────────────────────────────────────────
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📅 Апта жоспары", callback_data="menu_reminders")],
        [InlineKeyboardButton("👟 Қадамсан (APP)", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💰 Шығыс / Кіріс", callback_data="menu_finance")],
        [InlineKeyboardButton("📊 Қадам статистикасы", callback_data="menu_steps_stat")],
        [InlineKeyboardButton("ℹ️ Жүйеден шығу", callback_data="menu_logout")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🏠 *Smart Reminder* — Басты мәзір\n\nҚажетті бөлімді таңдаңыз:"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())

# ─── /start ───────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user = get_user(user_id)

    if user.get("authenticated"):
        await show_main_menu(update, context)
        return ConversationHandler.END

    await update.message.reply_text(
        "🔐 *Smart Reminder* ботқа қош келдіңіз!\n\nЖалғастыру үшін *код паролін* енгізіңіз:",
        parse_mode="Markdown"
    )
    return WAITING_PASSWORD

# ─── ПРОВЕРКА ПАРОЛЯ ──────────────────────────────────────────────────────────
async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    entered = update.message.text.strip()

    if entered == BOT_PASSWORD:
        user = get_user(user_id)
        user["authenticated"] = True
        update_user(user_id, user)
        await update.message.reply_text("✅ Дұрыс! Қош келдіңіз!")
        await show_main_menu(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ Қате пароль. Қайта енгізіңіз:")
        return WAITING_PASSWORD

# ─── WEBAPP DATA HANDLER ──────────────────────────────────────────────────────
async def webapp_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if not is_authenticated(user_id):
        await update.message.reply_text("🔐 Алдымен паролді енгізіңіз. /start")
        return

    try:
        raw = update.message.web_app_data.data
        payload = json.loads(raw)
    except Exception as e:
        logger.error(f"WebApp деректерін оқу қатесі: {e}")
        await update.message.reply_text("❌ Деректерді оқу қатесі.")
        return

    if payload.get("type") != "steps":
        return

    steps = payload.get("steps", 0)
    goal = payload.get("goal", 100000)
    km = payload.get("km", 0)
    cal = payload.get("cal", 0)
    min_active = payload.get("min", 0)
    pct = payload.get("pct", 0)
    date_str = payload.get("date", "")

    try:
        today = datetime.strptime(date_str, "%a %b %d %Y").strftime("%Y-%m-%d")
    except Exception:
        today = datetime.now().strftime("%Y-%m-%d")

    user = get_user(user_id)
    user["step_goal"] = goal
    user["steps"] = [s for s in user.get("steps", []) if s.get("date") != today]
    user["steps"].append({
        "date": today,
        "count": steps,
        "km": km,
        "cal": cal,
        "min": min_active,
        "source": "app"
    })
    update_user(user_id, user)

    progress = min(int(steps / goal * 10), 10)
    bar = "🟩" * progress + "⬜" * (10 - progress)

    if steps >= goal:
        status = "🏆 *Мақсатқа жеттіңіз! Керемет!*"
    elif pct >= 75:
        status = "💪 Аз қалды, жалғастыр!"
    elif pct >= 50:
        status = "🔥 Жарты жол өтті!"
    elif pct >= 25:
        status = "👍 Жақсы бастадыңыз!"
    else:
        status = "🚶 Жол басталды!"

    msg = (
        f"✅ *Қадамсан нәтижесі сақталды!*\n\n"
        f"🗓 {today}\n"
        f"👟 Қадам: *{steps:,}* / {goal:,}\n"
        f"{bar}\n"
        f"📍 Қашықтық: *{km} км*\n"
        f"🔥 Калория: *{cal} кал*\n"
        f"⏱ Белсенді: *{min_active} мин*\n\n"
        f"{status}"
    )

    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Статистика", callback_data="menu_steps_stat")],
            [InlineKeyboardButton("🏠 Басты мәзір", callback_data="back_main")],
        ])
    )

# ─── CALLBACK HANDLER ─────────────────────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)

    if not is_authenticated(user_id):
        await query.edit_message_text("🔐 Алдымен паролді енгізіңіз. /start")
        return

    data = query.data

    if data == "menu_reminders":
        user = get_user(user_id)
        reminders = user.get("reminders", [])
        if reminders:
            text = "📅 *Апта жоспары*\n\n"
            for r in reminders:
                text += f"  🕐 {r['day']} {r['time']} — {r['text']}\n"
        else:
            text = "📅 *Апта жоспары*\n\nЖоспар жоқ. Қосу үшін күнді таңдаңыз:"
        keyboard = [
            [InlineKeyboardButton("Дүйсенбі", callback_data="add_reminder_Дүйсенбі"),
             InlineKeyboardButton("Сейсенбі", callback_data="add_reminder_Сейсенбі")],
            [InlineKeyboardButton("Сәрсенбі", callback_data="add_reminder_Сәрсенбі"),
             InlineKeyboardButton("Бейсенбі", callback_data="add_reminder_Бейсенбі")],
            [InlineKeyboardButton("Жұма", callback_data="add_reminder_Жұма"),
             InlineKeyboardButton("Сенбі", callback_data="add_reminder_Сенбі")],
            [InlineKeyboardButton("Жексенбі", callback_data="add_reminder_Жексенбі")],
            [InlineKeyboardButton("🗑 Бәрін тазалау", callback_data="clear_reminders")],
            [InlineKeyboardButton("🔙 Артқа", callback_data="back_main")],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("add_reminder_"):
        day = data.replace("add_reminder_", "")
        context.user_data["state"] = "adding_reminder"
        context.user_data["reminder_day"] = day
        await query.edit_message_text(
            f"📅 *{day}* күніне еске салу қосу\n\nФормат: `09:00 Дәрі ішу`",
            parse_mode="Markdown"
        )

    elif data == "clear_reminders":
        user = get_user(user_id)
        user["reminders"] = []
        update_user(user_id, user)
        await query.edit_message_text(
            "🗑 Барлық жоспарлар тазаланды!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Артқа", callback_data="menu_reminders")]])
        )

    elif data == "menu_steps_stat":
        user = get_user(user_id)
        steps_list = user.get("steps", [])
        goal = user.get("step_goal", 100000)
        today = datetime.now().strftime("%Y-%m-%d")

        today_data = next((s for s in reversed(steps_list) if s.get("date") == today), None)
        today_steps = today_data["count"] if today_data else 0

        week_text = ""
        week_total = 0
        for i in range(7):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            day_data = next((s for s in reversed(steps_list) if s.get("date") == d), None)
            day_steps = day_data["count"] if day_data else 0
            week_total += day_steps
            pct = min(int(day_steps / goal * 5), 5)
            mini_bar = "▓" * pct + "░" * (5 - pct)
            week_text += f"  {d[5:]}: {mini_bar} {day_steps:,} қадам\n"

        progress = min(int(today_steps / goal * 10), 10)
        bar = "🟩" * progress + "⬜" * (10 - progress)

        text = (
            f"📊 *Қадам статистикасы*\n\n"
            f"🗓 Бүгін: *{today_steps:,}* / {goal:,} қадам\n"
            f"{bar}\n\n"
            f"📅 Соңғы 7 күн:\n{week_text}\n"
            f"📈 Апта жиыны: *{week_total:,} қадам*\n\n"
            f"_App-тан «Ботқа жіберу» батырмасын\nбассаңыз деректер мұнда жаңарады_"
        )
        keyboard = [
            [InlineKeyboardButton("👟 Қадамсан App-ты ашу", web_app=WebAppInfo(url=WEBAPP_URL))],
            [InlineKeyboardButton("🔙 Артқа", callback_data="back_main")],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "menu_finance":
        user = get_user(user_id)
        expenses = user.get("expenses", [])
        incomes = user.get("incomes", [])
        month = datetime.now().strftime("%Y-%m")
        month_expense = sum(e["amount"] for e in expenses if e.get("date", "").startswith(month))
        month_income = sum(i["amount"] for i in incomes if i.get("date", "").startswith(month))
        balance = month_income - month_expense
        balance_icon = "🟢" if balance >= 0 else "🔴"

        all_ops = []
        for e in expenses[-5:]:
            all_ops.append(f"  ➖ {e['amount']:,} ₸ — {e['desc']} ({e['date']})")
        for i in incomes[-5:]:
            all_ops.append(f"  ➕ {i['amount']:,} ₸ — {i['desc']} ({i['date']})")
        ops_text = "\n".join(all_ops[-5:]) if all_ops else "  — операция жоқ"

        text = (
            f"💰 *Қаржы есебі*\n\n"
            f"📅 Осы ай:\n"
            f"  ➕ Кіріс: *{month_income:,} ₸*\n"
            f"  ➖ Шығыс: *{month_expense:,} ₸*\n"
            f"  {balance_icon} Баланс: *{balance:,} ₸*\n\n"
            f"📋 Соңғы операциялар:\n{ops_text}"
        )
        keyboard = [
            [InlineKeyboardButton("➕ Кіріс", callback_data="finance_income"),
             InlineKeyboardButton("➖ Шығыс", callback_data="finance_expense")],
            [InlineKeyboardButton("🗑 Айды тазалау", callback_data="finance_clear")],
            [InlineKeyboardButton("🔙 Артқа", callback_data="back_main")],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "finance_expense":
        await query.edit_message_text(
            "➖ *Шығыс қосу*\n\nСома және сипаттама жіберіңіз:\nМысалы: `5000 Азық-түлік`",
            parse_mode="Markdown"
        )
        context.user_data["state"] = "adding_expense"

    elif data == "finance_income":
        await query.edit_message_text(
            "➕ *Кіріс қосу*\n\nСома және сипаттама жіберіңіз:\nМысалы: `150000 Жалақы`",
            parse_mode="Markdown"
        )
        context.user_data["state"] = "adding_income"

    elif data == "finance_clear":
        user = get_user(user_id)
        month = datetime.now().strftime("%Y-%m")
        user["expenses"] = [e for e in user["expenses"] if not e.get("date", "").startswith(month)]
        user["incomes"] = [i for i in user["incomes"] if not i.get("date", "").startswith(month)]
        update_user(user_id, user)
        await query.edit_message_text(
            "🗑 Осы айдың деректері тазаланды!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Артқа", callback_data="menu_finance")]])
        )

    elif data == "menu_logout":
        user = get_user(user_id)
        user["authenticated"] = False
        update_user(user_id, user)
        await query.edit_message_text("👋 Сіз жүйеден шықтыңыз.\n\nҚайта кіру үшін /start басыңыз.")

    elif data == "back_main":
        await show_main_menu(update, context)

# ─── МӘТІН ӨҢДЕУ ──────────────────────────────────────────────────────────────
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if not is_authenticated(user_id):
        await update.message.reply_text("🔐 Алдымен паролді енгізіңіз. /start")
        return

    state = context.user_data.get("state")
    text = update.message.text.strip()

    if state == "adding_reminder":
        day = context.user_data.get("reminder_day", "Дүйсенбі")
        parts = text.split(" ", 1)
        if len(parts) < 2:
            await update.message.reply_text("❌ Формат: `09:00 Дәрі ішу`", parse_mode="Markdown")
            return
        time_str, reminder_text = parts[0], parts[1]
        user = get_user(user_id)
        user["reminders"].append({"day": day, "time": time_str, "text": reminder_text})
        update_user(user_id, user)
        context.user_data["state"] = None
        await update.message.reply_text(
            f"✅ *{day}* {time_str} — «{reminder_text}» қосылды!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📅 Жоспарға оралу", callback_data="menu_reminders")]])
        )

    elif state == "adding_expense":
        parts = text.split(" ", 1)
        try:
            amount = int(parts[0].replace(",", ""))
            desc = parts[1] if len(parts) > 1 else "Басқа"
            user = get_user(user_id)
            user["expenses"].append({"amount": amount, "desc": desc, "date": datetime.now().strftime("%Y-%m-%d")})
            update_user(user_id, user)
            context.user_data["state"] = None
            await update.message.reply_text(
                f"✅ Шығыс қосылды: *{amount:,} ₸* — {desc}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💰 Қаржыға оралу", callback_data="menu_finance")]])
            )
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Формат: `5000 Азық-түлік`", parse_mode="Markdown")

    elif state == "adding_income":
        parts = text.split(" ", 1)
        try:
            amount = int(parts[0].replace(",", ""))
            desc = parts[1] if len(parts) > 1 else "Басқа"
            user = get_user(user_id)
            user["incomes"].append({"amount": amount, "desc": desc, "date": datetime.now().strftime("%Y-%m-%d")})
            update_user(user_id, user)
            context.user_data["state"] = None
            await update.message.reply_text(
                f"✅ Кіріс қосылды: *{amount:,} ₸* — {desc}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💰 Қаржыға оралу", callback_data="menu_finance")]])
            )
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Формат: `150000 Жалақы`", parse_mode="Markdown")

    else:
        await show_main_menu(update, context)

# ─── ЗАПУСК БОТА ──────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_password)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_data_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🤖 Smart Reminder Bot іске қосылды...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

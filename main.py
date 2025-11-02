import os
import sqlite3
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackContext,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from dotenv import load_dotenv
import pytz

TIMEZONE = pytz.timezone("Asia/Samarkand")
load_dotenv()

# States for conversation
YEAR, MONTH, DAY, HOUR, MINUTE, TASK, DELETE_TASK, PHONE = range(8)

# Initialize scheduler
jobstores = {'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')}
scheduler = AsyncIOScheduler(jobstores=jobstores, timezone=TIMEZONE)
scheduler.start()

# Database setup
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone_number TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_text TEXT,
            scheduled_time TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def save_user(user_id, username, first_name, last_name, phone_number):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, phone_number)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name, phone_number))
    conn.commit()
    conn.close()

def save_task(user_id, task_text, scheduled_time):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (user_id, task_text, scheduled_time)
        VALUES (?, ?, ?)
    ''', (user_id, task_text, scheduled_time))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

def get_user_tasks(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT task_id, task_text, scheduled_time FROM tasks WHERE user_id = ?', (user_id,))
    tasks = cursor.fetchall()
    conn.close()
    return tasks

def delete_task(task_id, user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE task_id = ? AND user_id = ?', (task_id, user_id))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

async def check_registration(update: Update, context: CallbackContext) -> bool:
    user_id = update.message.from_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text(
            "❌ Siz ro'yxatdan o'tmagansiz!\n"
            "Iltimos, avval ro'yxatdan o'ting: /register"
        )
        return False
    return True

async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user = get_user(user_id)
    
    if user:
        await update.message.reply_text(
            f"Salom {user[2]}! Men Budulnik botiman.\n"
            "Vazifa qo'shish uchun /add buyrug'ini yuboring.\n"
            "Vazifalarni ko'rish uchun /list.\n"
            "Vazifani o'chirish uchun /delete."
        )
    else:
        await update.message.reply_text(
            "Salom! Men Budulnik botiman.\n"
            "Botdan foydalanish uchun avval ro'yxatdan o'ting: /register\n\n"
            "Vazifa qo'shish uchun /add buyrug'ini yuboring.\n"
            "Vazifalarni ko'rish uchun /list.\n"
            "Vazifani o'chirish uchun /delete."
        )

async def register(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    user = get_user(user_id)
    
    if user:
        await update.message.reply_text("✅ Siz allaqachon ro'yxatdan o'tgansiz!")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📱 Ro'yxatdan o'tish uchun telefon raqamingizni yuboring:\n\n"
        "Telefon raqamingizni \"Raqamni ulashish\" tugmasi orqali yuboring yoki\n"
        "+998901234567 formatida kiriting:",
        reply_markup=ReplyKeyboardMarkup(
            [[{"text": "📞 Raqamni ulashish", "request_contact": True}]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return PHONE

async def get_phone(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    user_data = update.message.from_user
    
    if update.message.contact:
        phone_number = update.message.contact.phone_number
    else:
        phone_number = update.message.text
    
    # Save user to database
    save_user(
        user_id=user_id,
        username=user_data.username,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        phone_number=phone_number
    )
    
    await update.message.reply_text(
        "✅ Ro'yxatdan o'tdingiz! Endi vazifa qo'shishingiz mumkin: /add",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def add_task(update: Update, context: CallbackContext) -> int:
    if not await check_registration(update, context):
        return ConversationHandler.END
    
    # Get current year for keyboard
    current_year = datetime.now().year
    years = [str(current_year + i) for i in range(3)]  # Next 3 years
    
    keyboard = [years[i:i+3] for i in range(0, len(years), 3)]
    
    await update.message.reply_text(
        "📅 Vazifa uchun yilni tanlang:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return YEAR

async def get_year(update: Update, context: CallbackContext) -> int:
    context.user_data['year'] = update.message.text
    
    months = [
        ["Yanvar", "Fevral", "Mart"],
        ["Aprel", "May", "Iyun"],
        ["Iyul", "Avgust", "Sentabr"],
        ["Oktabr", "Noyabr", "Dekabr"]
    ]
    
    await update.message.reply_text(
        "📅 Oy ni tanlang:",
        reply_markup=ReplyKeyboardMarkup(months, one_time_keyboard=True, resize_keyboard=True)
    )
    return MONTH

async def get_month(update: Update, context: CallbackContext) -> int:
    month_mapping = {
        'Yanvar': 1, 'Fevral': 2, 'Mart': 3, 'Aprel': 4,
        'May': 5, 'Iyun': 6, 'Iyul': 7, 'Avgust': 8,
        'Sentabr': 9, 'Oktabr': 10, 'Noyabr': 11, 'Dekabr': 12
    }
    context.user_data['month'] = month_mapping[update.message.text]
    
    # Generate days keyboard (1-31)
    days = [[str(i), str(i+1), str(i+2)] for i in range(1, 32, 3)]
    
    await update.message.reply_text(
        "📅 Kunni tanlang:",
        reply_markup=ReplyKeyboardMarkup(days, one_time_keyboard=True, resize_keyboard=True)
    )
    return DAY

async def get_day(update: Update, context: CallbackContext) -> int:
    context.user_data['day'] = update.message.text
    
    hours = [[f"{i:02d}", f"{i+1:02d}", f"{i+2:02d}", f"{i+3:02d}"] for i in range(0, 24, 4)]
    
    await update.message.reply_text(
        "⏰ Soatni tanlang (24 soatlik format):",
        reply_markup=ReplyKeyboardMarkup(hours, one_time_keyboard=True, resize_keyboard=True)
    )
    return HOUR

async def get_hour(update: Update, context: CallbackContext) -> int:
    context.user_data['hour'] = update.message.text
    
    minutes = [[f"{i:02d}", f"{i+5:02d}", f"{i+10:02d}", f"{i+15:02d}"] for i in range(0, 60, 20)]
    
    await update.message.reply_text(
        "⏰ Minutni tanlang:",
        reply_markup=ReplyKeyboardMarkup(minutes, one_time_keyboard=True, resize_keyboard=True)
    )
    return MINUTE

async def get_minute(update: Update, context: CallbackContext) -> int:
    context.user_data['minute'] = update.message.text
    
    await update.message.reply_text(
        "📝 Vazifa matnini yuboring:",
        reply_markup=ReplyKeyboardRemove()
    )
    return TASK

async def get_task(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    task_text = update.message.text
    
    # Create datetime object
    try:
        year = int(context.user_data['year'])
        month = int(context.user_data['month'])
        day = int(context.user_data['day'])
        hour = int(context.user_data['hour'])
        minute = int(context.user_data['minute'])
        
        scheduled_time = TIMEZONE.localize(datetime(year, month, day, hour, minute))
        current_time = datetime.now(TIMEZONE)
        
        if scheduled_time <= current_time:
            await update.message.reply_text("❌ Xato: Vaqt o'tgan sana yoki vaqtni kiritdingiz! Qaytadan urining: /add")
            return ConversationHandler.END
            
    except ValueError as e:
        await update.message.reply_text(f"❌ Xato: Noto'g'ri sana formati! Qaytadan urining: /add")
        return ConversationHandler.END
    
    # Save task to database
    task_id = save_task(user_id, task_text, scheduled_time)
    
    # Schedule the job
    job = scheduler.add_job(
        send_reminder,
        'date',
        run_date=scheduled_time,
        args=[user_id, task_text, task_id]
    )
    
    await update.message.reply_text(
        f"✅ Vazifa qo'shildi!\n"
        f"📅 Sana: {scheduled_time.strftime('%Y-%m-%d %H:%M')}\n"
        f"📝 Vazifa: {task_text}"
    )
    return ConversationHandler.END

async def list_tasks(update: Update, context: CallbackContext) -> None:
    if not await check_registration(update, context):
        return
    
    user_id = update.message.from_user.id
    tasks = get_user_tasks(user_id)
    
    if not tasks:
        await update.message.reply_text("📭 Hozircha vazifalar mavjud emas.")
        return
    
    tasks_text = "📋 Sizning vazifalaringiz:\n\n"
    for task_id, task_text, scheduled_time in tasks:
        task_time = datetime.fromisoformat(scheduled_time)
        tasks_text += f"🆔 ID: {task_id}\n"
        tasks_text += f"⏰ Vaqt: {task_time.strftime('%Y-%m-%d %H:%M')}\n"
        tasks_text += f"📝 Vazifa: {task_text}\n"
        tasks_text += "─" * 20 + "\n"
    
    await update.message.reply_text(tasks_text)

async def delete_task_command(update: Update, context: CallbackContext) -> int:
    if not await check_registration(update, context):
        return ConversationHandler.END
    
    await update.message.reply_text("🗑 O'chirish uchun vazifa ID sini yuboring:")
    return DELETE_TASK

async def remove_task(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    
    try:
        task_id = int(update.message.text)
    except ValueError:
        await update.message.reply_text("❌ Xato: ID raqam bo'lishi kerak!")
        return DELETE_TASK
    
    success = delete_task(task_id, user_id)
    
    if success:
        # Also remove from scheduler if possible
        # Note: APScheduler doesn't have a direct way to find jobs by args
        # We'll rely on database cleanup for now
        await update.message.reply_text("✅ Vazifa o'chirildi.")
    else:
        await update.message.reply_text("❌ Xato: Bunday ID topilmadi yoki sizga tegishli emas.")
    
    return ConversationHandler.END

async def send_reminder(user_id: int, task_text: str, task_id: int) -> None:
    try:
        await application.bot.send_message(
            chat_id=user_id, 
            text=f"🔔 ESLA!TMA:\n\n{task_text}"
        )
        # Remove task from database after sending
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error sending reminder: {e}")

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def profile(update: Update, context: CallbackContext) -> None:
    if not await check_registration(update, context):
        return
    
    user_id = update.message.from_user.id
    user = get_user(user_id)
    
    profile_text = (
        f"👤 Profil ma'lumotlari:\n\n"
        f"🆔 ID: {user[0]}\n"
        f"👤 Ism: {user[2]}\n"
        f"📞 Telefon: {user[4]}\n"
        f"📅 Ro'yxatdan o'tgan: {user[5]}"
    )
    
    await update.message.reply_text(profile_text)

def main() -> None:
    global application
    application = Application.builder().token("8372137251:AAFZhRDsvvM7DmoQfquZ_iAlqq-qd0Zs4Js").build()
    
    # Registration conversation
    reg_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('register', register)],
        states={
            PHONE: [
                MessageHandler(filters.CONTACT, get_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Task conversation
    task_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add', add_task)],
        states={
            YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_year)],
            MONTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_month)],
            DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_day)],
            HOUR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_hour)],
            MINUTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_minute)],
            TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_task)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Delete conversation
    delete_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('delete', delete_task_command)],
        states={
            DELETE_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_task)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('list', list_tasks))
    application.add_handler(CommandHandler('profile', profile))
    application.add_handler(reg_conv_handler)
    application.add_handler(task_conv_handler)
    application.add_handler(delete_conv_handler)

    application.run_polling()

if __name__ == '__main__':
    main()

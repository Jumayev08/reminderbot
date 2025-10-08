import os
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
TIME, TASK, DELETE_TASK = range(3)

# Initialize scheduler
jobstores = {'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')}
scheduler = AsyncIOScheduler(jobstores=jobstores, timezone=TIMEZONE)
scheduler.start()

tasks_db = {}

async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "Salom! Men Budulnik botiman.\n"
        "Vazifa qo'shish uchun /add buyrug'ini yuboring.\n"
        "Vazifalarni ko'rish uchun /list.\n"
        "Vazifani o'chirish uchun /delete."
    )

async def add_task(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text(
        "Vazifa vaqtini HH:MM formatida yuboring:",
        reply_markup=ReplyKeyboardRemove()
    )
    return TIME

async def get_time(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    time_str = update.message.text
    
    try:
        datetime.strptime(time_str, "%H:%M").time()
        context.user_data['time'] = time_str
        await update.message.reply_text("Vazifa matnini yuboring:")
        return TASK
    except ValueError:
        await update.message.reply_text("Noto'g'ri format! Qaytadan HH:MM ko'rinishida yuboring:")
        return TIME

async def get_task(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    task_text = update.message.text
    time_str = context.user_data['time']
    
    hour, minute = map(int, time_str.split(':'))
    
    job = scheduler.add_job(
        send_reminder,
        'cron',
        hour=hour,
        minute=minute,
        args=[user_id, task_text]
    )
    
    if user_id not in tasks_db:
        tasks_db[user_id] = {}
    tasks_db[user_id][job.id] = task_text
    
    await update.message.reply_text(f"✅ Vazifa qo'shildi: {time_str} - {task_text}")
    return ConversationHandler.END

async def list_tasks(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in tasks_db or not tasks_db[user_id]:
        await update.message.reply_text("Hozircha vazifalar mavjud emas.")
        return
    
    tasks = [f"ID: {job_id}\n⏰ {task}\n" for job_id, task in tasks_db[user_id].items()]
    await update.message.reply_text("\n".join(tasks))

async def delete_task(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("O'chirish uchun vazifa ID sini yuboring:")
    return DELETE_TASK

async def remove_task(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    job_id = update.message.text
    
    if user_id in tasks_db and job_id in tasks_db[user_id]:
        scheduler.remove_job(job_id)
        del tasks_db[user_id][job_id]
        await update.message.reply_text("✅ Vazifa o'chirildi.")
    else:
        await update.message.reply_text("❌ Xato: Bunday ID topilmadi.")
    
    return ConversationHandler.END

async def send_reminder(user_id: int, task_text: str) -> None:
    await application.bot.send_message(chat_id=user_id, text=f"🔔 Eslatma: {task_text}")

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main() -> None:
    global application
    application = Application.builder().token("8372137251:AAFZhRDsvvM7DmoQfquZ_iAlqq-qd0Zs4Js").build()
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('add', add_task),
            CommandHandler('delete', delete_task),
        ],
        states={
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_task)],
            DELETE_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_task)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('list', list_tasks))
    application.add_handler(conv_handler)

    application.run_polling()

if __name__ == '__main__':
    main()

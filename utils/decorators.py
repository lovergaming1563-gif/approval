from functools import wraps
from config import ADMIN_IDS

def admin_only(func):
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            if update.callback_query:
                await update.callback_query.answer("⛔ Access Denied: Admin only.", show_alert=True)
            elif update.effective_message:
                await update.effective_message.reply_text("⛔ Access Denied: Admin only.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

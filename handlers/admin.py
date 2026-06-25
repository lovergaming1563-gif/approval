from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.manager import DatabaseManager
from database.models import ItemStatus
from utils.decorators import admin_only
import io
import html

db = DatabaseManager()

# Menu buttons
def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
         InlineKeyboardButton("📝 Recent Activity", callback_data="admin_activity")],
        [InlineKeyboardButton("📥 Export Pending", callback_data="export_pending"),
         InlineKeyboardButton("✅ Export Approved", callback_data="export_approved")],
        [InlineKeyboardButton("❌ Export Rejected", callback_data="export_rejected")],
        [InlineKeyboardButton("🧹 Clear Approved", callback_data="clear_approved"),
         InlineKeyboardButton("🧹 Clear Rejected", callback_data="clear_rejected")],
        [InlineKeyboardButton("🔥 Clear All Items", callback_data="clear_all")],
        [InlineKeyboardButton("📁 Upload TXT", callback_data="upload_txt")]
    ]
    return InlineKeyboardMarkup(keyboard)

@admin_only
async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome Admin! Select an option below:",
        reply_markup=get_admin_keyboard()
    )

@admin_only
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "admin_stats":
        stats = db.get_stats()
        text = (
            "📊 <b>Database Statistics</b>\n\n"
            f"⏳ Pending: {stats.get('pending', 0)}\n"
            f"🔄 Assigned: {stats.get('assigned', 0)}\n"
            f"✅ Approved: {stats.get('approved', 0)}\n"
            f"❌ Rejected: {stats.get('rejected', 0)}"
        )
        await query.edit_message_text(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")

    elif data == "admin_back":
        await query.edit_message_text(
            "👋 Welcome Admin! Select an option below:",
            reply_markup=get_admin_keyboard()
        )

    elif data == "admin_activity":
        activity = db.get_recent_activity(10)
        if not activity:
            await query.edit_message_text("No recent activity found.", reply_markup=get_admin_keyboard())
            return
        
        text = "📝 <b>Recent Activity</b>\n\n"
        for item in activity:
            status_emoji = "✅" if item.status == ItemStatus.APPROVED else "❌"
            time_str = item.completed_at.strftime("%Y-%m-%d %H:%M:%S")
            # Escape to prevent HTML parsing errors
            escaped_username = html.escape(item.username or "Unknown")
            escaped_content = html.escape(item.content or "")
            text += f"{status_emoji} {escaped_username} (<code>{item.user_id}</code>)\nItem: <code>{escaped_content}</code>\nTime: {time_str}\n\n"
        
        await query.edit_message_text(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")

    elif data.startswith("export_"):
        status_map = {
            "export_pending": ItemStatus.PENDING,
            "export_approved": ItemStatus.APPROVED,
            "export_rejected": ItemStatus.REJECTED
        }
        status = status_map[data]
        items = db.export_items(status)
        
        if not items:
            await query.message.reply_text(f"No {status.value} items to export.")
            return

        file_content = "\n".join(items)
        file_obj = io.BytesIO(file_content.encode('utf-8'))
        
        await query.message.reply_document(
            document=file_obj, 
            filename=f"{status.value}_items.txt", 
            caption=f"Exported {len(items)} {status.value} items."
        )

    elif data.startswith("clear_"):
        if data == "clear_all":
            db.clear_all_items()
            await query.edit_message_text("🔥 All database items cleared successfully!", reply_markup=get_admin_keyboard())
        else:
            status = ItemStatus.APPROVED if "approved" in data else ItemStatus.REJECTED
            db.clear_items(status)
            await query.edit_message_text(f"🧹 {status.value.capitalize()} list cleared!", reply_markup=get_admin_keyboard())

    elif data == "upload_txt":
        # UX Improvement: Add a back button so the menu doesn't disappear completely
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="admin_back")]])
        await query.edit_message_text(
            "Please upload a .txt file. Each line will be added as a pending item.", 
            reply_markup=keyboard
        )

@admin_only
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document or not update.message.document.file_name.endswith('.txt'):
        await update.message.reply_text("Please upload a valid .txt file.")
        return

    # Use compatible get_file() and download_to_memory() methods for PTB v21.x
    file = await update.message.document.get_file()
    file_bytes = io.BytesIO()
    await file.download_to_memory(out=file_bytes)
    file_bytes.seek(0)

    try:
        content_str = file_bytes.read().decode('utf-8-sig')  # Handles UTF-8 with BOM
    except UnicodeDecodeError:
        file_bytes.seek(0)
        content_str = file_bytes.read().decode('latin-1')  # Fallback encoding

    lines = content_str.splitlines()
    count = db.add_items(lines)
    
    await update.message.reply_text(
        f"✅ Successfully added {count} unique pending items.", 
        reply_markup=get_admin_keyboard()
    )

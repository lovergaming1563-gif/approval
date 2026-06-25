import asyncio
import json
import urllib.request
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.manager import DatabaseManager
from database.models import ItemStatus
import html

db = DatabaseManager()
logger = logging.getLogger(__name__)

# Global dict to store active tasks: {user_id: Task}
active_tasks = {}

def get_user_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔍 Request Item", callback_data="request_item")]])

def get_resolve_keyboard():
    keyboard = [[
        InlineKeyboardButton("✅ Approve", callback_data="approve_item"),
        InlineKeyboardButton("❌ Reject", callback_data="reject_item")
    ]]
    return InlineKeyboardMarkup(keyboard)

def format_item_content(content: str) -> str:
    if not content:
        return ""
    if "|" in content:
        parts = [p.strip() for p in content.split("|", 1)]
        number = parts[0]
        link = parts[1]
        
        escaped_number = html.escape(number)
        escaped_link = html.escape(link)
        
        if link.startswith(("http://", "https://")):
            return f"<code>{escaped_number}</code> | <a href=\"{escaped_link}\">{escaped_link}</a>"
        else:
            return f"<code>{escaped_number}</code> | <code>{escaped_link}</code>"
    else:
        content_stripped = content.strip()
        escaped_content = html.escape(content_stripped)
        if content_stripped.startswith(("http://", "https://")):
            return f"<a href=\"{escaped_content}\">{escaped_content}</a>"
        return f"<code>{escaped_content}</code>"

def extract_link(content: str) -> str | None:
    if not content:
        return None
    if "|" in content:
        parts = [p.strip() for p in content.split("|", 1)]
        link = parts[1]
        if link.startswith(("http://", "https://")):
            return link
    else:
        content_stripped = content.strip()
        if content_stripped.startswith(("http://", "https://")):
            return content_stripped
    return None

def sync_fetch_url(url: str) -> str | None:
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return None

async def fetch_latest_sms(url: str) -> tuple[str, dict] | None:
    content = await asyncio.to_thread(sync_fetch_url, url)
    if not content:
        return None
    try:
        data = json.loads(content)
        if not data:
            return None
        
        # Normalize lists to dicts
        if isinstance(data, list):
            data = {str(i): v for i, v in enumerate(data)}
            
        if not isinstance(data, dict):
            return ("default_key", {"body": str(data)})

        items = []
        for k, v in data.items():
            if v is None:
                continue
            if isinstance(v, dict):
                items.append((k, v))
            else:
                items.append((k, {"body": str(v)}))
                
        if not items:
            return None
            
        items.sort(key=lambda x: x[0])  # Sort lexicographically by Firebase push keys
        return items[-1]
    except Exception as e:
        logger.error(f"Error parsing JSON from {url}: {e}")
        return None

def extract_sms_fields(sms_dict: dict) -> dict:
    if not isinstance(sms_dict, dict):
        return {"body": str(sms_dict), "sender": "Unknown", "date": "", "sim_number": ""}
        
    keys = {k.lower(): k for k in sms_dict.keys()}
    
    # 1. Body/Message detection
    body = ""
    body_key_candidates = ["body", "msg", "message", "text", "content", "sms", "payload"]
    for cand in body_key_candidates:
        if cand in keys:
            body = str(sms_dict[keys[cand]])
            break
    if not body:
        # Fallback: Find the key with the longest string value
        longest_val = ""
        for k, v in sms_dict.items():
            val_str = str(v)
            if len(val_str) > len(longest_val):
                longest_val = val_str
        body = longest_val

    # 2. Sender detection
    sender = "Unknown"
    sender_key_candidates = ["sender", "from", "title", "name", "address", "number"]
    for cand in sender_key_candidates:
        if cand in keys and keys[cand] in sms_dict:
            val_str = str(sms_dict[keys[cand]])
            if val_str != body:
                sender = val_str
                break
            
    # 3. Date detection
    date = ""
    date_key_candidates = ["date", "time", "created_at", "datetime", "timestamp_str"]
    for cand in date_key_candidates:
        if cand in keys and keys[cand] in sms_dict:
            val_str = str(sms_dict[keys[cand]])
            if val_str != body and val_str != sender:
                date = val_str
                break

    # 4. SIM number detection
    sim = ""
    sim_key_candidates = ["sim_number", "sim", "slot", "sim_slot"]
    for cand in sim_key_candidates:
        if cand in keys and keys[cand] in sms_dict:
            sim = str(sms_dict[keys[cand]])
            break

    return {
        "body": body,
        "sender": sender,
        "date": date,
        "sim_number": sim
    }

def format_sms_message(sms: dict) -> str:
    extracted = extract_sms_fields(sms)
    body = html.escape(extracted["body"])
    sender = html.escape(extracted["sender"])
    sim = html.escape(extracted["sim_number"])
    date = html.escape(extracted["date"])
    
    sim_info = f" ({sim})" if sim else ""
    date_info = f"\n📅 <b>Date:</b> {date}" if date else ""
    return (
        f"📨 <b>New SMS Received!</b>\n\n"
        f"👤 <b>Sender:</b> {sender}{sim_info}{date_info}\n\n"
        f"💬 <b>Message:</b>\n<code>{body}</code>"
    )

def format_sms_body_only(sms: dict) -> str:
    extracted = extract_sms_fields(sms)
    body = html.escape(extracted["body"])
    sender = html.escape(extracted["sender"])
    date = html.escape(extracted["date"])
    date_info = f" ({date})" if date else ""
    return f"👤 <b>{sender}</b>{date_info}:\n<code>{body}</code>"

def cancel_active_task(user_id: int):
    task = active_tasks.pop(user_id, None)
    if task:
        task.cancel()
        logger.info(f"Cancelled active polling task for user {user_id}")

async def poll_sms_task(user_id: int, url: str, initial_key: str, context: ContextTypes.DEFAULT_TYPE):
    last_key = initial_key
    logger.info(f"Started polling SMS for user {user_id} on URL: {url} starting from key {last_key}")
    try:
        while True:
            await asyncio.sleep(1)  # Poll every 1 second
            res = await fetch_latest_sms(url)
            if res:
                sms_key, latest_sms = res
                if sms_key > last_key:
                    last_key = sms_key
                    formatted_msg = format_sms_message(latest_sms)
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=formatted_msg,
                            parse_mode="HTML"
                        )
                    except Exception as send_err:
                        logger.error(f"Failed to send SMS to user {user_id}: {send_err}")
    except asyncio.CancelledError:
        logger.info(f"Polling task for user {user_id} cancelled.")
    except Exception as e:
        logger.error(f"Error in polling task for user {user_id}: {e}")

async def user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome! Click the button below to request an item for review.",
        reply_markup=get_user_keyboard()
    )

async def user_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name

    if data == "request_item":
        item, success = db.assign_next_item(user_id, username)
        
        if not success:
            formatted_content = format_item_content(item.content or "")
            
            # Start polling background task if not already polling
            if user_id not in active_tasks:
                url = extract_link(item.content or "")
                if url:
                    res = await fetch_latest_sms(url)
                    initial_key = res[0] if res else ""
                    active_tasks[user_id] = asyncio.create_task(
                        poll_sms_task(user_id, url, initial_key, context)
                    )

            await query.edit_message_text(
                f"⚠️ You already have an assigned item:\n\n{formatted_content}",
                reply_markup=get_resolve_keyboard(),
                parse_mode="HTML"
            )
            return

        if not item:
            await query.edit_message_text("😔 Sorry, no pending items available at the moment.")
            return

        # Cancel any previous task for the user just in case
        cancel_active_task(user_id)

        url = extract_link(item.content or "")
        latest_sms_text = ""
        initial_key = ""
        
        if url:
            res = await fetch_latest_sms(url)
            if res:
                initial_key, latest_sms = res
                latest_sms_text = f"\n\n📖 <b>Latest SMS:</b>\n{format_sms_body_only(latest_sms)}"
            else:
                latest_sms_text = "\n\n📖 <b>Latest SMS:</b>\n<i>No messages found yet.</i>"

            # Start polling background task
            active_tasks[user_id] = asyncio.create_task(
                poll_sms_task(user_id, url, initial_key, context)
            )

        formatted_content = format_item_content(item.content or "")
        await query.edit_message_text(
            f"📦 <b>Assigned Item:</b>\n\n{formatted_content}{latest_sms_text}\n\nPlease approve or reject this item.",
            reply_markup=get_resolve_keyboard(),
            parse_mode="HTML"
        )

    elif data == "approve_item":
        success = db.resolve_item(user_id, ItemStatus.APPROVED)
        cancel_active_task(user_id)
        if success:
            await query.edit_message_text("✅ Item approved successfully!", reply_markup=get_user_keyboard())
        else:
            await query.edit_message_text("❌ No assigned item found to approve.", reply_markup=get_user_keyboard())

    elif data == "reject_item":
        success = db.resolve_item(user_id, ItemStatus.REJECTED)
        cancel_active_task(user_id)
        if success:
            await query.edit_message_text("❌ Item rejected successfully!", reply_markup=get_user_keyboard())
        else:
            await query.edit_message_text("❌ No assigned item found to reject.", reply_markup=get_user_keyboard())

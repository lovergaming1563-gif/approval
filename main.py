import logging
import os
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import TELEGRAM_BOT_TOKEN, ADMIN_IDS
from handlers.admin import admin_start, admin_callback_handler, handle_document
from handlers.user import user_start, user_callback_handler

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class HealthCheckHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        # Prevent request logs from flooding stdout
        pass

def run_health_check_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Starting health check server on port {port}")
    server.serve_forever()

async def start(update, context):
    user_id = update.effective_user.id
    if user_id in ADMIN_IDS:
        await admin_start(update, context)
    else:
        await user_start(update, context)

async def callback_router(update, context):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    
    if data.startswith("admin_") or data.startswith("export_") or data.startswith("clear_") or data == "upload_txt":
        if user_id not in ADMIN_IDS:
            await query.answer("⛔ Access Denied: Admin only.", show_alert=True)
            return
        await admin_callback_handler(update, context)
    else:
        await user_callback_handler(update, context)

def main():
    # Start health check server in background thread for Render
    threading.Thread(target=run_health_check_server, daemon=True).start()

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_router))
    application.add_handler(MessageHandler(filters.Document.FileExtension("txt"), handle_document))

    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()

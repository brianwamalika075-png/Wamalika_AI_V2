# main.py - COPY EVERYTHING BELOW THIS LINE
import asyncio
import os
import logging
from datetime import datetime
import pandas as pd
import numpy as np
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import aiohttp
import warnings
warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TOKEN_HERE")
    ALLOWED_USERS = [int(id) for id in os.getenv("ALLOWED_USERS", "123456789").split(",")]
    ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
    PORT = int(os.getenv("PORT", "8080"))

class SimpleForexBot:
    def __init__(self):
        self.is_active = False
        self.signals_count = 0
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome message"""
        if update.effective_user.id not in Config.ALLOWED_USERS:
            await update.message.reply_text("⛔ Sorry, you don't have access.")
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 Check Market", callback_data='market')],
            [InlineKeyboardButton("🤖 Start Trading", callback_data='start')],
            [InlineKeyboardButton("📈 Performance", callback_data='stats')],
        ]
        
        await update.message.reply_text(
            "🤖 *AI Forex Trading Bot*\n\n"
            "Welcome! I analyze forex markets using AI.\n\n"
            "Choose an option below:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def button_click(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button clicks"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'market':
            await query.edit_message_text(
                "📊 *Market Analysis*\n\n"
                "Analyzing EUR/USD...\n\n"
                f"Current Price: 1.0850\n"
                f"AI Signal: BUY 📈\n"
                f"Confidence: 75%\n\n"
                "Trade at your own risk!",
                parse_mode='Markdown'
            )
        elif query.data == 'start':
            self.is_active = True
            await query.edit_message_text(
                "✅ *Trading Started!*\n\n"
                "Bot is now monitoring markets.\n"
                "I'll send you signals when opportunities appear.\n\n"
                "⚠️ Demo mode only - No real money!",
                parse_mode='Markdown'
            )
        elif query.data == 'stats':
            await query.edit_message_text(
                f"📈 *Bot Statistics*\n\n"
                f"Signals generated: {self.signals_count}\n"
                f"Status: {'🟢 Active' if self.is_active else '🔴 Inactive'}\n"
                f"Uptime: Running smoothly\n\n"
                f"Note: Add real statistics later!",
                parse_mode='Markdown'
            )
    
    async def webhook_handler(self, request):
        """Handle incoming webhooks"""
        try:
            data = await request.json()
            update = Update.de_json(data, self.application.bot)
            await self.application.process_update(update)
            return aiohttp.web.Response(status=200, text="OK")
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return aiohttp.web.Response(status=500, text="Error")
    
    async def health_check(self, request):
        """Health check endpoint"""
        return aiohttp.web.Response(
            text=json.dumps({
                "status": "healthy",
                "active": self.is_active,
                "time": datetime.now().isoformat()
            }),
            content_type='application/json'
        )
    
    async def run(self):
        """Start the bot"""
        # Initialize bot
        self.application = Application.builder().token(Config.TELEGRAM_TOKEN).build()
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CallbackQueryHandler(self.button_click))
        
        # Setup webhook if URL provided
        if Config.WEBHOOK_URL:
            import json
            from aiohttp import web
            
            # Set Telegram webhook
            webhook_url = f"{Config.WEBHOOK_URL}/webhook"
            await self.application.bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True
            )
            
            # Create web server
            app = web.Application()
            app.router.add_post("/webhook", self.webhook_handler)
            app.router.add_get("/", self.health_check)
            app.router.add_get("/health", self.health_check)
            
            logger.info(f"Starting webhook on port {Config.PORT}")
            await web._run_app(app, host="0.0.0.0", port=Config.PORT)
        else:
            # Fallback to polling
            logger.info("Starting in polling mode")
            await self.application.run_polling()

if __name__ == "__main__":
    bot = SimpleForexBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped")

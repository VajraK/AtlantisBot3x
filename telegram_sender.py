import os
import logging
import asyncio
import yaml
from telegram import Bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

class TelegramSender:
    def __init__(self, token=None, chat_id=None):
        config = load_config()
        self.token = token or config.get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or config.get("telegram_chat_id") or os.environ.get("TELEGRAM_CHAT_ID")
        if not self.token or not self.chat_id:
            logger.error("Telegram bot token or chat ID missing!")
            raise ValueError("Telegram bot token and chat ID must be provided")
        self.bot = Bot(token=self.token)

    async def send_filing_result(self, result: str, url: str):
        """
        Sends the summarized investment opportunity to Telegram with the original source URL.
        Skips sending if result is empty or just 'X'.
        """
        if not result or result.strip() == 'X':
            logger.info("Result is empty or 'X'; skipping Telegram message.")
            return

        message = f"✨\n\n{result}\n\n🔗 URL\n{url}"

        try:
            await self.bot.send_message(chat_id=self.chat_id, text=message)
            logger.info(f"✅ Sent Telegram message for URL: {url}")
        except Exception as e:
            logger.error(f"❌ Failed to send Telegram message: {e}")

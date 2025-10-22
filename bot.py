import os
import time
import json
import feedparser
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError

# Load env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@cs2insidedraw")  # channel or chat id where drafts go
INTERVAL = int(os.getenv("INTERVAL", 600))  # seconds between checks
SOURCES_FILE = os.getenv("SOURCES_FILE", "sources.txt")
STATE_FILE = os.getenv("STATE_FILE", "posted.json")

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN not set in environment")

bot = Bot(token=BOT_TOKEN)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Load or init posted links state (to avoid reposts)
if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            posted_links = set(json.load(f))
    except Exception:
        posted_links = set()
else:
    posted_links = set()

def save_state():
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(posted_links), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error("Failed to save state: %s", e)

def load_sources(path=SOURCES_FILE):
    if not os.path.exists(path):
        logging.error("Sources file not found: %s", path)
        return []
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
    return lines

def format_entry(entry, source_url):
    title = getattr(entry, "title", "No title")
    link = getattr(entry, "link", "")
    published = getattr(entry, "published", getattr(entry, "updated", ""))
    # Build compact message for drafts
    msg = f"📰 <b>{title}</b>\\n\\n🔗 {link}\\n\\n🔎 Источник: {source_url}\\n🕓 {published}"
    return msg, link

def fetch_and_send():
    sources = load_sources()
    if not sources:
        logging.warning("No feeds found in sources file.")
        return
    for src in sources:
        try:
            feed = feedparser.parse(src)
            entries = getattr(feed, "entries", [])[:5]
            for entry in entries:
                link = getattr(entry, "link", None)
                if not link or link in posted_links:
                    continue
                msg, link = format_entry(entry, src)
                try:
                    bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode="HTML", disable_web_page_preview=False)
                    logging.info("Sent: %s", link)
                    posted_links.add(link)
                    # be polite with Telegram rate limits
                    time.sleep(1.5)
                except TelegramError as te:
                    logging.error("Telegram error sending message: %s", te)
                except Exception as e:
                    logging.error("Failed to send: %s", e)
        except Exception as e:
            logging.error("Failed to parse feed %s: %s", src, e)
    save_state()

def main_loop():
    logging.info("CS2InsideBot RSS worker started. Checking every %s seconds", INTERVAL)
    while True:
        try:
            fetch_and_send()
        except Exception as e:
            logging.exception("Unhandled fetch error: %s", e)
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main_loop()

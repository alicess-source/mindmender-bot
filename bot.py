import os
import json
import random
import tempfile
import datetime as dt
import asyncio
from typing import List

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

# ---------- CONFIG ----------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DAILY_CHANNEL_ID = int(os.getenv("DAILY_CHANNEL_ID", "0"))
QUOTES_FILE = "quotes.json"

# UK timezone
try:
    import zoneinfo
    TZ = zoneinfo.ZoneInfo("Europe/London")
except Exception:
    TZ = dt.timezone.utc

INTENTS = discord.Intents.default()
INTENTS.message_content = True
bot = commands.Bot(command_prefix="!", intents=INTENTS)
quotes_lock = asyncio.Lock()

# ---------- DEFAULT QUOTES ----------
DEFAULT_QUOTES: List[str] = [
    "It's okay not to be okay. You're doing your best.",
    "Small steps still count. Showing up matters.",
    "You are not your thoughts; they come and they go.",
    "Asking for help shows strength, not weakness.",
    "Breathe in calm, breathe out pressure. One moment at a time.",
    "You matter, even on the hard days.",
    "Recovery isn’t linear – and that’s perfectly fine.",
    "You’ve survived every tough day so far. That’s power.",
    "Self-compassion is allowed — especially today.",
    "You don’t have to be perfect to be worthy.",
    "Feeling things deeply means you care — that’s courage.",
    "Rest is productive, too.",
    "Thoughts aren’t facts.",
    "You can start small — progress is still progress.",
    "Good enough is good enough.",
    "You are more than your anxiety.",
    "One slow breath can change everything.",
    "Be as kind to yourself as you are to others.",
    "A pause is not a failure.",
    "You are enough. Always have been."
]

# ---------- FILE HANDLING ----------
def load_quotes() -> List[str]:
    if not os.path.exists(QUOTES_FILE):
        save_quotes_atomic(DEFAULT_QUOTES)
        return list(DEFAULT_QUOTES)
    try:
        with open(QUOTES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and all(isinstance(x, str) for x in data):
            return data
    except Exception:
        pass
    save_quotes_atomic(DEFAULT_QUOTES)
    return list(DEFAULT_QUOTES)

def save_quotes_atomic(quotes: List[str]) -> None:
    os.makedirs(os.path.dirname(QUOTES_FILE) or ".", exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        prefix="quotes_", suffix=".json",
        dir=os.path.dirname(QUOTES_FILE) or "."
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp:
            json.dump(quotes, tmp, ensure_ascii=False, indent=2)
        os.replace(tmp_path, QUOTES_FILE)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

QUOTES = load_quotes()

# nyckelord som triggar auto-svar (endast i daily-quotes-kanalen)
KEYWORDS = {
    "sad", "depressed", "anxious", "anxiety",
    "panic", "stress", "lonely", "tired", "overwhelmed"
}

def random_quote() -> str:
    return random.choice(QUOTES)

# ---------- EVENTS ----------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

    # starta bara loops om vi har ett giltigt kanal-ID
    if DAILY_CHANNEL_ID:
        morning_quote.start()
        evening_quote.start()

    # sätt en liten status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="daily mental health reminders"
        )
    )

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # bara reagera i daily-quotes-kanalen
    if message.channel.id == DAILY_CHANNEL_ID:
        if any(k in message.content.lower() for k in KEYWORDS):
            await message.channel.send(f"💛 {random_quote()}")

    # låt kommandon fungera som vanligt
    await bot.process_commands(message)

# ---------- SLASH COMMANDS ----------
@bot.tree.command(name="quote", description="Get a motivational quote")
async def quote_command(interaction: discord.Interaction):
    # begränsa kommandot till daily-quotes-kanalen
    if interaction.channel_id != DAILY_CHANNEL_ID:
        await interaction.response.send_message(
            "❌ This command only works in the daily-quotes channel!",
            ephemeral=True
        )
        return

    await interaction.response.send_message(f"💛 {random_quote()}")

@bot.tree.command(name="add_quote", description="Add your own quote (saved permanently)")
@app_commands.describe(text="Your quote text")
async def add_quote(interaction: discord.Interaction, text: str):
    t = text.strip()
    if len(t) < 6:
        await interaction.response.send_message(
            "Please write a slightly longer quote 🙏",
            ephemeral=True
        )
        return

    async with quotes_lock:
        if t not in QUOTES:
            QUOTES.append(t)
            save_quotes_atomic(QUOTES)

    await interaction.response.send_message(
        "Thanks! Your quote was saved permanently ✨",
        ephemeral=True
    )

# ---------- DAILY POSTS ----------
@tasks.loop(time=dt.time(hour=9, tzinfo=TZ))
async def morning_quote():
    channel = bot.get_channel(DAILY_CHANNEL_ID)
    if channel:
        await channel.send(
            f"@here 🌅 Good morning! Here's your daily reminder:\n> {random_quote()}"
        )

@tasks.loop(time=dt.time(hour=21, tzinfo=TZ))
async def evening_quote():
    channel = bot.get_channel(DAILY_CHANNEL_ID)
    if channel:
        await channel.send(
            f"@here 🌙 Good evening! Before you rest, remember:\n> {random_quote()}"
        )

# ---------- RUN ----------
if not TOKEN:
    raise SystemExit("Please set DISCORD_TOKEN in .env first.")
bot.run(TOKEN)

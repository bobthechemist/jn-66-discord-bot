
# bot.py
import discord
from discord.ext import commands
import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import json
from utils.scheduler import Scheduler

# --- BOOTSTRAP LOGGING FOR CONFIGURATION ---

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    # NOTE: We do NOT specify handlers here. basicConfig defaults to a StreamHandler (console).
)
log = logging.getLogger(__name__)

# --- CONFIGURATION ---

# Load secrets
load_dotenv()

BOT_TOKEN = os.getenv("DISCORD_TOKEN")
AUTHORIZED_USER_ID = os.getenv("USER_ID") # Discord User ID

# Load configuration information from bot_config.json
try:
    with open('bot_config.json', 'r') as f:
        config = json.load(f)
except FileNotFoundError:
    log.critical("FATAL: bot_config.json not found. Please copy bot_config.json.example to config.json and fill it out.")
    exit()
except json.JSONDecodeError:
    log.critical("FATAL: Could not decode bot_config.json. Please ensure it is valid JSON.")
    exit()

# --- FINAL LOGGER SETUP ---

# Set up logging with with a max file size of 0.5 MB, three log files, and rotation.
log_location = config.get('log_location', 'bot.log')
handler = RotatingFileHandler(
    log_location,  # Log file path
    maxBytes=1*1024*512,  # Maximum file size in bytes (1/2 MB in this example)
    backupCount=3  # Number of backup files to keep
)

root_logger = logging.getLogger()
root_logger.handlers.clear()
root_logger.addHandler(handler)

log.info(f"Logging initialized. Log files will be saved to: {log_location}")

# --- Bot Initialization ---
intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True

class JN66Bot(commands.Bot):
    """JN-66 is a discord bot that serves as an intelligent task management system. It provides a DM-based discord interface to 
    create and review tasks, review (google) calendar events, and store thoughts.
    """
    def __init__(self, config, authorized_user_id):
        super().__init__(command_prefix=config.get('bot_prefix', '!'), intents=intents)
        # Attach the authorized user ID to the bot instance so cogs can access it
        self.authorized_user_id = int(authorized_user_id)
        self.username = config.get('username','a user with no name')
        self.botname = config.get('botname', 'a bot with no name')
        self.db_filename = config.get('db_filename', 'bot.db')
        self.model = config.get('ollama_model','gemma2:2b')
        self.calendars = config.get('calendars_to_check', [])
        self.scheduler = Scheduler(self)


    async def setup_hook(self):
        """A hook that runs after login but before connecting to the websocket."""
        log.info("--- Loading Cogs ---")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    log.info(f"Loaded cog: {filename}")
                except Exception as e:
                    log.error(f"Failed to load cog {filename}", exc_info=True)
        

    async def on_ready(self):
        log.info(f'{self.user} has landed and is ready.')
        # Start scheduled tasks
        self.scheduler.start_all()


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    if not BOT_TOKEN or not AUTHORIZED_USER_ID:
        log.critical("DISCORD_TOKEN and/or USER_ID not found in environment variables.")
    else:
        try:
            bot = JN66Bot(config=config, authorized_user_id=AUTHORIZED_USER_ID)
            bot.run(BOT_TOKEN)
        except discord.errors.LoginFailure:
            log.critical("Login failed: Improper token passed.")
        except Exception as e:
            log.critical(f"An unexpected error occurred.", exc_info=e)


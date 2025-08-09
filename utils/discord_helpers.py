# utils/discord_helpers.py
import discord
import logging

log = logging.getLogger(__name__)

async def send_long_message(channel: discord.abc.Messageable, text: str):
    """
    Sends a message to a Discord channel, splitting it into chunks of 2000 characters
    if it exceeds the limit.
    """
    if not text:
        log.warning("send_long_message was called with empty text.")
        return

    if len(text) <= 2000:
        await channel.send(text)
    else:
        log.info("Response is too long, splitting into chunks...")
        # Split the text into chunks of 2000 characters
        chunks = [text[i:i + 2000] for i in range(0, len(text), 2000)]
        for chunk in chunks:
            await channel.send(chunk)
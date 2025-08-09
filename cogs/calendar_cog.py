# cogs/calendar_cog.py
import discord
from discord.ext import commands
import logging
import os
import asyncio
from datetime import datetime, timedelta, timezone, time


# Google API Imports
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Our Bot's Utility Imports
from utils.ui_helpers import create_embed, EmbedColors
from utils.scheduler import Job

log = logging.getLogger(__name__)

# The scopes define what permissions the bot will request from your Google account.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# --- HELPER CLASS: GOOGLE CALENDAR LOGIC ---
# This class handles all the direct interaction with the Google Calendar API.
# It is kept inside this file because it is only used by the CalendarCog.
class CalendarAssistant:
    def __init__(self, calendars_to_check):
        self.calendars_to_check = [cal['summary'] for cal in calendars_to_check]
        self.creds = self.authenticate()


    def authenticate(self):
        """Handles Google authentication, refreshing tokens as needed."""
        creds = None
        if os.path.exists('gtoken.json'):
            creds = Credentials.from_authorized_user_file('gtoken.json', SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                log.info("Refreshing Google API token.")
                creds.refresh(Request())
            else:
                log.warning("Performing first-time Google API authentication. This requires manual browser interaction.")
                flow = InstalledAppFlow.from_client_secrets_file('gcredentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open('gtoken.json', 'w') as token:
                token.write(creds.to_json())
        return creds

    def fetch_todays_events(self) -> list:
        """Fetches and processes today's events. This is a blocking function."""
        log.info("Fetching today's calendar events.")
        service = build('calendar', 'v3', credentials=self.creds)
        now_utc = datetime.now(timezone.utc)
        timeMin = now_utc.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        timeMax = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        events_today = []
        calendar_list = service.calendarList().list().execute().get('items', [])
        calendar_id_map = {c['summary']: c['id'] for c in calendar_list}
        
        for cal_name in self.calendars_to_check:
            cal_id = calendar_id_map.get(cal_name)
            if not cal_id:
                log.warning(f"Could not find calendar ID for '{cal_name}'. Skipping.")
                continue

            events_result = service.events().list(
                calendarId=cal_id, timeMin=timeMin, timeMax=timeMax,
                singleEvents=True, orderBy='startTime').execute()
            
            for event in events_result.get('items', []):
                summary = event.get('summary', 'No Title')
                start = event.get('start', {})
                
                if 'dateTime' in start:
                    start_time_obj = datetime.fromisoformat(start['dateTime'])
                    start_time_str = start_time_obj.strftime('%I:%M %p') # e.g., 09:30 AM
                else:
                    naive_date = datetime.fromisoformat(start['date'])
                    start_time_obj = naive_date.replace(tzinfo=timezone.utc)
                    start_time_str = 'All-Day'
                    
                events_today.append({
                    'calendar': cal_name, 
                    'summary': summary, 
                    'start_time': start_time_str,
                    'sort_key': start_time_obj # Use the datetime object for accurate sorting
                })
        
        # Sort events chronologically, handling All-Day events properly
        return sorted(events_today, key=lambda x: x['sort_key'])


# --- THE COG CLASS ---
class CalendarCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Initialize the assistant when the cog is loaded.
        self.assistant = CalendarAssistant(calendars_to_check=bot.calendars)
        # Scheduled task to run every day at 6:00 PM
        calendar_job = Job(
            callback=self.scheduled_today_task,
            target_id=self.bot.authorized_user_id,
            target_type='dm',
            target_time=time(10, 25, tzinfo=timezone.utc), # +4 for the moment
            hours=24,
        )
        self.bot.scheduler.add_job(calendar_job)



    async def _build_today_response(self) -> tuple[discord.Embed, discord.ui.View | None]:
        """
        An internal helper that fetches the calendar and builds the embed and view.
        This contains the core logic shared by the command and scheduled job.
        
        Returns:
            A a tuble containing (embed, None) (future use will contain a view).
        """

        events = await asyncio.to_thread(self.assistant.fetch_todays_events)

        if not events:
            final_embed = create_embed("Today's Agenda", "🎉 You have no events scheduled for today. Enjoy the peace!", EmbedColors.SUCCESS)
        else:
            description_parts = []
            current_calendar = None
            for event in events:
                # Add a header for each new calendar
                if event['calendar'] != current_calendar:
                    current_calendar = event['calendar']
                    description_parts.append(f"\n**📅 {current_calendar}**")
                
                description_parts.append(f"• `{event['start_time']}` - {event['summary']}")
            
            final_embed = create_embed("Today's Agenda", "\n".join(description_parts), EmbedColors.INFO)

            return (final_embed, None)

    @commands.command(name="today")
    @commands.dm_only()
    async def get_todays_events(self, ctx: commands.Context):
        """Fetches and displays all events for today from your configured Google Calendars."""
        # This command should only be used by the authorized user.
        if ctx.author.id != self.bot.authorized_user_id:
            log.error(f"--> User with id {ctx.author.id} isn't authorized to access calendars.")
            return

        try:
            # 1. Acknowledge immediately so the user knows the bot is working.
            thinking_embed = create_embed("Checking Calendars...", "Please wait while I fetch your schedule.", EmbedColors.INFO)
            message = await ctx.send(embed=thinking_embed)
            # 4. Edit the original message with the final result.
            embed, view = await self._build_today_response()
            await message.edit(embed=embed)

        except Exception as e:
            log.error(f"An error occurred in the today command: {e}", exc_info=True)
            error_embed = create_embed("Error", f"An unexpected error occurred while fetching calendar events: {e}", EmbedColors.ERROR)
            # Try to edit the original message, or send a new one if that fails.
            if 'message' in locals():
                await message.edit(embed=error_embed)
            else:
                await ctx.send(embed=error_embed)
    
    async def scheduled_today_task(self, target: discord.User):
        """A special version of the 'today' command designed for the scheduler."""
        log.info(f"Running scheduled 'today' job for {target.name}")
        try:
            embed, view = await self._build_today_response()
            await target.send(embed=embed)
        except Exception as e:
            log.error(f"Error in scheduled 'today' job: {e}", exc_info=True)
            await target.send(embed=create_embed("Error", "Sorry, an error occurred while fetching your calendar.", EmbedColors.ERROR))



# This async function is required for the cog to be loaded by the bot.
async def setup(bot: commands.Bot):
    await bot.add_cog(CalendarCog(bot))
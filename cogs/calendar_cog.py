# cogs/calendar_cog.py
import discord
from discord.ext import commands
import logging
import os
import asyncio
from datetime import datetime, timedelta, timezone, time
import pytz 

# ... (Google API Imports and other imports are the same) ...
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from utils.ui_helpers import create_embed, EmbedColors
from utils.scheduler import Job

log = logging.getLogger(__name__)
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

class CalendarAssistant:
    # --- NEW: Pass the local timezone into the assistant ---
    def __init__(self, calendars_to_check, local_timezone_str):
        self.calendars_to_check = [cal['summary'] for cal in calendars_to_check]
        self.creds = self.authenticate()
        
        # --- NEW: Store the user's local timezone object ---
        try:
            self.local_timezone = pytz.timezone(local_timezone_str)
            log.info(f"Calendar assistant initialized with timezone: {self.local_timezone}")
        except pytz.UnknownTimeZoneError:
            log.error(f"Unknown timezone '{local_timezone_str}'. Defaulting to UTC.")
            self.local_timezone = pytz.utc

    def authenticate(self):
        # ... (this method is unchanged) ...
        creds = None
        if os.path.exists('gtoken.json'):
            creds = Credentials.from_authorized_user_file('gtoken.json', SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('gcredentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            with open('gtoken.json', 'w') as token:
                token.write(creds.to_json())
        return creds

    def fetch_todays_events(self) -> list:
        """Fetches and processes today's events, correctly handling timezones."""
        log.info("Fetching today's calendar events.")
        service = build('calendar', 'v3', credentials=self.creds)
        
        # --- NEW: Get the start/end of the day in the user's local timezone ---
        now_local = datetime.now(self.local_timezone)
        timeMin_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        timeMax_local = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        # Convert to UTC ISO format for the API call
        timeMin = timeMin_local.astimezone(pytz.utc).isoformat()
        timeMax = timeMax_local.astimezone(pytz.utc).isoformat()

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
                    # --- THIS IS THE MAIN FIX ---
                    # 1. Parse the datetime string from the API
                    naive_dt = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))

                    # 2. Check if the datetime object is naive (has no tzinfo)
                    if naive_dt.tzinfo is None or naive_dt.tzinfo.utcoffset(naive_dt) is None:
                        # If it's naive, assume it's in the event's specified timezone (or UTC as a fallback)
                        event_tz_str = event.get('timeZone', 'UTC')
                        event_tz = pytz.timezone(event_tz_str)
                        # Make the datetime "aware" by localizing it
                        start_time_obj = event_tz.localize(naive_dt)
                    else:
                        # If it's already aware, just use it
                        start_time_obj = naive_dt
                    
                    # 3. Convert the final "aware" object to the user's local timezone for display
                    start_time_local = start_time_obj.astimezone(self.local_timezone)
                    start_time_str = start_time_local.strftime('%I:%M %p')
                else: # All-day event
                    naive_date = datetime.fromisoformat(start['date'])
                    start_time_obj = self.local_timezone.localize(naive_date)
                    start_time_str = 'All-Day'
                    
                events_today.append({
                    'calendar': cal_name, 
                    'summary': summary, 
                    'start_time': start_time_str,
                    'sort_key': start_time_obj
                })
        
        return sorted(events_today, key=lambda x: x['sort_key'])


class CalendarCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # --- NEW: Get the timezone from the bot's config ---
        self.local_timezone_str = getattr(self.bot, 'local_timezone', 'UTC')
        self.assistant = CalendarAssistant(calendars_to_check=bot.calendars, local_timezone_str=self.local_timezone_str)
        
        # ... (rest of your cog is the same) ...
        calendar_job = Job(
            callback=self.scheduled_today_task,
            target_id=self.bot.authorized_user_id,
            target_type='dm',
            target_time=time(10, 25, tzinfo=timezone.utc),
            hours=24,
        )
        self.bot.scheduler.add_job(calendar_job)
    
    # ... (the rest of the cog's methods like _build_today_response, get_todays_events, etc. are unchanged) ...
    async def _build_today_response(self) -> tuple[discord.Embed, discord.ui.View | None]:
        events = await asyncio.to_thread(self.assistant.fetch_todays_events)
        if not events:
            final_embed = create_embed("Today's Agenda", "🎉 You have no events scheduled for today. Enjoy the peace!", EmbedColors.SUCCESS)
        else:
            description_parts = []
            current_calendar = None
            for event in events:
                if event['calendar'] != current_calendar:
                    current_calendar = event['calendar']
                    description_parts.append(f"\n**📅 {current_calendar}**")
                description_parts.append(f"• `{event['start_time']}` - {event['summary']}")
            final_embed = create_embed("Today's Agenda", "\n".join(description_parts), EmbedColors.INFO)
        return (final_embed, None)

    @commands.command(name="today")
    @commands.dm_only()
    async def get_todays_events(self, ctx: commands.Context):
        if ctx.author.id != self.bot.authorized_user_id:
            return
        try:
            thinking_embed = create_embed("Checking Calendars...", "Please wait while I fetch your schedule.", EmbedColors.INFO)
            message = await ctx.send(embed=thinking_embed)
            embed, view = await self._build_today_response()
            await message.edit(embed=embed)
        except Exception as e:
            log.error(f"An error occurred in the today command: {e}", exc_info=True)
            error_embed = create_embed("Error", f"An unexpected error occurred: {e}", EmbedColors.ERROR)
            if 'message' in locals():
                await message.edit(embed=error_embed)
            else:
                await ctx.send(embed=error_embed)
    
    async def scheduled_today_task(self, target: discord.User):
        log.info(f"Running scheduled 'today' job for {target.name}")
        try:
            embed, view = await self._build_today_response()
            await target.send(embed=embed)
        except Exception as e:
            log.error(f"Error in scheduled 'today' job: {e}", exc_info=True)
            await target.send(embed=create_embed("Error", "Sorry, an error occurred while fetching your calendar.", EmbedColors.ERROR))

async def setup(bot: commands.Bot):
    await bot.add_cog(CalendarCog(bot))
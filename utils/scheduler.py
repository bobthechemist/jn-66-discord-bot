# utils/scheduler.py
import asyncio
import logging
from datetime import datetime, time, timedelta, timezone
import discord
from discord.ext import tasks, commands

log = logging.getLogger(__name__)

# time_until function remains the same...
def time_until(target_time: time) -> float:
    # ... (no changes here)
    now = datetime.now(timezone.utc)
    target_today = datetime.combine(now.date(), target_time, tzinfo=timezone.utc)
    if target_today < now:
        target_tomorrow = target_today + timedelta(days=1)
        return (target_tomorrow - now).total_seconds()
    else:
        return (target_today - now).total_seconds()

class Job:
    """Represents a single job to be scheduled."""
    # --- MODIFICATION: Make target_time optional ---
    def __init__(self, callback, target_id: int, target_type: str, target_time: time | None = None, **frequency_kwargs):
        """
        Args:
            callback: The async function to call.
            target_id: The ID of the user or channel to send the message to.
            target_type: Must be 'dm' or 'channel'.
            target_time: (Optional) The time of day (in UTC) to run the job. If None, the job starts immediately.
            **frequency_kwargs: Keyword arguments for discord.ext.tasks.loop()
        """
        # ... (validation checks remain the same) ...
        self.callback = callback
        self.target_id = target_id
        self.target_type = target_type
        self.target_time = target_time
        self.frequency_kwargs = frequency_kwargs
        self.task = None

class Scheduler:
    # ... (__init__ remains the same) ...
    def __init__(self, bot: commands.Bot):
        self._jobs = []
        self.bot = bot
        self.timezone = None # Will get from a configuration eventually

    def add_job(self, job: Job):
        """Creates and schedules a task based on a Job object."""
        async def job_wrapper():
            # ... (this wrapper remains the same) ...
            target = None
            try:
                if job.target_type == 'dm':
                    target = await self.bot.fetch_user(job.target_id)
                elif job.target_type == 'channel':
                    target = self.bot.get_channel(job.target_id)
                if target:
                    await job.callback(target)
                else:
                    log.error(f"Scheduled job '{job.callback.__name__}' failed: Could not find target with ID {job.target_id}")
            except Exception as e:
                log.error(f"An error occurred in scheduled job '{job.callback.__name__}': {e}", exc_info=True)

        async def before_wrapper():
            # --- MODIFICATION: Handle optional target_time ---
            if job.target_time:
                # If a time is specified, wait for it.
                seconds = time_until(job.target_time)
                log.info(f"Job '{job.callback.__name__}' waiting {seconds:.2f} seconds until its next run at {job.target_time}.")
                await asyncio.sleep(seconds)
            else:
                # If no time is specified, start the loop immediately.
                log.info(f"Job '{job.callback.__name__}' starting its first cycle immediately.")
                return

        task_loop = tasks.loop(**job.frequency_kwargs)(job_wrapper)
        task_loop.before_loop(before_wrapper)
        
        job.task = task_loop
        self._jobs.append(job)
        log.info(f"Successfully scheduled job '{job.callback.__name__}' to target '{job.target_type}' with ID {job.target_id}.")


    def start_all(self):
        # ... (no changes here)
        log.info(f"Starting {len(self._jobs)} scheduled job(s)...")
        for job in self._jobs:
            if not job.task.is_running():
                job.task.start()
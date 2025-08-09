# cogs/llm_cog.py
import discord
from discord.ext import commands
import ollama
import logging
from utils.discord_helpers import send_long_message
from utils.ui_helpers import create_embed, ConfirmationView, EmbedColors
from utils.database_manager import DatabaseManager 
import asyncio
from datetime import datetime, date, time, timezone
from utils.task_agent import Agent as TaskAgent # Use an alias to avoid name confusion
from utils.ui_helpers import TaskView
from utils.scheduler import Job


# --- CONFIGURATION ---
#OLLAMA_MODEL = 'qwen2.5-coder:1.5b'
SYSTEM_PROMPT = f"You are a helpful assistant."
#DATABASE = 'btcbot_test.db'

# ^^^ We might want configuration information to go into btcbot.py

log = logging.getLogger(__name__)

class LLMCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Each cog instance will have its own conversation history
        self.conversation_history = []
        self._initialize_history()
        # As the administrative cog, we control the database
        self.db = DatabaseManager(bot.db_filename)

        # Schedule tasks to run every day at 6:30 AM
        task_job = Job(
            callback=self.scheduled_tasks_task,
            target_id=self.bot.authorized_user_id,
            target_type='dm',
            target_time=time(10, 30, tzinfo=timezone.utc), # No target_time means it starts right away +4 for the moment
            hours=24 # can also be minutes
        )
        self.bot.scheduler.add_job(task_job)

    def _initialize_history(self):
        """Clears the history and adds the initial system prompt."""
        self.conversation_history.clear()
        self.conversation_history.append({'role': 'system', 'content': SYSTEM_PROMPT + f"The name of the User you are speaking with is {self.bot.username}."})
        log.info("LLM conversation history initialized.")



    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """The listener for messages, specific to this cog's functionality."""
        # Standard checks: ignore bots, non-DMs, and unauthorized users
        # We access the authorized ID from the bot instance now
        if (message.author.bot or
            not isinstance(message.channel, discord.DMChannel) or
            message.author.id != self.bot.authorized_user_id):
            return

        
        # If the message is a command, the bot's core will handle it.
        # We only care about messages that are NOT commands.
        if message.content.startswith(self.bot.command_prefix):
            return

        # --- LLM Logic ---
        try:
            self.conversation_history.append({'role': 'user', 'content': message.content})
            # Let's sore the conversation in the database as well.
            self.db.store_message({'author':self.bot.username, 'timestamp':datetime.now().isoformat(), 'message': message.content})
            thinking_message = await message.channel.send("🤔 Thinking...")
            response = await asyncio.to_thread(
                ollama.chat,
                model=self.bot.model,
                messages=self.conversation_history
            )
            response_content = response['message']['content']
            # Store the bot's response in the database.
            self.db.store_message({'author':self.bot.botname, 'timestamp':datetime.now().isoformat(), 'message': response_content})
            self.conversation_history.append({'role': 'assistant', 'content': response_content})
            if len(response_content) <= 2000:
                await thinking_message.edit(content=response_content)
            else:
                await thinking_message.delete()
                await send_long_message(message.channel, response_content)
        except Exception as e:
            error_message = f"Sorry, an error occurred with the LLM: {e}"
            log.error(error_message)
            await message.channel.send(error_message)

    @commands.command()
    @commands.dm_only()
    async def history(self, ctx: commands.Context):
        """Shows the current conversation history (for debugging)."""
        if not self.conversation_history:
            await ctx.send("History is empty.")
            return
        history_str = "\n".join([f"**{msg['role']}**: {msg['content']}" for msg in self.conversation_history])
        await send_long_message(ctx.channel, f"--- Conversation History ---\n{history_str}")

    @commands.command(name="clearhistory")
    @commands.dm_only()
    async def clear_llm_history(self, ctx: commands.Context):
        """Asks for confirmation before clearing the LLM conversation history."""
        view = ConfirmationView(author=ctx.author, confirm_label="Nuke it!", cancel_label="i don't wanna")
        embed = create_embed(
            title="Confirm Action",
            description="Are you sure you want to permanently clear the conversation history?",
            color=EmbedColors.WARNING
        )
        view.message = await ctx.send(embed=embed, view=view)
        await view.wait()

        if view.value is True:
            self._initialize_history()
            final_embed = create_embed("Success", "Conversation history has been cleared.", EmbedColors.SUCCESS)

        elif view.value is False:
            final_embed = create_embed("Cancelled", "The action was cancelled.", EmbedColors.INFO)
        else:
            final_embed = create_embed("Timed Out", "You did not respond in time.", EmbedColors.ERROR)

        await view.message.edit(embed=final_embed, view=None)

    @commands.command()
    @commands.dm_only()
    async def m(self, ctx: commands.Context, *, message): #Note JN-66 uses m(self, ctx, *, message)
        """Stores the user's thoughts in the musing database"""
        # Add database logic
        self.db.store_musing({'timestamp':datetime.now().isoformat(), 'musing': message})
        await ctx.send("I have stored your thoughts. 💭")

    @commands.command()
    @commands.dm_only()
    async def t(self, ctx: commands.Context, *, message: str):
        """
        Uses an LLM to parse a message into a structured task and stores it.
        """
        try:
            # 1. Acknowledge the request and instantiate the agent.
            processing_embed = create_embed("Processing Task...", "Your request is being analyzed by the AI. Please wait.", EmbedColors.INFO)
            response_message = await ctx.send(embed=processing_embed)
            
            task_agent = TaskAgent(model_name=self.bot.model)

            # 2. Run the blocking LLM call in a separate thread.
            # This prevents the bot from freezing while waiting for the AI.
            task_data = await asyncio.to_thread(task_agent.process_task, message)
            
            # 3. Add bot-managed metadata to the task dictionary.
            task_data['creation_date'] = datetime.now().isoformat()
            task_data['status'] = 'pending' # All new tasks are pending
            task_data['notes'] = f"Original prompt: '{message}'" # Store the original text for context

            # 4. Store the structured task in the database.
            self.db.store_task(task_data)
            log.info(f"Task stored successfully: {task_data['description']}")

            # 5. Create a confirmation embed to show the user what was stored.
            confirm_embed = create_embed(
                title=f"✅ Task Stored: {task_data['description']}",
                description=(
                    f"**Priority:** {task_data['priority']}\n"
                    f"**Due Date:** {task_data['due_date']}"
                ),
                color=EmbedColors.SUCCESS
            )

            # 6. Edit the original "Processing..." message with the final result.
            await response_message.edit(embed=confirm_embed)

        except Exception as e:
            log.error(f"An error occurred in the !t command: {e}", exc_info=True)
            error_embed = create_embed(
                "Error Processing Task",
                f"An unexpected error occurred: {e}\n\nPlease try again.",
                EmbedColors.ERROR
            )
            # Try to edit the original message, or send a new one if that fails
            if 'response_message' in locals():
                await response_message.edit(embed=error_embed)
            else:
                await ctx.send(embed=error_embed)

    async def _build_tasks_response(self) -> tuple[discord.Embed, discord.ui.View | None]:
        """
        An internal helper that fetches tasks and builds the embed and view.
        This contains the core logic shared by the command and the scheduled job.
        
        Returns:
            A tuple containing the (embed, view). The view will be None if there are no tasks.
        """
        today_iso = date.today().isoformat()
        criteria = {'due_date': ('<=', today_iso), 'status': 'pending'}
        tasks_to_show = self.db.fetch_tasks(criteria)

        if not tasks_to_show:
            embed = create_embed("Tasks", "🎉 No pending tasks due today or earlier!", EmbedColors.SUCCESS)
            return embed, None # Return the embed and None for the view

        # Flag and sort tasks
        today = date.today()
        for task in tasks_to_show:
            task['is_overdue'] = date.fromisoformat(task['due_date']) < today
            
        priority_map = {'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        tasks_to_show.sort(key=lambda x: (x['due_date'], priority_map.get(x['priority'], 4)))

        # Build the response components
        embed = create_embed(
            "Pending & Overdue Tasks",
            "Here are your tasks. Click a task to mark it as complete. **Overdue tasks are in ALL CAPS.**",
            EmbedColors.INFO
        )
        view = TaskView(tasks=tasks_to_show, db_manager=self.db)
        
        return embed, view

    @commands.command()
    @commands.dm_only()
    async def tasks(self, ctx: commands.Context):
        """
        Fetches and displays pending tasks as interactive buttons.
        """
        try:
            embed, view = await self._build_tasks_response()
            await ctx.send(embed=embed, view=view)
        except Exception as e:
            log.error(f"An error occurred in the !tasks command: {e}", exc_info=True)
            error_embed = create_embed("Error", f"An unexpected error occurred while fetching tasks: {e}", EmbedColors.ERROR)
            await ctx.send(embed=error_embed)

    async def scheduled_tasks_task(self, target: discord.User):
        """A special version of the 'tasks' command designed for the scheduler."""
        log.info(f"Running scheduled 'tasks' job for {target.name}")
        try:
            embed, view = await self._build_tasks_response()
            await target.send(embed=embed, view=view)
        except Exception as e:
            log.error(f"Error in scheduled 'tasks' job: {e}", exc_info=True)
            await target.send(embed=create_embed("Error", "Sorry, an error occurred while fetching your daily tasks.", EmbedColors.ERROR))

# This async function is required for the cog to be loaded.
async def setup(bot: commands.Bot):
    await bot.add_cog(LLMCog(bot))
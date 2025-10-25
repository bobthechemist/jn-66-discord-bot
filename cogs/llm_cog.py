# cogs/llm_cog.py
import discord
from discord.ext import commands
import ollama
import logging
import asyncio
import re
import requests
import base64
import io
from datetime import datetime, date, time, timezone

from utils.discord_helpers import send_long_message
from utils.ui_helpers import create_embed, ConfirmationView, EmbedColors
from utils.database_manager import DatabaseManager
from utils.task_agent import Agent as TaskAgent
from utils.ui_helpers import TaskView
from utils.scheduler import Job

log = logging.getLogger(__name__)

class LLMCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # --- NEW: Configuration for the agent ---
        # These will be loaded from bot_config.json via the main bot script
        self.conversation_model = getattr(self.bot, 'conversation_model', 'gemma2:2b')
        self.coder_model = getattr(self.bot, 'coder_model', 'qwen2.5-coder:1.5b')
        self.sandbox_url = getattr(self.bot, 'sandbox_url', 'http://localhost:5000/execute')
        
        # Each cog instance will have its own conversation history
        self.conversation_history = []
        self._initialize_history()
        
        self.db = DatabaseManager(bot.db_filename)
        self.setup_scheduled_jobs()

    def _initialize_history(self):
        """Clears the history and adds the initial system prompt for the agent."""
        self.conversation_history.clear()
        
        # --- NEW: Agentic System Prompt ---
        # This prompt teaches the LLM how to use its new code execution tool.
        system_prompt = f"""
        You are {self.bot.botname}, a helpful assistant speaking with {self.bot.username}.
        You have access to a tool that can execute Python code in a secure sandbox.

        When you need to perform a calculation, generate a plot, or access information via code, you MUST respond with the special tag [TOOL_USE] followed by a clear, one-sentence prompt for a specialist code generation model.

        Example 1:
        User: What is the square root of 256?
        You: To answer that, I will calculate the square root of 256. [TOOL_USE] Generate Python code to calculate and print the square root of 256.

        Example 2:
        User: Plot the sine and cosine functions on the same graph.
        You: I will generate a plot of both functions. [TOOL_USE] Generate Python code to plot sin(x) and cos(x) from -2*pi to 2*pi on the same graph, with a legend.

        Do not write the code yourself. Only provide the [TOOL_USE] tag and the prompt for the coder model. If the user is just chatting, respond normally without using the tool.
        """
        self.conversation_history.append({'role': 'system', 'content': system_prompt})
        log.info("LLM conversation history initialized with agentic prompt.")

    def setup_scheduled_jobs(self):
        """Initializes and adds all scheduled jobs for this cog."""
        task_job = Job(
            callback=self.scheduled_tasks_task,
            target_id=self.bot.authorized_user_id,
            target_type='dm',
            target_time=time(10, 30, tzinfo=timezone.utc),
            hours=24
        )
        self.bot.scheduler.add_job(task_job)

    # --- NEW: Helper method to extract code ---
    def _extract_python_code(self, text: str) -> str:
        """Extracts Python code from markdown code blocks."""
        match = re.search(r'```python\s*([\s\S]+?)\s*```', text)
        if match: return match.group(1).strip()
        match = re.search(r'```\s*([\s\S]+?)\s*```', text)
        if match: return match.group(1).strip()
        # As a fallback, if no markdown is present, assume the whole response is code.
        return text.strip()

    # --- NEW: Helper method to run code in the sandbox ---
    async def _execute_code_in_sandbox(self, code_string: str):
        """Sends code to the Docker sandbox and returns the result."""
        log.info("Executing code in sandbox...")
        try:
            # requests is a blocking library, so we run it in a separate thread
            # to avoid freezing the entire bot.
            response = await asyncio.to_thread(
                requests.post,
                self.sandbox_url,
                json={"code": code_string},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            log.error(f"API Error connecting to sandbox: {e}")
            return {"stdout": "", "stderr": f"API Error: Could not connect to the sandbox.\n{e}", "image_b64": None}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """The listener for messages, now with agentic tool-use logic."""
        if (message.author.bot or
            not isinstance(message.channel, discord.DMChannel) or
            message.author.id != self.bot.authorized_user_id or
            message.content.startswith(self.bot.command_prefix)):
            return

        thinking_message = await message.channel.send("🤔 Thinking...")
        
        try:
            # Add user message to history and DB
            self.conversation_history.append({'role': 'user', 'content': message.content})
            self.db.store_message({'author': self.bot.username, 'timestamp': datetime.now().isoformat(), 'message': message.content})

            # === REASONING STEP ===
            # Ask the conversational LLM what to do.
            response = await asyncio.to_thread(
                ollama.chat, model=self.conversation_model, messages=self.conversation_history
            )
            assistant_response = response['message']['content']

            # === DECISION STEP: Check for tool use ===
            if "[TOOL_USE]" not in assistant_response:
                # No tool needed, just a normal chat response
                self.conversation_history.append({'role': 'assistant', 'content': assistant_response})
                self.db.store_message({'author': self.bot.botname, 'timestamp': datetime.now().isoformat(), 'message': assistant_response})
                await thinking_message.edit(content=assistant_response)
                return

            # === TOOL USE PATH ===
            log.info("LLM decided to use the code execution tool.")
            await thinking_message.edit(content="✅ Decision: Use Code Execution Tool. Generating code...")
            
            # 1. Generate Code
            code_prompt = assistant_response.split("[TOOL_USE]")[-1].strip()
            coder_response = await asyncio.to_thread(
                ollama.chat,
                model=self.coder_model,
                messages=[{'role': 'user', 'content': f'Generate only the Python code for this prompt, without any explanation: {code_prompt}'}]
            )
            generated_code = self._extract_python_code(coder_response['message']['content'])
            
            # 2. Execute Code (with error-correction loop)
            max_retries = 2
            for i in range(max_retries):
                await thinking_message.edit(content=f"⚙️ Attempt {i+1}: Executing generated code...")
                execution_result = await self._execute_code_in_sandbox(generated_code)

                if not execution_result['stderr']:
                    log.info("Code executed successfully.")
                    break  # Success!

                log.warning(f"Code execution failed. Stderr: {execution_result['stderr']}")
                if i < max_retries - 1:
                    await thinking_message.edit(content=f"⚠️ Code failed. Attempting to fix (Attempt {i+2})...")
                    correction_prompt = f"The following Python code failed with an error. Please fix it and provide only the complete, corrected script.\n\nCODE:\n{generated_code}\n\nERROR:\n{execution_result['stderr']}"
                    coder_response = await asyncio.to_thread(
                        ollama.chat, model=self.coder_model, messages=[{'role': 'user', 'content': correction_prompt}]
                    )
                    generated_code = self._extract_python_code(coder_response['message']['content'])
                else:
                    log.error("Max retries reached. Could not fix the code.")
            
            # 3. Summarize Result
            await thinking_message.edit(content="📝 Summarizing results...")
            tool_output = f"[TOOL_RESULT]\nSTDOUT:\n{execution_result['stdout']}\nSTDERR:\n{execution_result['stderr']}"
            
            # Update history for the final summary
            self.conversation_history.append({'role': 'assistant', 'content': assistant_response})
            self.conversation_history.append({'role': 'tool', 'content': tool_output})
            
            summarizer_prompt = f"""A user has prompted you with a question and you used a tool to answer it. The tool returns textual answers in STDOUT
                and any errors in STDERR. Based on the tool's output, provide a concise, natural language answer to my original question.\n
                [ORIGINAL_QUESTION]{message.content}
                {tool_output}"
                """
            #self.conversation_history.append({'role': 'user', 'content': summarizer_prompt})
            
            final_response = await asyncio.to_thread(
                ollama.chat, model=self.conversation_model, messages=[{'role':'user', 'content':summarizer_prompt}]
            )
            final_message = final_response['message']['content']
            
            # 4. Send Final Response to Discord
            self.conversation_history.append({'role': 'assistant', 'content': final_message})
            self.db.store_message({'author': self.bot.botname, 'timestamp': datetime.now().isoformat(), 'message': f"[Agent Output]\n{final_message}"})

            # Prepare file if an image was created
            discord_file = None
            if execution_result.get('image_b64'):
                log.info("Image data found in sandbox response.")
                image_data = base64.b64decode(execution_result['image_b64'])
                image_buffer = io.BytesIO(image_data)
                discord_file = discord.File(image_buffer, filename="result.png")

            if discord_file:
                await thinking_message.edit(content=final_message, attachments=[discord_file])
            else:
                await thinking_message.edit(content=final_message)

        except Exception as e:
            error_message = f"Sorry, a critical error occurred in the agentic loop: {e}"
            log.error(error_message, exc_info=True)
            await thinking_message.edit(content=error_message)


    # --- ALL OTHER COMMANDS (!history, !m, !t, !tasks) remain unchanged ---
    # [ ... The rest of your existing commands go here ... ]
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
            processing_embed = create_embed("Processing Task...", "Your request is being analyzed. Please wait.", EmbedColors.INFO)
            response_message = await ctx.send(embed=processing_embed)
            
            # --- The task_agent now uses the improved version ---
            task_agent = TaskAgent(model_name=self.bot.model)
            task_data = await asyncio.to_thread(task_agent.process_task, message)
            
            task_data['creation_date'] = datetime.now().isoformat()
            task_data['status'] = 'pending'
            task_data['notes'] = f"Original prompt: '{message}'"

            # --- MODIFIED: Store the task and get its ID back ---
            task_id = self.db.store_task(task_data)
            log.info(f"Task stored successfully (ID: {task_id}): {task_data['description']}")

            # --- MODIFIED: Create a confirmation embed that includes the Task ID ---
            confirm_embed = create_embed(
                # Title now includes the task ID
                title=f"✅ Task Stored (ID: {task_id})",
                description=(
                    f"**Description:** {task_data['description']}\n"
                    f"**Priority:** {task_data['priority']}\n"
                    f"**Due Date:** {task_data['due_date']}"
                ),
                color=EmbedColors.SUCCESS,

            )

            await response_message.edit(embed=confirm_embed)

        except Exception as e:
            log.error(f"An error occurred in the !t command: {e}", exc_info=True)
            error_embed = create_embed(
                "Error Processing Task",
                f"An unexpected error occurred: {e}\n\nPlease try again.",
                EmbedColors.ERROR
            )
            if 'response_message' in locals():
                await response_message.edit(embed=error_embed)
            else:
                await ctx.send(embed=error_embed)

    @commands.command(name="edit")
    @commands.dm_only()
    async def edit_task(self, ctx: commands.Context, task_id: int, *, new_description: str):
        """
        Edits the description of an existing task.
        Usage: !edit <task_id> <new_description>
        """
        try:
            # Check if the task exists first
            existing_task = self.db.fetch_tasks(criteria={'task_id': task_id})
            if not existing_task:
                embed = create_embed("Error", f"No task found with ID `{task_id}`.", EmbedColors.ERROR)
                await ctx.send(embed=embed)
                return

            # Update the task in the database
            updates = {'description': new_description}
            self.db.update_task(task_id, updates)
            log.info(f"Task {task_id} description updated to: '{new_description}'")

            # Send a confirmation message
            embed = create_embed(
                "Task Updated",
                f"Successfully updated the description for Task ID `{task_id}`.",
                EmbedColors.SUCCESS
            )
            await ctx.send(embed=embed)

        except ValueError:
            await ctx.send("Invalid Task ID. Please provide a number.")
        except Exception as e:
            log.error(f"Error in !edit command: {e}", exc_info=True)
            error_embed = create_embed("Error", f"An unexpected error occurred: {e}", EmbedColors.ERROR)
            await ctx.send(embed=error_embed)
            
    @commands.command(name="delete")
    @commands.dm_only()
    async def delete_task(self, ctx: commands.Context, task_id: int):
        """
        Deletes a task after asking for confirmation
        """
        view = ConfirmationView(author=ctx.author, confirm_label="Delete task", cancel_label="Keep task")
        embed = create_embed(
            title="Confirm task deletion",
            description="Are you sure you want to delete this task?",
            color=EmbedColors.WARNING
        )
        view.message = await ctx.send(embed=embed, view=view)
        await view.wait()

        if view.value is True:
            self.db.delete_task(task_id=task_id)
            final_embed = create_embed("Success", "Task has been removed.", EmbedColors.SUCCESS)
        elif view.value is False:
            final_embed = create_embed("Cancelled", "Not deleting the task", EmbedColors.INFO)
        else:
            final_embed = create_embed("Timed Out", "You did not respond in time.", EmbedColors.ERROR)

        await view.message.edit(embed=final_embed, view=None)

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

    @commands.command(name="view")
    @commands.dm_only()
    async def view_task(self, ctx: commands.Context, task_id: int):
        """Displays all details for a specific task."""
        try:
            task = self.db.fetch_tasks(criteria={'task_id': task_id})
            if not task:
                embed = create_embed("Error", f"No task found with ID `{task_id}`.", EmbedColors.ERROR)
                await ctx.send(embed=embed)
                return

            task_details = task[0] # fetch_tasks returns a list
            
            # Safely format the creation date
            creation_date_str = task_details.get('creation_date', 'N/A')
            if 'T' in creation_date_str:
                creation_date_str = creation_date_str.split('T')[0]

            description = (
                f"**Description:** {task_details.get('description', 'N/A')}\n"
                f"**Status:** {task_details.get('status', 'N/A').capitalize()}\n"
                f"**Priority:** {task_details.get('priority', 'N/A')}\n"
                f"**Due Date:** {task_details.get('due_date', 'N/A')}\n"
                f"**Created On:** {creation_date_str}\n"
                f"**Completed On:** {task_details.get('date_completed') or 'Not completed'}\n"
                f"**Notes:** {task_details.get('notes') or 'None'}\n"
            )

            embed = create_embed(
                title=f"📋 Task Details (ID: {task_id})",
                description=description,
                color=EmbedColors.INFO
            )
            await ctx.send(embed=embed)

        except ValueError:
            await ctx.send("Invalid Task ID. Please provide a number.")
        except Exception as e:
            log.error(f"Error in !view command: {e}", exc_info=True)
            error_embed = create_embed("Error", f"An unexpected error occurred: {e}", EmbedColors.ERROR)
            await ctx.send(embed=error_embed)

    @commands.command(name="edit")
    @commands.dm_only()
    async def edit_task(self, ctx: commands.Context, task_id: int, *, updates: str):
        """
        Edits one or more fields of an existing task.
        Usage: !edit <task_id> field1:value1, field2:value2
        """
        try:
            # Check if the task exists first
            existing_task = self.db.fetch_tasks(criteria={'task_id': task_id})
            if not existing_task:
                embed = create_embed("Error", f"No task found with ID `{task_id}`.", EmbedColors.ERROR)
                await ctx.send(embed=embed)
                return

            # Parse the updates string
            update_dict = {}
            valid_fields = ['description', 'priority', 'due_date', 'status', 'notes', 'estimated_time', 'actual_time', 'date_completed']
            
            try:
                pairs = [pair.strip() for pair in updates.split(',')]
                for pair in pairs:
                    if ':' not in pair:
                        raise ValueError(f"Invalid format for '{pair}'. Expected 'field:value'.")
                    key, value = pair.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if key not in valid_fields:
                        await ctx.send(embed=create_embed("Error", f"Invalid field: `{key}`. You can only edit: {', '.join(valid_fields)}", EmbedColors.ERROR))
                        return
                    # Allow setting a field to empty
                    if value.lower() in ['none', 'null', '']:
                        update_dict[key] = None
                    else:
                        update_dict[key] = value
            except ValueError as ve:
                 await ctx.send(embed=create_embed("Error", f"Could not parse your updates. {ve}", EmbedColors.ERROR))
                 return

            if not update_dict:
                await ctx.send(embed=create_embed("Error", "No valid updates were provided.", EmbedColors.ERROR))
                return

            # Update the task in the database
            self.db.update_task(task_id, update_dict)
            log.info(f"Task {task_id} updated with: {update_dict}")

            # Send a confirmation message
            updated_fields_str = "\n".join([f"**{key.capitalize()}:** {value}" for key, value in update_dict.items()])
            embed = create_embed(
                "✅ Task Updated",
                f"Successfully updated Task ID `{task_id}` with the following changes:\n{updated_fields_str}",
                EmbedColors.SUCCESS
            )
            await ctx.send(embed=embed)

        except ValueError:
            await ctx.send("Invalid Task ID. Please provide a number.")
        except Exception as e:
            log.error(f"Error in !edit command: {e}", exc_info=True)
            error_embed = create_embed("Error", f"An unexpected error occurred: {e}", EmbedColors.ERROR)
            await ctx.send(embed=error_embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(LLMCog(bot))
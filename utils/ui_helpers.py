# utils/ui_helpers.py
import discord
import logging
from datetime import date
from typing import List, Dict, TYPE_CHECKING

# This is a common pattern to allow type hinting for a class that would cause a circular import.
if TYPE_CHECKING:
    from .database_manager import DatabaseManager

log = logging.getLogger(__name__)

# Define standard colors for consistency across the bot's embeds
class EmbedColors:
    SUCCESS = 0x4CAF50  # Green
    ERROR = 0xF44336    # Red
    INFO = 0x2196F3     # Blue
    WARNING = 0xFFC107   # Amber

def create_embed(title: str, description: str = "", color: int = EmbedColors.INFO) -> discord.Embed:
    """
    Creates a standardized Discord embed.
    Args:
        title: The title of the embed.
        description: The main text of the embed.
        color: The color of the left-side border of the embed.
    Returns:
        A discord.Embed object ready to be sent.
    """
    embed = discord.Embed(title=title, description=description, color=color)
    # You could add a standard footer to all embeds here, for example:
    #embed.set_footer(text="Brought to you by BTc bot")
    return embed

class ConfirmationView(discord.ui.View):
    """
    A view that adds 'Confirm' and 'Cancel' buttons to a message.
    The view returns `True` if 'Confirm' is pressed, `False` if 'Cancel' is pressed,
    and `None` if the interaction times out.
    """
    def __init__(self, author: discord.User, timeout: int = 60, confirm_label: str = "Confirm", cancel_label: str = "Cancel"):
        super().__init__(timeout=timeout)
        self.value = None
        self.author = author
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label
        self.confirm.label = confirm_label
        self.cancel.label = cancel_label

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This isn't for you!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        # We only need to edit the message on timeout now
        if self.message:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Callback for the 'Confirm' button."""
        # Defer the response, telling Discord "I'll update this later."
        await interaction.response.defer()
        
        # Now set the value and stop the view. The command will handle the rest.
        self.value = True
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Callback for the 'Cancel' button."""
        # Defer the response, telling Discord "I'll update this later."
        await interaction.response.defer()
        
        # Now set the value and stop the view. The command will handle the rest.
        self.value = False
        self.stop()

class TaskButton(discord.ui.Button):
    """A button that represents a single task. When clicked, it marks the task as complete."""
    
    def __init__(self, task: Dict, db_manager: 'DatabaseManager'):
        """
        Args:
            task: The task dictionary from the database.
            db_manager: An instance of the DatabaseManager to perform the update.
        """
        label_text = task['description'].upper() if task.get('is_overdue', False) else task['description']
        # Discord button labels have an 80-character limit.
        super().__init__(label=label_text[:80], style=discord.ButtonStyle.primary, custom_id=f"task_{task['task_id']}")
        self.task_id = task['task_id']
        self.task_description = task['description']
        self.db_manager = db_manager

    async def callback(self, interaction: discord.Interaction):
        """This function is called when a user clicks the button."""
        try:
            # 1. Update the database record.
            today_iso = date.today().isoformat()
            updates = {'status': 'completed', 'date_completed': today_iso}
            self.db_manager.update_task(self.task_id, updates)

            # 2. Provide visual feedback by disabling the button and changing its look.
            self.disabled = True
            self.style = discord.ButtonStyle.success
            self.label = "✓ " + self.label # Add a checkmark
            
            # 3. Edit the original message to show the updated view (with the disabled button).
            await interaction.response.edit_message(view=self.view)
            
            # 4. Send a quiet, ephemeral confirmation to the user who clicked.
            await interaction.followup.send(f'Task "{self.task_description}" marked as completed!', ephemeral=True)
            log.info(f"Task ID {self.task_id} marked as complete by {interaction.user.name}.")

        except Exception as e:
            log.error(f"Error in TaskButton callback for task {self.task_id}: {e}", exc_info=True)
            await interaction.followup.send("Sorry, there was an error completing that task.", ephemeral=True)


class TaskView(discord.ui.View):
    """A view that displays a list of tasks as clickable buttons."""
    
    def __init__(self, tasks: List[Dict], db_manager: 'DatabaseManager'):
        super().__init__(timeout=None) # Set a long or no timeout
        
        # For each pending task, create and add a button to the view.
        for task in tasks:
            if task['status'] == 'pending':
                self.add_item(TaskButton(task, db_manager))
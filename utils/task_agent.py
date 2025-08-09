# utils/task_agent.py

from ollama import chat
from pydantic import BaseModel, Field
from datetime import datetime
import parsedatetime as pdt
import logging

log = logging.getLogger(__name__)

# The calendar object for parsing dates
cal = pdt.Calendar()

class Task(BaseModel):
    description: str = Field(..., description="A concise description of the task to be done.")
    priority: str = Field(..., description="The priority of the task, must be one of: LOW, MEDIUM, HIGH.")
    due: str = Field(..., description="The natural language phrase indicating the due date (e.g., 'tomorrow', 'next Friday', 'August 15th').")

    # This property intelligently converts the 'due' string into a standard YYYY-MM-DD format.
    @property
    def due_date(self) -> str:
        """Parses the 'due' field and returns an ISO format date string."""
        time_struct, parse_status = cal.parse(self.due)
        if parse_status != 0:
            # If parsing is successful, return the date part in ISO format
            return datetime(*time_struct[:6]).date().isoformat()
        else:
            # If parsing fails (e.g., no date found), default to today
            return datetime.now().date().isoformat()

class Agent:
    def __init__(self, model_name='gemma2:2b'):
        self.model_name = model_name

    def process_task(self, prompt: str) -> dict:
        """
        Uses an LLM to process a natural language prompt into a structured task.
        Returns a dictionary with description, priority, and a standardized due_date.
        """
        system_prompt = """
        You are a task management assistant. Your job is to analyze the user's request and extract key details for creating a task.
        From the user's prompt, you must extract three pieces of information:
        1.  `description`: A concise summary of the actual task to be done. For example, if the user says "I really need to remember to clean the garage this weekend", the description should be "Clean the garage".
        2.  `priority`: Analyze the user's language to determine the task's priority. Choose one of three options: LOW, MEDIUM, or HIGH. Phrases like "don't forget," "it's really important," or "ASAP" indicate a HIGH priority. A standard request is MEDIUM.
        3.  `due`: Extract the exact phrase that indicates the due date. If no date or time is mentioned, use the word "today".
        """
        response = chat(
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt}
            ],
            model=self.model_name,
            # Tell the model to format its output according to our Pydantic model's JSON schema
            format='json',
            options={'temperature': 0.2} # Lower temperature for more deterministic output
        )
        
        # Validate the JSON output from the model against our Task structure
        task_model = Task.model_validate_json(response['message']['content'])

        # Return a clean dictionary using the parsed properties
        return {
            'description': task_model.description,
            'priority': task_model.priority,
            'due_date': task_model.due_date # This calls our @property method
        }

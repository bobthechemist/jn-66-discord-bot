# utils/task_agent.py

from ollama import chat
# --- We'll bring back the more robust validation from before ---
from pydantic import BaseModel, Field, ValidationError, field_validator
from datetime import datetime
import parsedatetime as pdt
import logging

log = logging.getLogger(__name__)
cal = pdt.Calendar()

class Task(BaseModel):
    description: str = Field(..., description="A concise summary of the task to be done.")
    priority: str = Field(..., description="The priority of the task, must be one of: LOW, MEDIUM, HIGH.")
    due: str = Field(..., description="The natural language phrase indicating the due date (e.g., 'tomorrow', 'next Friday', 'August 15th').")

    @field_validator('description')
    def validate_description(cls, value):
        if not value or not value.strip():
            raise ValueError("Task description cannot be empty.")
        return value

    @property
    def due_date(self) -> str:
        time_struct, parse_status = cal.parse(self.due)
        if parse_status != 0:
            return datetime(*time_struct[:6]).date().isoformat()
        else:
            return datetime.now().date().isoformat()

class Agent:
    def __init__(self, model_name='gemma2:2b'):
        self.model_name = model_name

    def process_task(self, prompt: str) -> dict:
        """
        Uses an LLM to process a natural language prompt into a structured task.
        Includes a retry loop to handle validation errors.
        """
        # --- NEW, IMPROVED PROMPT ---
        # This prompt is more direct and avoids overly specific examples that the LLM might latch onto.
        system_prompt = """
        You are a task management assistant. Your job is to analyze a user's request and extract key details into a JSON object.
        From the user's prompt, you must extract three pieces of information:

        1.  `description`: This MUST be a concise summary of the task from the user's prompt. Do NOT make up a task. For example, if the user says "remind me to finish the quarterly report", the description should be "Finish the quarterly report". This field cannot be empty.
        2.  `priority`: Analyze the user's language for urgency. Choose ONLY ONE of: LOW, MEDIUM, or HIGH. Default to MEDIUM if unsure.
        3.  `due`: Extract the part of the prompt that indicates the due date. If no date is mentioned, use the word "today".
        """
        
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': prompt}
        ]

        max_retries = 2
        for i in range(max_retries):
            response = chat(
                messages=messages,
                model=self.model_name,
                format='json',
                options={'temperature': 0.1} # Lowered temperature for more determinism
            )
            response_content = response['message']['content']
            
            try:
                task_model = Task.model_validate_json(response_content)
                return {
                    'description': task_model.description,
                    'priority': task_model.priority,
                    'due_date': task_model.due_date
                }
            except ValidationError as e:
                log.warning(f"Task validation failed on attempt {i + 1}. Error: {e}")
                if i < max_retries - 1:
                    correction_prompt = f"Your previous JSON was invalid. Please correct it based on the user's original prompt.\n\nERRORS:\n{e}\n\nPlease provide only the corrected JSON object."
                    messages.append({'role': 'assistant', 'content': response_content})
                    messages.append({'role': 'user', 'content': correction_prompt})
                else:
                    raise e
        
        raise ValueError("Failed to get a valid task from the LLM after multiple attempts.")
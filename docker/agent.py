# agent.py (with error correction)
import ollama
import requests
import json
import re
import base64
from PIL import Image
import io
import os
import readline

# --- Configuration & Helper Functions (No changes here) ---
CONVERSATION_MODEL = 'gemma2:2b'
CODE_MODEL = 'qwen2.5-coder:1.5b'
SANDBOX_URL = 'http://localhost:5000/execute'

class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_colored(text, color, bold=False):
    bold_code = Colors.BOLD if bold else ""
    print(f"{bold_code}{color}{text}{Colors.END}")

def execute_code_in_sandbox(code_string: str):
    print_colored("\n[Executing code in sandbox...]", Colors.YELLOW)
    try:
        response = requests.post(SANDBOX_URL, json={"code": code_string}, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"stdout": "", "stderr": f"API Error: {e}", "image_b64": None}

def display_image_from_b64(b64_string: str):
    try:
        image_data = base64.b64decode(b64_string)
        image = Image.open(io.BytesIO(image_data))
        image_path = "llm_plot_output.png"
        image.save(image_path)
        print_colored(f"[Image saved to {image_path}]", Colors.GREEN)
        image.show()
    except Exception as e:
        print_colored(f"Could not display image: {e}", Colors.RED)

def extract_python_code(text: str) -> str:
    match = re.search(r'```python\s*([\s\S]+?)\s*```', text)
    if match: return match.group(1).strip()
    match = re.search(r'```\s*([\s\S]+?)\s*```', text)
    if match: return match.group(1).strip()
    return text.strip()

# --- The Agent's "Brain" (UPDATED) ---
def run_agentic_loop(user_prompt, conversation_history):
    conversation_history.append({'role': 'user', 'content': user_prompt})
    
    # === REASONING STEP ===
    print_colored("\n[Thinking...]", Colors.BLUE)
    response = ollama.chat(model=CONVERSATION_MODEL, messages=conversation_history, stream=False)
    assistant_response = response['message']['content']

    if "[TOOL_USE]" in assistant_response:
        print_colored("[Decision: Use Code Execution Tool]", Colors.YELLOW, bold=True)
        
        # --- CODE GENERATION STEP ---
        code_prompt = assistant_response.split("[TOOL_USE]")[-1].strip()
        print_colored(f"Coder Prompt: {code_prompt}", Colors.BLUE)
        
        coder_response = ollama.chat(
            model=CODE_MODEL,
            messages=[{'role': 'user', 'content': f'Generate only the Python code for this prompt, without any explanation: {code_prompt}'}],
            stream=False
        )
        generated_code = extract_python_code(coder_response['message']['content'])
        
        # --- NEW: EXECUTION AND CORRECTION LOOP ---
        max_retries = 2
        for i in range(max_retries):
            print_colored(f"\n--- Attempt {i+1}: Generated Code ---", Colors.GREEN)
            print(generated_code)
            print_colored("---------------------------------", Colors.GREEN)
            
            execution_result = execute_code_in_sandbox(generated_code)
            
            # Check if the code executed successfully
            if not execution_result['stderr']:
                print_colored("[Code executed successfully!]", Colors.GREEN)
                break  # Exit the loop on success
            
            # If there's an error, try to fix it
            print_colored("\n[Code failed with an error. Attempting to fix...]", Colors.RED)
            print_colored("Error Message:\n" + execution_result['stderr'], Colors.RED)
            
            if i < max_retries - 1:
                correction_prompt = f"""
                The following Python code failed:
                --- CODE START ---
                {generated_code}
                --- CODE END ---

                It produced this error:
                --- ERROR START ---
                {execution_result['stderr']}
                --- ERROR END ---

                Please fix the code and provide only the complete, corrected Python script.
                """
                coder_response = ollama.chat(
                    model=CODE_MODEL,
                    messages=[{'role': 'user', 'content': correction_prompt}],
                    stream=False
                )
                generated_code = extract_python_code(coder_response['message']['content'])
            else:
                print_colored("[Max retries reached. Could not fix the code.]", Colors.RED, bold=True)
        
        # --- The rest of the logic proceeds as before ---
        tool_output = f"""
        [TOOL_RESULT]
        STDOUT:
        {execution_result['stdout']}
        STDERR:
        {execution_result['stderr']}
        """
        
        print_colored("\n[Execution Result Fed Back to Thinker]", Colors.YELLOW)
        print(tool_output)

        if execution_result.get('image_b64'):
            display_image_from_b64(execution_result['image_b64'])

        # --- FINAL RESPONSE STEP ---
        conversation_history.append({'role': 'assistant', 'content': assistant_response})
        conversation_history.append({'role': 'tool', 'content': tool_output})
        
        print_colored("\n[Summarizing result...]", Colors.BLUE)
        final_response = ollama.chat(model=CONVERSATION_MODEL, messages=conversation_history, stream=False)
        final_message = final_response['message']['content']
        conversation_history.append({'role': 'assistant', 'content': final_message})
        
        print_colored("\nJN-66:", Colors.GREEN, bold=True)
        print(final_message)

    else:
        # If no tool is needed, just respond normally
        conversation_history.append({'role': 'assistant', 'content': assistant_response})
        print_colored("\nJN-66:", Colors.GREEN, bold=True)
        print(assistant_response)

# --- Main Application Loop (No changes here) ---
if __name__ == "__main__":
    SYSTEM_PROMPT = """
    You are JN-66, a helpful assistant. You have access to a tool that can execute Python code.
    When you need to perform a calculation, generate a plot, or access information via code, you must respond with the special tag [TOOL_USE] followed by a clear, one-sentence prompt for a specialist code generation model.
    Example:
    User: What is the square root of 256?
    You: To answer that, I will calculate the square root of 256. [TOOL_USE] Generate Python code to calculate and print the square root of 256.
    Do not write the code yourself. Only provide the [TOOL_USE] tag and the prompt for the coder model.
    """
    history = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    print_colored("LLM Agent Initialized. Type 'exit' to quit.", Colors.GREEN, bold=True)
    while True:
        try:
            user_input = input(f"\n{Colors.BOLD}> You: {Colors.END}")
            if user_input.lower() in ['exit', 'quit']:
                break
            run_agentic_loop(user_input, history)
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        

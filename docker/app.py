# app.py (with corrected plot handling)
from flask import Flask, request, jsonify
import io
import contextlib
import traceback
import base64

# Import libraries that the LLM might use
import numpy as np
import pandas as pd
import sklearn
import matplotlib.pyplot as plt
import requests
import math # Add math for completeness

app = Flask(__name__)

@app.route("/execute", methods=["POST"])
def execute_code():
    data = request.get_json()
    if not data or "code" not in data:
        return jsonify({"error": "No code provided"}), 400

    code = data["code"]
    
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    image_buffer = io.BytesIO()
    
    try:
        with contextlib.redirect_stdout(stdout_buffer):
            with contextlib.redirect_stderr(stderr_buffer):
                # The 'globals()' dict provides the scope for exec
                exec_scope = globals()
                exec(code, exec_scope)

        # --- THIS IS THE CORRECTED LOGIC ---
        # Heuristic: Check if the code likely generated a plot by seeing if 'plt' or 'matplotlib' was used.
        # This is more reliable than checking for lingering figure numbers.
        if 'plt' in code or 'matplotlib' in code:
            # Check if there are any active figures to save
            if plt.get_fignums():
                # Save the current figure to the image buffer
                plt.savefig(image_buffer, format='png', bbox_inches='tight')
            
            # CRITICAL FIX: Close all figures to prevent them from carrying over to the next request.
            plt.close('all')

    except Exception:
        stderr_buffer.write(traceback.format_exc())
        # Also ensure plots are closed even if an error occurs
        plt.close('all')


    # --- Prepare the JSON response ---
    stdout_val = stdout_buffer.getvalue()
    stderr_val = stderr_buffer.getvalue()
    
    if image_buffer.getbuffer().nbytes > 0:
        image_buffer.seek(0)
        image_b64 = base64.b64encode(image_buffer.read()).decode('utf-8')
    else:
        image_b64 = None

    return jsonify({
        "stdout": stdout_val,
        "stderr": stderr_val,
        "image_b64": image_b64
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
    
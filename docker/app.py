# app.py
from flask import Flask, request, jsonify
import io
import contextlib
import traceback
import base64

# Import libraries that the LLM might use. They need to be here
# so that exec() has access to them in its scope.
import numpy as np
import pandas as pd
import sklearn
import matplotlib.pyplot as plt
import requests

app = Flask(__name__)

@app.route("/execute", methods=["POST"])
def execute_code():
    """Executes Python code and captures output, errors, and plots."""
    data = request.get_json()
    if not data or "code" not in data:
        return jsonify({"error": "No code provided"}), 400

    code = data["code"]
    
    # Create string buffers to capture stdout and stderr
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()

    # Create a buffer to capture plot images
    image_buffer = io.BytesIO()
    
    try:
        # Redirect stdout and stderr to our buffers
        with contextlib.redirect_stdout(stdout_buffer):
            with contextlib.redirect_stderr(stderr_buffer):
                # Use exec to run the code. The 'globals()' dict provides
                # access to the imported libraries like numpy, pandas, etc.
                exec(code, globals())
        
        # After execution, check if a plot was created.
        # If plt.get_fignums() is not empty, it means there's an open figure.
        if plt.get_fignums():
            # Save the current figure to the image buffer in PNG format
            plt.savefig(image_buffer, format='png')
            # Important: Clear the figure so it doesn't appear in the next run
            plt.clf()
        
    except Exception:
        # If an exception occurs during exec, capture it in stderr
        stderr_buffer.write(traceback.format_exc())

    # --- Prepare the JSON response ---
    stdout_val = stdout_buffer.getvalue()
    stderr_val = stderr_buffer.getvalue()
    
    # Check if the image buffer has data
    if image_buffer.getbuffer().nbytes > 0:
        # Reset buffer pointer and encode the image data as a Base64 string
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
    # Run the app on host 0.0.0.0 to make it accessible from outside the container
    app.run(host='0.0.0.0', port=5000)
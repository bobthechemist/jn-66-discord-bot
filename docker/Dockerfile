# Start with an official, lightweight Python image.
FROM python:3.11-slim-bookworm

# --- Security Best Practice: Run as a non-root user ---
RUN groupadd --gid 1001 sandboxgroup && \
    useradd --uid 1001 --gid 1001 -m sandboxuser

# --- Application Setup ---
WORKDIR /app

# Copy the requirements file first.
COPY requirements.txt .

# --- DEBUGGING STEP ---
# List the contents of the /app directory to verify the copy worked.
# The output of this will appear during the 'docker build' process.
RUN ls -l

# Install the Python dependencies using a more robust command.
RUN python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

# Copy the actual application code into the container.
COPY app.py .

# Switch to the non-root user for running the application.
USER sandboxuser

# --- Runtime ---
EXPOSE 5000
CMD ["python3", "-u", "app.py"]


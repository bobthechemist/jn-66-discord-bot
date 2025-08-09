# JN-66: An Intelligent Discord Task Management Bot

![Discord.py](https://img.shields.io/badge/Discord.py-2.3.2-7289DA?style=for-the-badge&logo=discord&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)

JN-66 is a personal assistant and task management "droid" for Discord, inspired by the droids of Star Wars. It operates exclusively through Direct Messages to provide a private, intelligent interface for organizing your life. It leverages a locally hosted Large Language Model (LLM) via Ollama for natural language understanding and integrates with Google Calendar to keep you on schedule.

## Features

*   **🤖 Conversational AI:** Chat directly with the bot in your DMs. Any message that isn't a command is treated as part of an ongoing conversation.
*   **🧠 AI-Powered Task Creation:** Use the `!t` command with a natural phrase (e.g., `!t I need to finish the report by Friday`) and the LLM will automatically extract the task, priority, and due date.
*   **✅ Interactive Task Management:** The `!tasks` command displays your pending and overdue tasks as clickable buttons. Simply click a task to mark it as complete.
*   **📅 Daily Google Calendar Agenda:** Get a daily summary of your events from multiple Google Calendars.
*   **💡 Quick Thought Capture:** Use the `!m` command to quickly save any "musing" or thought that comes to mind.
*   **🔄 LLM Context Control:** View the bot's conversation history with `!history` or wipe its memory for a fresh start with `!clearhistory`.
*   **⏰ Scheduled Notifications:** The bot automatically sends you your daily agenda and task list at a pre-configured time.

## Limitations

*   It is designed for a single user. It is not currently written for multiple users on a server to get a personalized experience. Since this is not a feature that is of interest to me, I won't be spending time implementing it.
*   This project is the result of my exploration of "vibe programming" which means much of the structure is AI generated. While I've gone through the code to understand what was written and done, there may be areas that are still a black box to me.

## Prerequisites

Before you begin, you will need the following:

1.  **Python 3.10+**
2.  **A Discord Bot Application:** Create one on the [Discord Developer Portal](https://discord.com/developers/applications). Your bot will need the `Server Members Intent`, `Message Content Intent`, and `DM Messages Intent` enabled.
3.  **Ollama Instance:** A running instance of [Ollama](https://ollama.com/) on your local machine or network. You must have a model downloaded (e.g., by running `ollama pull gemma2:2b`).
4.  **Google Cloud Platform Project:** A project with the **Google Calendar API** enabled. You can set this up on the [Google Cloud Console](https://console.cloud.google.com/).

## Installation & Configuration

Follow these steps to get your JN-66 instance running.

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/jn-66.git
cd jn-66
```

### 2. Install Dependencies
It is highly recommended to use a Python virtual environment.
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
pip install -r requirements.txt
```

### 3. Configure Google API Credentials
This is the most complex step.
1.  In your Google Cloud Platform project, navigate to "APIs & Services" > "Credentials".
2.  Click "Create Credentials" and select "OAuth client ID".
3.  Choose **"Desktop app"** as the application type.
4.  After creation, a "Download JSON" button will appear. Click it.
5.  Rename the downloaded file to `gcredentials.json` and place it in the root directory of this project.

### 4. Set Up Environment Secrets
Create a file named `.env` in the root directory of the project. This file will hold your secret tokens.
```env
# Your Discord bot's secret token
DISCORD_TOKEN="your_super_secret_discord_bot_token"

# Your own unique Discord User ID
USER_ID="your_discord_user_id"
```

### 5. Set Up Bot Configuration
1.  Find the `bot_config.json.example` file in the repository.
2.  Make a copy of it and rename the copy to `bot_config.json`.
3.  Open `bot_config.json` and customize the values:
    *   `bot_prefix`: The command prefix for the bot (e.g., `!`).
    *   `ollama_model`: The name of the LLM you have downloaded in Ollama (e.g., `gemma2:2b`).
    *   `db_filename`: The name for the bot's SQLite database file.
    *   `log_location`: The path where the log file will be saved.
    *   `calendars_to_check`: A list of the Google Calendars you want the bot to access. Find the calendar ID/email in your Google Calendar settings.

    **Example `calendars_to_check`:**
    ```json
    "calendars_to_check": [
      {
        "summary": "your_personal_email@gmail.com",
        "description": "Personal Calendar"
      },
      {
        "summary": "your_work_email@example.com",
        "description": "Work Calendar"
      }
    ]
    ```

## Running the Bot

### First-Time Run
The very first time you run the bot, you will need to authorize it to access your Google account.
```bash
python jn-66.py
```
A URL will appear in your console. Copy and paste it into your browser, log in to your Google account, and grant the requested permissions. You will be redirected to a localhost page (which may show an error, this is normal). This process creates a `gtoken.json` file in your project directory, which will be used for all future runs.

### Normal Operation
For all subsequent runs, simply start the bot with the same command:
```bash
python jn-66.py
```

### Using a service

Create a `jn-66.service` file using the template below. Save this file as `/etc/systemd/system/jn-66.service`.

```
[Unit]
Description=Intelligent Task Management Bot (JN-66)
After=network.target

[Service]
User=bob
WorkingDirectory=<path-to-project-directory>
ExecStart=<absolute-path-to-venv-python> <path-to-project-directory>/jn-66.py

[Install]
WantedBy=multi-user.target
```

You'll need to run `systemctl daemon-reload` followed by `systemctl enable jn-66` and `systemctl start jn-66` to finish the install.

## Command Reference

| Command             | Description                                                               | Example                                               |
| ------------------- | ------------------------------------------------------------------------- | ----------------------------------------------------- |
| **Task Management** |                                                                           |                                                       |
| `!t <description>`  | Creates a new task. The LLM infers priority and due date.                 | `!t I really need to finish the project by tomorrow`  |
| `!tasks`            | Displays your pending and overdue tasks as interactive buttons.           | `!tasks`                                              |
| `!m <thought>`      | Stores a "musing" or thought in the database.                             | `!m I should learn how to make pasta from scratch.`   |
| **Calendar**        |                                                                           |                                                       |
| `!today`            | Fetches and displays today's events from your configured Google Calendars.| `!today`                                              |
| **LLM & Utility**   |                                                                           |                                                       |
| `!history`          | Shows the current LLM conversation history.                               | `!history`                                            |
| `!clearhistory`     | Asks for confirmation before clearing the LLM's memory.                   | `!clearhistory`                                       |
| `!ping`             | Checks the bot's latency to Discord's servers.                            | `!ping`                                               |
| **Admin Commands**  | *(Bot owner only)*                                                        |                                                       |
| `!reload <cog>`     | Reloads a specified cog (e.g., `llm_cog`).                                | `!reload admin_cog`                                   |
| `!load <cog>`       | Loads a cog.                                                              | `!load utils_cog`                                     |
| `!unload <cog>`     | Unloads a cog.                                                            | `!unload calendar_cog`                                |

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
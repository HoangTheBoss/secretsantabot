# ⚙️ Setup & Deployment Guide

This guide walks you through setting up the Discord Application, configuring permissions and environment variables, and running the bot locally or on a server.

---

## 1. Discord Developer Portal Setup

### Step 1: Create Application
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** (top right) and name it (e.g., `Buda Secret Santa`).
3. (Optional) Upload an icon (e.g., Santa hat or gift box).

### Step 2: Configure Bot & Privileged Intents
1. Navigate to the **Bot** tab on the left sidebar.
2. Under **Token**, click **Reset Token** to generate your bot token. Copy this securely (you will need it for `.env`).
3. Scroll down to **Privileged Gateway Intents**:
   - Enable **Server Members Intent** (required to check member status and send DMs).
   - Enable **Message Content Intent** (optional/recommended for prefix commands or relay monitoring).
4. Save Changes.

### Step 3: Invite Bot to Your Discord Server
1. Navigate to **OAuth2** ➡️ **URL Generator**.
2. Under **Scopes**, select:
   - `bot`
   - `applications.commands` (for Slash Commands)
3. Under **Bot Permissions**, select:
   - `Send Messages`
   - `Embed Links`
   - `Attach Files`
   - `Read Message History`
   - `Use External Emojis`
   - `Add Reactions`
4. Copy the generated URL at the bottom, paste it into your browser, select your private Discord server, and click **Authorize**.

---

## 2. Server Configuration & Finding IDs

To bind the bot to your private setup, you will need Discord developer IDs:

1. In your Discord client, open **User Settings** ➡️ **Advanced** ➡️ enable **Developer Mode**.
2. **Guild ID:** Right-click your server icon ➡️ **Copy Server ID**.
3. **Channel ID:** Right-click your dedicated Secret Santa text channel (e.g. `#secret-santa`) ➡️ **Copy Channel ID**.
4. **Admin Role ID:** Open Server Settings ➡️ Roles ➡️ Right-click your Admin/Organizer role ➡️ **Copy Role ID**.

---

## 3. Local Environment Setup

### Prerequisites
- **Python 3.11+** (Tested on Python 3.13)
- `pip` and virtual environment support (`venv`)

### Installation Steps

```bash
# Clone the repository
git clone <your-repo-url>
cd budasecretsanta

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration (`.env`)

Copy the template file:
```bash
cp .env.example .env
```

Edit `.env` with your values:
```env
# Discord Bot Credentials
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=123456789012345678
SANTA_CHANNEL_ID=123456789012345678
SANTA_ADMIN_ROLE_ID=123456789012345678

# Database Path (defaults to local sqlite file)
DATABASE_PATH=data/secretsanta.db

# Logging Level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Branding & Appearance Defaults (Optional)
DEFAULT_EVENT_NAME=Buda Secret Santa
DEFAULT_LOGO_URL=https://example.com/logo.png
DEFAULT_BANNER_URL=https://example.com/banner.png
DEFAULT_FOOTER_TEXT=Buda Secret Santa • Ho Ho Ho!
DEFAULT_THEME_COLOR=RED
```

---

## 4. Running the Bot

```bash
python3 run.py
```

When started, the bot will:
1. Connect to Discord and log in as your bot application.
2. Initialize and migrate the SQLite database in `data/secretsanta.db`.
3. Sync slash commands with your private server (`GUILD_ID`) instantly (guild-scoped sync takes seconds, unlike global sync which can take up to an hour).
4. Verify channel binding and print readiness logs.

---

## 5. Deployment Options (Self-Hosting for Small Groups)

Since this bot is for private friend groups:
- **Local Machine:** Run on your laptop or home machine during the event weeks. SQLite will retain state between launches.
- **Raspberry Pi / Home Server:** Run as a `systemd` service or tmux session.
- **Free/Cheap Cloud VPS (Fly.io, Railway, DigitalOcean):** Mount a persistent volume for `data/secretsanta.db` and run as a lightweight Python container.

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

## 3. Installation & Setup

### Option A: Debian & Debian-Based Systems (Debian, Ubuntu, Mint, Raspberry Pi OS)

Run the automated installer:
```bash
# Clone the repository
git clone <your-repo-url>
cd budasecretsanta

# Run automated Debian setup
# (Updates apt, installs python3-venv, pip, build tools, sets up .venv and requirements)
./setup.sh
```

### Option B: Manual Setup (Any OS)

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

Copy the template file (done automatically by `./setup.sh`):
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

# Branding & Appearance (Optional)
EVENT_NAME=Buda Secret Santa 2026
THEME_COLOR=RED
FOOTER_TEXT=Buda Secret Santa • Ho Ho Ho! 🎄
LOGO_FILENAME=logo.png
BANNER_FILENAME=banner.png

# Built-in Asset Server & Reverse Proxy
HTTP_SERVER_ENABLED=true
HTTP_HOST=0.0.0.0
HTTP_PORT=8080
PUBLIC_HOSTNAME=santa.yourdomain.com
PUBLIC_URL=https://santa.yourdomain.com
```

### Reverse Proxy Example (Nginx)

When deploying behind Nginx or Caddy with TLS:

```nginx
server {
    server_name santa.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 4. Running the Bot

### Quick Start
```bash
./start.sh
# Or manually with activated venv: python3 run.py
```

When started, the bot will:
1. Connect to Discord and log in as your bot application.
2. Checkpoint and migrate SQLite database in `data/secretsanta.db` with WAL mode enabled.
3. Automatically take a hot restore backup in `data/backups/`.
4. Register and recover persistent interactive views (Santa DMs, wishlists, registration cards).
5. Sync slash commands with your private server (`GUILD_ID`) instantly.

---

## 5. 24/7 Production Deployment on Debian / Ubuntu (Systemd)

To run the bot as a background service that automatically restarts on system reboot or crash:

```bash
# Install and enable the systemd service
./scripts/install_service.sh
```

### Systemd Management Commands

| Action | Command |
|---|---|
| **View Live Logs** | `journalctl -u budasecretsanta -f` |
| **Check Status** | `sudo systemctl status budasecretsanta` |
| **Restart Bot** | `sudo systemctl restart budasecretsanta` |
| **Stop Bot** | `sudo systemctl stop budasecretsanta` |
| **Start Bot** | `sudo systemctl start budasecretsanta` |

# 🎅 Buda Secret Santa Discord Bot

An automated Discord bot tailored for managing private **Secret Santa** gift exchanges **leading up to an in-person (offline) party**.

The bot handles all the digital logistics (polling, registration, matching, secret wishlists, anonymous Q&A, and gift preparation tracking), leaving the actual party, unboxing, and reveals to be enjoyed **100% manually and in person**.

Built with **Python 3.13+**, **`discord.py`**, and **`aiosqlite`**.

---

## 🎯 Bot Scope & Philosophy

- **Digital Coordination, Human Gathering:** Automate everything leading up to the party date so organizers don't have to juggle spreadsheets or draw paper slips. Once everyone arrives at the party with wrapped gifts in hand, the group puts phones away and enjoys the unboxing in person!
- **Channel Hub:** Bound to a single dedicated `#secret-santa` channel for announcements, polls, and live countdowns.
- **Strict DM Secrecy:** Pairs, wishlists, and gift tag instructions are delivered strictly via private DMs.
- **Routine Updates & Reminders:**
  - **Public Channel Updates:** Scheduled periodic countdown & prep dashboard updates in `#secret-santa`.
  - **Private DM Nudges:** Targeted reminder DMs sent only to Santas who haven't marked their gift as wrapped, complete with action buttons (`[Mark as Wrapped 🎁]`, `[Ask Baby Anonymously ✉️]`).
  - **On-Demand Reminders:** Host slash commands (`/remind channel`, `/remind dms`, `/remind user`) to broadcast nudges with custom notes at any time.
- **Anonymous Q&A Relay:** Santas can anonymously ask their baby clarifying questions via the bot without spoiling their identity.

- **Preparation Tracking:** Public spoiler-free progress meter (e.g. *"7/9 Santas have wrapped their gifts and are ready for the party!"*).
- **Host Backup Sheet:** A private command for the host to export or inspect pairings in case someone forgets who they got.

---

## 🧭 Documentation Index

- 📋 [**System Specification (`docs/SPECIFICATION.md`)**](docs/SPECIFICATION.md): Data schema, lifecycle states, matching algorithm, and command reference.
- 🥂 [**Offline Party Playbook (`docs/OFFLINE_PARTY_PLAYBOOK.md`)**](docs/OFFLINE_PARTY_PLAYBOOK.md): Organizer timeline and physical party guidelines (gift labeling, placement, and manual in-person reveal ideas).
- ⚙️ [**Setup & Deployment Guide (`docs/SETUP_GUIDE.md`)**](docs/SETUP_GUIDE.md): Discord Developer Portal, bot permissions, environment configuration, and running the bot.

---

## ⚡ Quick Start Overview

```bash
# 1. Clone repository & enter directory
git clone <repo-url>
cd budasecretsanta

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your DISCORD_TOKEN, GUILD_ID, and SANTA_CHANNEL_ID

# 5. Run the bot
python3 run.py
```

---

## 🎮 Lifecycle Overview

```
[1. Channel Setup] ➡️ [2. Date / Budget Polling] ➡️ [3. Registration & Modals]
                                                            ⬇️
[Hand over to Party!] ⬅️ [5. Anonymous Q&A & Tracking] ⬅️ [4. Constrained Draw & DM Dispatch]
```

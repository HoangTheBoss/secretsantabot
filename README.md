# 🎅 Buda Secret Santa Discord Bot

An automated Discord bot tailored for managing private **Secret Santa** gift exchanges **leading up to an in-person (offline) party**.

The bot handles all the digital logistics (polling, registration, matching, secret wishlists, anonymous Q&A, and gift preparation tracking), leaving the actual party, unboxing, and reveals to be enjoyed **100% manually and in person**.

Built with **Python 3.13+**, **`discord.py`**, and **`aiosqlite`**.

---

## 🎯 Bot Scope & Philosophy

- **Digital Coordination, Human Gathering:** Automate everything leading up to the party date so organizers don't have to juggle spreadsheets or draw paper slips. Once everyone arrives at the party with wrapped gifts in hand, the group puts phones away and enjoys the unboxing in person!
- **UI-First & Modal-Driven Workflow:**
  - **Interactive Modals:** Clean pop-up forms for setup (`/secretsanta setup`), poll creation (`/secretsanta poll`), deadlines (`/secretsanta set_deadline`), and wishlists.
  - **Native Member Pickers:** Visual `UserSelect` dropdown to select couple/roommate exclusions with zero typing.
  - **All-in-One Control Panel (`/secretsanta panel`):** Interactive master control board with buttons to manage settings, polls, deadlines, exclusions, reminders, and draws without memorizing commands.
  - **Interactive Status Dashboard:** `/my_status` includes a 1-click `[Edit Wishlist 📝]` button.
- **Channel Hub:** Bound to a single dedicated `#secret-santa` channel for announcements, polls, and live countdowns.

- **Vietnam Timezone & Deadlines (`Asia/Ho_Chi_Minh` / UTC+7):**
  - All naive dates and times default automatically to Vietnam Time (ICT / GMT+7).
  - Relative deadlines (e.g., `3d`, `7 days`, `24h`) and absolute dates (`2026-12-10 20:00`, `Dec 15`) are converted to epoch timestamps with Discord dynamic timezone tags (`<t:TIMESTAMP:F>` and `<t:TIMESTAMP:R>`).
- **Escalating Reminders Toward Deadline:**
  - Automated alerts escalate in frequency as the deadline approaches: **3 days $\to$ 48 hours $\to$ 24 hours $\to$ 12 hours $\to$ 6 hours $\to$ 2 hours $\to$ final 1 hour call!**
  - Background scheduler automatically executes the draw, saves pairs, and dispatches secret DMs the instant the deadline arrives!
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

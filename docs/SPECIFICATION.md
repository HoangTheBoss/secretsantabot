# System Specification & Architecture

## 1. System Scope & Philosophy

**Buda Secret Santa** is focused strictly on the **pre-party preparation lifecycle**:
1. Polling the group on party date, venue, and budget ceiling.
2. Registering participants and collecting wishlists via Discord Modals.
3. Managing pairing exclusions (e.g., partners/roommates).
4. Running the secret draw and dispatching private assignments with physical gift labeling codes.
5. Providing an Anonymous Q&A Relay so Santas can clarify sizes/preferences.
6. Tracking gift preparation progress with a spoiler-free countdown.

**Out of Scope for the Bot:**
- In-person party unboxing, real-time guessing games, or live party timers. All party activities are carried out manually by the group in real life.
- The bot simply provides an **Admin Backup Export** command so the organizer can privately view or print a master list if someone forgets their target or needs verification during the party.

---

## 2. Event Lifecycle & State Machine

```mermaid
stateDiagram-v2
    [*] --> DRAFT: Admin initializes event
    DRAFT --> POLLING: Run budget / date / venue polls
    POLLING --> REGISTRATION: Open signups & wishlist collection
    REGISTRATION --> REGISTRATION: Users join/update wishlist via modal
    REGISTRATION --> MATCHED: Admin triggers draw (validates constraints)
    MATCHED --> IN_PROGRESS: Secret DMs dispatched with gift codes
    IN_PROGRESS --> IN_PROGRESS: Anonymous Q&A + Prep status updates
    IN_PROGRESS --> READY_FOR_PARTY: All gifts wrapped / Party date reached
    READY_FOR_PARTY --> COMPLETED: Admin archives event post-party
    COMPLETED --> [*]
```

### State Definitions

| State | Scope | Description |
| :--- | :--- | :--- |
| `DRAFT` | Channel (Admin) | Session initialized; bound to `#secret-santa`. |
| `POLLING` | Public Channel | Bot runs interactive polls for budget limit and party date/venue. |
| `REGISTRATION` | Public & DM | Users join via button; bot verifies DM capability; users submit wishlist via modal. |
| `MATCHED` | Automated Engine | Validates constraints ($N \ge 3$, exclusions); computes derangement cycle. |
| `IN_PROGRESS` | Private DMs | Santas receive target profile, physical gift tag code, and Anonymous Q&A. |
| `READY_FOR_PARTY` | Public Channel | All gifts reported ready (or party date arrived); countdown reaches zero. |
| `COMPLETED` | Database | Session archived; pairings recorded to avoid repeat matches in future years. |

---

## 3. Database Schema (SQLite / `aiosqlite`)

```sql
-- Active and historical game sessions
CREATE TABLE IF NOT EXISTS game_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT', -- 'DRAFT', 'POLLING', 'REGISTRATION', 'IN_PROGRESS', 'READY_FOR_PARTY', 'COMPLETED'
    budget TEXT,                          -- e.g. "$25 - $35"
    party_date TEXT,                      -- e.g. "2026-12-24 19:00"
    party_venue TEXT,                     -- e.g. "Alice's Place / Bistro 42"
    signup_deadline TEXT,
    signup_deadline_epoch INTEGER,
    auto_draw BOOLEAN DEFAULT 1,
    triggered_milestones TEXT DEFAULT '',
    registration_message_id INTEGER,
    event_name TEXT DEFAULT 'Buda Secret Santa',
    logo_url TEXT,
    banner_url TEXT,
    footer_text TEXT,
    theme_color TEXT,
    last_reminded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Registered participants and their preferences
CREATE TABLE IF NOT EXISTS participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    display_name TEXT NOT NULL,
    wishlist TEXT DEFAULT '',
    dislikes TEXT DEFAULT '',
    offline_notes TEXT DEFAULT '',        -- Dietary restrictions, drink preference, arrival notes
    gift_status TEXT DEFAULT 'NOT_STARTED', -- 'NOT_STARTED', 'BOUGHT', 'WRAPPED'
    dm_verified BOOLEAN DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES game_sessions(id) ON DELETE CASCADE,
    UNIQUE (session_id, user_id)
);

-- Secret pairings
CREATE TABLE IF NOT EXISTS pairings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    santa_id INTEGER NOT NULL,
    baby_id INTEGER NOT NULL,
    gift_tag_code TEXT NOT NULL,          -- Code (e.g. "POLAR-4") written on physical wrapping
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    gift_status TEXT DEFAULT 'NOT_STARTED', -- 'NOT_STARTED', 'BOUGHT', 'WRAPPED'
    FOREIGN KEY (session_id) REFERENCES game_sessions(id) ON DELETE CASCADE,
    UNIQUE (session_id, santa_id),
    UNIQUE (session_id, baby_id)
);

-- Exclusion constraints (e.g. couples, roommates, siblings)
CREATE TABLE IF NOT EXISTS exclusions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    user_a_id INTEGER NOT NULL,
    user_b_id INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES game_sessions(id) ON DELETE CASCADE,
    UNIQUE (session_id, user_a_id, user_b_id)
);

-- Anonymous Relay Messages
CREATE TABLE IF NOT EXISTS relay_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    santa_id INTEGER NOT NULL,
    baby_id INTEGER NOT NULL,
    direction TEXT NOT NULL,              -- 'SANTA_TO_BABY' or 'BABY_TO_SANTA'
    content TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 4. Feature Specifications

### 4.1 Channel Hub & Polling
- All public interactions are locked to the configured `SANTA_CHANNEL_ID`.
- **Interactive Modals:**
  - Running `/secretsanta poll` opens the **CreatePollModal**, where the host enters the question and choices (one per line).
  - The bot renders an interactive button poll supporting 2 to 5 options.
  - Votes are tracked per member and update live on the button labels.

### 4.2 Registration & Modals
- Main Channel Embed features:
  - **[Join 🎁] Button**: Verifies DMs with an ephemeral check, then opens a modal dialog.
    - Fields:
      1. *Wishlist / Interests* (links, ideas, genres).
      2. *Dislikes / Allergies* (items to avoid).
      3. *Party / Drink Notes* (e.g., wine vs beer, arrival notes).
  - **[Update Wishlist 📝] Button**: Re-opens the modal with previously entered answers.
  - **[Leave ❌] Button**: Allows withdrawing before the draw.

### 4.3 Exclusion Management
- Host can run `/secretsanta exclude` without arguments to open the **ExclusionManageView**, which features a native `UserSelect` dropdown to pick 2 members visually.
- Exclusions can also be cleared with a single click.

### 4.4 All-in-One Host Control Panel (`/secretsanta panel`)
- Host can run `/secretsanta panel` to open a unified interactive dashboard featuring:
  - `[ ⚙️ Settings ]`: Opens `SetupModal`
  - `[ 🎨 Branding ]`: Opens `BrandingModal`
  - `[ 📊 Create Poll ]`: Opens `CreatePollModal`
  - `[ ⏰ Set Deadline ]`: Opens `DeadlineModal`
  - `[ 🚫 Exclusions ]`: Opens `ExclusionManageView`
  - `[ 📢 Reminders ]`: Opens `RemindMenuView`
  - `[ 🔒 Master Sheet ]`: Displays secret cheat sheet
  - `[ 🎲 Draw Pairs ]`: Manually executes the draw

### 4.5 Custom Branding & Appearance Engine
- Configurable via `/secretsanta branding` slash command or the `[ 🎨 Branding ]` panel button:
  - **Event Name:** Replaces default titles across public cards and private DMs (e.g. `Buda Secret Santa 2026`).
  - **Theme Color:** Supports named color constants (`RED`, `GREEN`, `GOLD`, `BLUE`, `PURPLE`, etc.) or custom hex values (`#E74C3C`).
  - **Logo / Thumbnail URL:** Appears as thumbnail on registration & progress cards and author icon on Santa assignment DMs.
  - **Banner Image URL:** Displays high-resolution banner image across registration and progress cards.
  - **Footer Text & Icon:** Custom signature text and logo shown on embeds.
- Updates immediately refresh the channel's registration message in-place without reposting or spamming chat.
- Defaults configurable via environment variables (`DEFAULT_EVENT_NAME`, `DEFAULT_LOGO_URL`, `DEFAULT_BANNER_URL`, `DEFAULT_FOOTER_TEXT`, `DEFAULT_THEME_COLOR`).

### 4.6 Matching & Secret DM Dispatch
- **Manual Draw:** The host can manually execute the draw anytime using `/secretsanta draw`.
- **Automatic Draw on Deadline:**
  - When configuring `/secretsanta setup` or `/secretsanta set_deadline deadline:"3d" auto_draw:True`, the bot monitors the deadline epoch timestamp in a background loop.
  - As soon as the deadline arrives:
    1. Verifies $\ge 3$ participants have joined.
    2. Runs algorithmic derangement with backtracking to satisfy all exclusions.
    3. Saves pairings to SQLite and advances session state to `IN_PROGRESS`.
    4. Automatically dispatches private DMs to each Santa with their target's wishlist and secret gift tag code.
    5. Posts celebratory announcement to `#secret-santa`.
  - If fewer than 3 participants joined by deadline, the bot posts a friendly warning postponing the draw and keeping registration open.


### 4.7 Anonymous Q&A Relay
- Santa clicks **[Ask Baby Anonymously ✉️]** in their DM $\to$ opens modal $\to$ submits question.
- Bot relays the question to Baby's DM:
  > *"📩 Message from your Secret Santa: 'What is your T-shirt size?'"*
  > `[ Reply to Secret Santa ↩️ ]`
- Baby replies via modal; bot relays answer back to Santa.

### 4.8 Preparation Tracker & Countdown
- The main channel displays an auto-updating embed:
  > **🎄 Secret Santa Countdown to the Party!**
  > ⏳ **Days remaining:** 4 days (Dec 22, 19:00)
  > 📍 **Venue:** Alice's Place
  > 💰 **Budget:** ~$30
  >
  > **🎁 Preparation Progress:**
  > `[████████░░]` **7 / 9 Santas have wrapped their gifts!**
- No names are spoiled publicly.

### 4.9 Routine Updates & Reminders System
- **Timezone Standard:** Defaults to **Vietnam Time (`Asia/Ho_Chi_Minh` / ICT / UTC+7)**. All date strings (e.g. `Dec 15 20:00`) are parsed relative to GMT+7, with Discord dynamic tags `<t:EPOCH:F>` displaying the equivalent in every user's local device time.
- **Background Task (`discord.ext.tasks`):**
  - Runs routine reminder loops and checks auto-draw/milestones every 30 seconds.
- **Escalating Reminders Toward Sign-Up Deadline:**
  - Automated public reminders trigger at escalating intervals:
    - **72 Hours (3 Days):** Initial notice of closing registration.
    - **48 Hours (2 Days):** Mid-week alert with current participant count.
    - **24 Hours (1 Day):** 24-hour warning that draw executes tomorrow.
    - **12 Hours:** Half-day countdown.
    - **6 Hours:** Afternoon notice.
    - **2 Hours:** Urgent alert.
    - **1 Hour:** Final 60-minute call before pairs are locked and drawn.
  - Each milestone triggers at most once via database milestone tracking (`triggered_milestones`).
- **Smart DM Nudges for Santas:**
  - Automatically queries Santas whose gifts are still `NOT_STARTED` or `BOUGHT` (ignoring Santas who already wrapped).
  - Delivers a private DM embed reminding them of their target's name, physical gift tag code, and interactive buttons to mark as wrapped or ask questions.
- **On-Demand Admin Commands:**
  - `/remind channel [custom_note]`: Immediately posts a public reminder to `#secret-santa`.
  - `/remind dms [custom_note]`: Immediately sends reminder DMs to all unwrapped Santas.
  - `/remind user member:<Member> [custom_note]`: Sends a reminder DM to a specific user.

### 4.10 Host Emergency Backup
- `/secretsanta admin export`: Ephemerally sends the organizer a private master cheat sheet (or CSV/text summary) of all pairings and gift codes in case someone forgets who they have on party day.
- `/secretsanta admin resend @participant`: Privately re-sends a participant their target info DM.

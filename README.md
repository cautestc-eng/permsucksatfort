# Orlando Moderation Bot

A complete Discord moderation bot designed for easy deployment on Replit. Includes SSU (Server Startup/Shutdown) system, infraction management, staff tracking, channel locking, and more.

## Features

- **SSU System** — Start, end, pause, resume, lock/unlock SSU sessions with branded embeds
- **Moderation** — Warn, kick, ban, unban, timeout, untimeout, purge, nickname, notes
- **Infractions** — Issue, remove, edit, view, search with automatic point escalation
- **Staff Management** — Profiles, statistics, leaderboards
- **Channel Locking** — Lock/unlock channels with configurable messages
- **Appeals** — Create, accept, deny infraction appeals
- **Server Stats** — Live player/staff tracking via Melonly API
- **Automatic Logging** — Separate log channels for every action type
- **Database** — SQLite with automatic migrations

## Quick Start (Replit)

1. **Clone or upload** this repository to Replit
2. **Set up environment** — Copy `.env.example` to `.env` and add your bot token
3. **Configure** — Copy `config.json.example` to `config.json` and fill in your guild ID, role IDs, channel IDs
4. **Run** — Press the Run button in Replit

The bot will automatically create the database and all required tables on first run.

## Configuration

Edit `config.json` to set:
- `guild_id` — Your Discord server ID
- `roles` — Role IDs for each permission level
- `channels` — Channel IDs for logging
- `embed_colors` — Custom embed colors
- `thresholds` — Infraction point thresholds
- `server_name`, `server_code` — Server branding
- `max_players` — Maximum player count display

## Environment Variables

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Your Discord bot token |
| `MELONLY_API_URL` | Melonly API endpoint for server stats |
| `MELONLY_API_KEY` | Melonly API key (if required) |

## Commands

### SSU
- `/ssu [code]` — Start a Server Startup
- `/ssu_end` — End active SSU
- `/ssu_pause` / `/ssu_resume` — Pause/resume SSU
- `/ssu_lock` / `/ssu_unlock` — Lock/unlock SSU
- `/ssu_status` — Check SSU status

### Sessions
- `/session_history` — View session history
- `/session_info` — View session details
- `/session_delete` — Delete a session
- `/session_export` — Export sessions as JSON

### Moderation
- `/warn`, `/kick`, `/ban`, `/unban`
- `/timeout`, `/untimeout`
- `/purge`, `/nickname`, `/note`

### Infractions
- `/infraction_issue` — Issue an infraction
- `/infraction_remove` — Remove an infraction
- `/infraction_edit` — Edit an infraction
- `/infraction_view` — View infraction details
- `/infraction_history` — View member infraction history
- `/infraction_search` — Search infractions
- `/infraction_leaderboard` — Points leaderboard

### Staff
- `/staff_profile` — View staff profile
- `/staff_stats` — View staff statistics
- `/staff_leaderboard` — Staff leaderboard

### Channels
- `/lock` — Lock a channel
- `/unlock` — Unlock a channel
- `/slowmode` — Set channel slowmode

### Appeals
- `/appeal_create` — Create an appeal
- `/appeal_accept` — Accept an appeal
- `/appeal_deny` — Deny an appeal

### Server Stats
- `/server_update` — Manually update stats
- `/server_players` — View player count
- `/server_staff` — View staff count

## Permission Hierarchy

| Role | Permissions |
|---|---|
| Trial Moderator | View infractions, view stats |
| Moderator | Warn, kick, timeout, issue infractions |
| Supervisor | Manage infractions, start/end SSU, lock channels |
| Administrator | Ban, remove infractions, manage sessions, config |
| Management | Everything |

## Asset Files

The bot automatically uses PNG files in the root directory:
- `Session Startup.png` — SSU start banner
- `Session shutdown.png` — SSU end banner
- `logo.png` — Server logo
- `Session Boost.png` — Boost banner
- `Sessionvote.png` — Vote banner

## Database

The bot uses SQLite (`orlando_bot.db`) with the following tables:
- `users` — User profiles and points
- `infractions` — Infraction records
- `staff_stats` — Staff statistics
- `appeals` — Appeal records
- `ssu_history` — SSU session history
- `moderation_logs` — All moderation actions
- `server_stats_cache` — Cached server statistics

## Logging

Logs are written to `logs/bot.log` with rotation. Separate Discord log channels can be configured for:
- `#mod-log` — Moderation actions
- `#infraction-log` — Infraction actions
- `#ssu-log` — SSU events
- `#lock-log` — Channel lock/unlock
- `#ban-log` — Ban/unban events
- `#staff-log` — Staff escalation/alerts
- `#error-log` — Error notifications
"# permsucksatfort" 

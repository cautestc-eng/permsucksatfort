import sqlite3
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger("OrlandoBot.Database")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orlando_bot.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL DEFAULT 'Unknown',
            join_date TEXT DEFAULT (datetime('now')),
            rank TEXT DEFAULT 'Member',
            total_points INTEGER DEFAULT 0,
            active_infractions INTEGER DEFAULT 0,
            sessions_hosted INTEGER DEFAULT 0,
            moderation_actions INTEGER DEFAULT 0,
            bans INTEGER DEFAULT 0,
            kicks INTEGER DEFAULT 0,
            warnings INTEGER DEFAULT 0,
            locks_performed INTEGER DEFAULT 0,
            ssu_duration INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS infractions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            infraction_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            timestamp TEXT DEFAULT (datetime('now')),
            points INTEGER NOT NULL DEFAULT 0,
            category TEXT NOT NULL DEFAULT 'Other',
            infraction_type TEXT NOT NULL DEFAULT 'Custom',
            evidence_link TEXT DEFAULT '',
            active INTEGER DEFAULT 1,
            edited INTEGER DEFAULT 0,
            edit_reason TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (moderator_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS staff_stats (
            user_id INTEGER PRIMARY KEY,
            infractions_issued INTEGER DEFAULT 0,
            moderation_actions INTEGER DEFAULT 0,
            ssus_hosted INTEGER DEFAULT 0,
            ssu_duration INTEGER DEFAULT 0,
            locks_performed INTEGER DEFAULT 0,
            bans INTEGER DEFAULT 0,
            kicks INTEGER DEFAULT 0,
            warnings INTEGER DEFAULT 0,
            last_action_date TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS appeals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appeal_id TEXT UNIQUE NOT NULL,
            infraction_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            timestamp TEXT DEFAULT (datetime('now')),
            resolved_by INTEGER DEFAULT NULL,
            resolution_message TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (infraction_id) REFERENCES infractions(infraction_id)
        );

        CREATE TABLE IF NOT EXISTS ssu_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            host_id INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT DEFAULT '',
            duration INTEGER DEFAULT 0,
            peak_players INTEGER DEFAULT 0,
            peak_staff INTEGER DEFAULT 0,
            server_code TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            channel_id INTEGER DEFAULT 0,
            message_id INTEGER DEFAULT 0,
            end_message_id INTEGER DEFAULT 0,
            FOREIGN KEY (host_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS moderation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_id TEXT UNIQUE NOT NULL,
            moderator_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            reason TEXT NOT NULL,
            timestamp TEXT DEFAULT (datetime('now')),
            result TEXT DEFAULT 'success',
            duration INTEGER DEFAULT 0,
            channel_id INTEGER DEFAULT 0,
            FOREIGN KEY (moderator_id) REFERENCES users(user_id),
            FOREIGN KEY (target_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS server_stats_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            players INTEGER DEFAULT 0,
            staff INTEGER DEFAULT 0,
            max_players INTEGER DEFAULT 40,
            last_updated TEXT DEFAULT (datetime('now'))
        );
        
        CREATE TABLE IF NOT EXISTS config_cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")


def get_next_infraction_id():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM infractions")
    count = cursor.fetchone()[0]
    conn.close()
    return f"INF-{count + 1:06d}"


def get_next_session_id():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM ssu_history")
    count = cursor.fetchone()[0]
    conn.close()
    return f"SSU-{count + 1:06d}"


def get_next_action_id():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM moderation_logs")
    count = cursor.fetchone()[0]
    conn.close()
    return f"ACT-{count + 1:06d}"


def get_next_appeal_id():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM appeals")
    count = cursor.fetchone()[0]
    conn.close()
    return f"APL-{count + 1:06d}"


def ensure_user(user_id, username="Unknown"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
    conn.commit()
    conn.close()


def ensure_staff_stats(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO staff_stats (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

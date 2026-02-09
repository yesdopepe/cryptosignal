"""Fix DB: make YESDO admin and subscribe to all channels with email ON."""
import sqlite3

DB = "apps/api/crypto_signals.db"

conn = sqlite3.connect(DB)
c = conn.cursor()

# 1. Make YESDO admin
c.execute("UPDATE users SET is_admin = 1 WHERE id = 1")
print("Set YESDO as admin")

# 2. Subscribe YESDO to ALL channels with email ON
channels = c.execute("SELECT id, name FROM channels").fetchall()
for ch_id, ch_name in channels:
    exists = c.execute(
        "SELECT id FROM channel_subscriptions WHERE user_id = 1 AND channel_id = ?",
        (ch_id,)
    ).fetchone()
    if not exists:
        c.execute(
            "INSERT INTO channel_subscriptions (user_id, channel_id, is_active, notify_email, notify_telegram, created_at) VALUES (1, ?, 1, 1, 1, datetime('now'))",
            (ch_id,)
        )
        print(f"  Subscribed to: {ch_name} (id={ch_id})")
    else:
        c.execute(
            "UPDATE channel_subscriptions SET notify_email = 1 WHERE user_id = 1 AND channel_id = ?",
            (ch_id,)
        )
        print(f"  Updated: {ch_name} (id={ch_id}) -> email=ON")

conn.commit()

# 3. Verify
subs = c.execute("SELECT channel_id, notify_email FROM channel_subscriptions WHERE user_id = 1").fetchall()
print(f"\nFinal subscriptions: {subs}")
admin = c.execute("SELECT is_admin FROM users WHERE id = 1").fetchone()
print(f"YESDO is_admin: {admin[0]}")

conn.close()
print("\nDone!")

from app.services.db import get_db_connection

def create_notification(user_id, message):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO notifications (user_id, message) VALUES (?, ?)",
        (user_id, message)
    )
    conn.commit()
    conn.close()

def get_unread_notifications(user_id, limit=10):
    conn = get_db_connection()
    notifications = conn.execute(
        "SELECT id, message, created_at FROM notifications WHERE user_id = ? AND is_read = 0 ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(n) for n in notifications]

def mark_all_read(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_notification_count(user_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT COUNT(*) as count FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,)
    ).fetchone()
    conn.close()
    return row["count"] if row else 0

def get_recent_notifications(user_id, limit=5):
    conn = get_db_connection()
    notifications = conn.execute(
        "SELECT id, message, created_at, is_read FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(n) for n in notifications]

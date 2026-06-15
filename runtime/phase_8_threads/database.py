import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / 'data'
DB_PATH = DATA_DIR / 'threads.db'

def init_db():
    """Initializes the SQLite database schema."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS threads (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(thread_id) REFERENCES threads(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                rating INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def create_thread() -> str:
    """Creates a new thread and returns its UUID string."""
    thread_id = str(uuid.uuid4())
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO threads (id) VALUES (?)', (thread_id,))
        conn.commit()
    return thread_id

def list_threads() -> list:
    """Lists all active threads that have messages, ordered by the latest message time."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        query = '''
            SELECT t.id, t.created_at, 
                   (SELECT content FROM messages WHERE thread_id = t.id AND role = 'user' ORDER BY timestamp ASC LIMIT 1) as title,
                   (SELECT MAX(timestamp) FROM messages WHERE thread_id = t.id) as last_msg_time
            FROM threads t
            WHERE title IS NOT NULL
            ORDER BY last_msg_time DESC
        '''
        cursor.execute(query)
        return cursor.fetchall()

def add_message(thread_id: str, role: str, content: str):
    """Saves a message to the thread history."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO messages (thread_id, role, content) VALUES (?, ?, ?)',
            (thread_id, role, content)
        )
        conn.commit()

def get_history(thread_id: str, limit: int = 4) -> list:
    """Retrieves the last N messages for the specified thread."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT role, content FROM messages WHERE thread_id = ? ORDER BY timestamp DESC LIMIT ?',
            (thread_id, limit)
        )
        rows = cursor.fetchall()
        # Return chronologically (oldest first in the context window)
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

def insert_feedback(message_id: str, rating: int):
    """Saves a user feedback rating (1 or -1) for a specific message."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO feedback (message_id, rating) VALUES (?, ?)',
            (message_id, rating)
        )
        conn.commit()

# Initialize on import
init_db()

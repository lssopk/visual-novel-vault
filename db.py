import os, sqlite3, time
from pathlib import Path

DB_PATH = os.environ.get('DB_PATH', '/data/vault.sqlite3')

def connect():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA busy_timeout=10000')
    return db

def init():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS api_keys(id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT UNIQUE NOT NULL, scopes TEXT NOT NULL, created_at INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS games(id TEXT PRIMARY KEY, title TEXT NOT NULL, original_title TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', genre TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS chapters(id TEXT PRIMARY KEY, game_id TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE, number INTEGER NOT NULL, title TEXT NOT NULL, overview TEXT NOT NULL DEFAULT '', caution TEXT NOT NULL DEFAULT '', unlocked INTEGER NOT NULL DEFAULT 0, updated_at INTEGER NOT NULL, UNIQUE(game_id,number));
        CREATE TABLE IF NOT EXISTS entries(id TEXT PRIMARY KEY, chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', happened_at TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '', confidence TEXT NOT NULL DEFAULT 'unverified', position INTEGER NOT NULL DEFAULT 0, updated_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS characters(id TEXT PRIMARY KEY, game_id TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE, name TEXT NOT NULL, bio TEXT NOT NULL DEFAULT '', first_chapter INTEGER NOT NULL DEFAULT 1, updated_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS links(id TEXT PRIMARY KEY, game_id TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE, source_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE, target_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE, label TEXT NOT NULL DEFAULT '', first_chapter INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS theories(id TEXT PRIMARY KEY, chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE, title TEXT NOT NULL, claim TEXT NOT NULL DEFAULT '', support TEXT NOT NULL DEFAULT '', counter TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open', updated_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, at INTEGER NOT NULL, actor TEXT NOT NULL, method TEXT NOT NULL, resource TEXT NOT NULL, object_id TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS ix_entries_chapter ON entries(chapter_id,position);
        CREATE INDEX IF NOT EXISTS ix_characters_game ON characters(game_id,first_chapter);
        CREATE INDEX IF NOT EXISTS ix_links_game ON links(game_id,first_chapter);
        CREATE INDEX IF NOT EXISTS ix_chapters_game ON chapters(game_id,number);
        ''')

def now(): return int(time.time())

def audit(db, actor, method, resource, oid):
    db.execute('INSERT INTO audit(at,actor,method,resource,object_id) VALUES(?,?,?,?,?)', (now(),actor,method,resource,oid))

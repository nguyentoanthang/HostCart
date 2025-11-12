import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from src.data.models import Game, UserGame, Tag, GameStatus
from src.utils.config_manager import ConfigManager

class DatabaseManager:
    def __init__(self, db_path: str = "game_collection.db"):
        self.db_path = db_path
        self.init_database()
        self._configure_sqlite_cache()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(
            self.db_path,
            # Connection-level optimizations
            timeout=30.0,  # 30 second timeout
            check_same_thread=False  # Allow multi-threading
        )
        conn.row_factory = sqlite3.Row
        
        # Set connection-specific pragmas
        conn.execute("PRAGMA temp_store = MEMORY")  # Store temp tables in memory
        conn.execute("PRAGMA foreign_keys = ON")    # Enable foreign key constraints
        
        try:
            yield conn
        finally:
            conn.close()

    def init_database(self):
        """Initialize database with all required tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # User games table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_games (
                    id INTEGER PRIMARY KEY,                 -- User game ID (NOT NULL)
                    game_id TEXT NOT NULL,                  -- External game ID (IGDB ID or custom)
                    name TEXT NOT NULL,                     -- Game name (required)
                    summary TEXT,                           -- Game summary (can be NULL)
                    release_date TEXT,                      -- ISO date string (can be NULL)
                    genres TEXT,                            -- JSON array (can be NULL)
                    platforms TEXT,                         -- JSON array (can be NULL)
                    cover_url TEXT,                         -- Image URL (can be NULL)
                    screenshots TEXT,                       -- JSON array (can be NULL)
                    developer TEXT,                         -- Developer name (can be NULL)
                    publisher TEXT,                         -- Publisher name (can be NULL)
                    rating REAL,                            -- IGDB rating (can be NULL)
                    metacritic_score INTEGER,               -- Metacritic score (can be NULL)
                    created_at TEXT,                        -- Auto-set timestamp
                    updated_at TEXT,                        -- Auto-set timestamp
                    status TEXT NOT NULL,                   -- User game status (Cannot be NULL)
                    tags TEXT NOT NULL,                     -- JSON array of tag names (Cannot be NULL)
                    user_rating INTEGER,                    -- User's rating (can be NULL)
                    user_review TEXT,                       -- User's review (can be NULL)
                    played_time INTEGER NOT NULL,           -- Playtime in minutes (Cannot be NULL)
                    date_added TEXT NOT NULL,               -- When added to collection (Cannot be NULL)
                    date_started TEXT,                      -- When user started playing (can be NULL)
                    date_completed TEXT,                    -- When user completed (can be NULL)
                    last_played TEXT,                       -- Last play session (can be NULL)
                    notes TEXT,                             -- User notes (can be NULL)
                    UNIQUE(game_id)                         -- One entry per game_id
                )
            ''')

            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_games_id ON user_games (id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_games_game_id ON user_games (game_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_games_status ON user_games (status)')

            conn.commit()

    def _configure_sqlite_cache(self):
        """Configure SQLite's built-in caching for better performance"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Set page cache size (default is usually 2MB, increase for better performance)
            cursor.execute("PRAGMA cache_size = 10000")  # 10000 pages * page_size
            
            # Set page size (default is usually 4096 bytes)
            cursor.execute("PRAGMA page_size = 4096")
            
            # Enable memory-mapped I/O for faster reads
            cursor.execute("PRAGMA mmap_size = 268435456")  # 256MB
            
            # Set journal mode for better concurrency
            cursor.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging
            
            # Set synchronous mode (NORMAL is good balance of safety/performance)
            cursor.execute("PRAGMA synchronous = NORMAL")
            
            # Enable query optimization
            cursor.execute("PRAGMA optimize")
            
            conn.commit()

    def _row_to_dict(self, row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        """Convert sqlite3.Row to dictionary"""
        return dict(row) if row else None

    def _parse_json_field(self, value: Optional[str]) -> Optional[List[str]]:
        """Parse JSON string field to list"""
        if not value:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None

    def _serialize_json_field(self, value: Optional[List[str]]) -> Optional[str]:
        """Serialize list to JSON string"""
        if not value:
            return None
        return json.dumps(value)
    
    def _datetime_to_str(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.isoformat()

class GameCollectionManager:
    def __init__(self):
        db_path = ConfigManager().get_config().database.db_file
        self.db = DatabaseManager(db_path)

    # Game CRUD operations - Let SQLite handle caching
    def add_user_game(self, user_game: UserGame) -> int:
        """Add a new user game to the database"""

        game = user_game.game

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Insert into user_game table
            cursor.execute('''
                INSERT INTO user_games (game_id, name, summary, release_date, genres, platforms,
                                        cover_url, screenshots, developer, publisher, rating, metacritic_score,
                                        created_at, updated_at, status, tags, user_rating, user_review, played_time,
                                        date_added, date_started, date_completed, last_played, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                game.game_id,
                game.name,
                game.summary,
                self.db._datetime_to_str(game.release_date),
                self.db._serialize_json_field(game.genres),
                self.db._serialize_json_field(game.platforms),
                game.cover_url,
                self.db._serialize_json_field(game.screenshots),
                game.developer,
                game.publisher,
                game.rating,
                game.metacritic_score,
                self.db._datetime_to_str(game.created_at),
                self.db._datetime_to_str(game.updated_at),
                user_game.status.value,
                self.db._serialize_json_field([tag.name for tag in user_game.tags]),
                user_game.user_rating,
                user_game.user_review,
                user_game.played_time,
                self.db._datetime_to_str(user_game.date_added),
                self.db._datetime_to_str(user_game.date_started),
                self.db._datetime_to_str(user_game.date_completed),
                self.db._datetime_to_str(user_game.last_played),
                user_game.notes
            ))

            conn.commit()

            id = cursor.lastrowid

            if id is None:
                raise RuntimeError("Failed to insert game: no ID returned")
            
            return id

    def get_user_game_by_game_id(self, game_id: str) -> Optional[UserGame]:
        """Get user game by game_id"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_games WHERE game_id = ?', (game_id,))
            row = cursor.fetchone()
            
            if row:
                return self._row_to_user_game(row)
        return None

    def _row_to_user_game(self, row: sqlite3.Row) -> UserGame:
        """Convert database row to UserGame object"""
        
        # Check id is not NULL
        if row['game_id'] is None:
            raise ValueError("game_id cannot be NULL in database, database is corrupted.")
        
        # Check name is not NULL
        if row['name'] is None:
            raise ValueError("name cannot be NULL in database, database is corrupted.")

        # Create Game object
        game = Game(
            id=row['game_id'],
            name=row['name'],
            summary=row['summary'],
            release_date=datetime.fromisoformat(row['release_date']) if row['release_date'] else None,
            genres=self.db._parse_json_field(row['genres']),
            platforms=self.db._parse_json_field(row['platforms']),
            cover_url=row['cover_url'],
            screenshots=self.db._parse_json_field(row['screenshots']),
            developer=row['developer'],
            publisher=row['publisher'],
            rating=row['rating'],
            metacritic_score=row['metacritic_score'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
        )

        # Create Tag objects
        tag_names = self.db._parse_json_field(row['tags'])
        if not tag_names:
            raise ValueError("Tags cannot be NULL or empty in database, database is corrupted.")
        tags = [Tag(name=name) for name in tag_names]

        if row['date_added'] is None:
            raise ValueError("date_added cannot be NULL in database, database is corrupted.")
        
        if row['status'] is None:
            raise ValueError("status cannot be NULL in database, database is corrupted.")
        
        if row['played_time'] is None:
            raise ValueError("played_time cannot be NULL in database, database is corrupted.")

        # Create UserGame object
        user_game = UserGame(
            id=row['id'],
            game=game,
            tags=tags,
            status=GameStatus(row['status']),
            user_rating=row['user_rating'],
            user_review=row['user_review'],
            played_time=row['played_time'],
            date_added=datetime.fromisoformat(row['date_added']),
            date_started=datetime.fromisoformat(row['date_started']) if row['date_started'] else None,
            date_completed=datetime.fromisoformat(row['date_completed']) if row['date_completed'] else None,
            last_played=datetime.fromisoformat(row['last_played']) if row['last_played'] else None,
            notes=row['notes']
        )
        
        return user_game

    def update_user_game(self, user_game: UserGame) -> bool:
        """Update user game in database"""
        if user_game.id is None:
            return False
            
        game = user_game.game

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE user_games SET 
                    game_id = ?, name = ?, summary = ?, release_date = ?, genres = ?, platforms = ?,
                    cover_url = ?, screenshots = ?, developer = ?, publisher = ?, rating = ?, metacritic_score = ?,
                    created_at = ?, updated_at = ?, status = ?, tags = ?, user_rating = ?, user_review = ?, 
                    played_time = ?, date_added = ?, date_started = ?, date_completed = ?, last_played = ?, notes = ?
                WHERE id = ?
            ''', (
                game.game_id,
                game.name,
                game.summary,
                self.db._datetime_to_str(game.release_date),
                self.db._serialize_json_field(game.genres),
                self.db._serialize_json_field(game.platforms),
                game.cover_url,
                self.db._serialize_json_field(game.screenshots),
                game.developer,
                game.publisher,
                game.rating,
                game.metacritic_score,
                self.db._datetime_to_str(game.created_at),
                self.db._datetime_to_str(game.updated_at),
                user_game.status.value,
                self.db._serialize_json_field([tag.name for tag in user_game.tags]),
                user_game.user_rating,
                user_game.user_review,
                user_game.played_time,
                self.db._datetime_to_str(user_game.date_added),
                self.db._datetime_to_str(user_game.date_started),
                self.db._datetime_to_str(user_game.date_completed),
                self.db._datetime_to_str(user_game.last_played),
                user_game.notes,
                user_game.id
            ))

            conn.commit()
            return cursor.rowcount > 0

    def load_all_user_games(self) -> List[UserGame]:
        """Load all user games from database"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_games ORDER BY date_added DESC')
            rows = cursor.fetchall()
            
            return [self._row_to_user_game(row) for row in rows]

    def get_user_games_by_status(self, status: GameStatus) -> List[UserGame]:
        """Get user games filtered by status"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_games WHERE status = ? ORDER BY date_added DESC', (status.value,))
            rows = cursor.fetchall()
            
            return [self._row_to_user_game(row) for row in rows]

    def get_user_games_by_tag(self, tag_name: str) -> List[UserGame]:
        """Get user games that have a specific tag"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Use JSON_EXTRACT or LIKE for tag searching
            cursor.execute('''
                SELECT * FROM user_games 
                WHERE tags LIKE ? 
                ORDER BY date_added DESC
            ''', (f'%"{tag_name}"%',))
            rows = cursor.fetchall()
            
            # Filter to ensure exact tag match (not partial)
            user_games = []
            for row in rows:
                user_game = self._row_to_user_game(row)
                if user_game.has_tag_by_name(tag_name):
                    user_games.append(user_game)
            
            return user_games

    def delete_user_game(self, id: int) -> bool:
        """Delete user game from database by id"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_games WHERE id = ?', (id,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_user_game_by_game_id(self, game_id: str) -> bool:
        """Delete user game by game_id"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_games WHERE game_id = ?', (game_id,))
            conn.commit()
            return cursor.rowcount > 0

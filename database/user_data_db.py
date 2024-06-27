import os
import aiosqlite
import json
from datetime import datetime
from cachetools import TTLCache
from models.user_data import UserData

class UserDataDB:
    """Manages database operations for user data storage and retrieval."""

    def __init__(self, config, db_name='user_data.db'):
        """
        Initialize the Database instance.

        Args:
            config (dict): Configuration settings.
            db_name (str): Name of the database file.
        """
        self.db = None
        self.db_name = db_name
        os.makedirs(os.path.dirname(self.db_name), exist_ok=True)
        self.config = config
        self.provider_config = config["providers"][config["provider"]]
        self.cache = TTLCache(maxsize=config['user_data_db']['max_cache_size'],
                              ttl=config['user_data_db']['max_ttl'])

    def invalidate_cache(self, user_id: int):
        """Invalidate the cache for a user."""
        if user_id in self.cache:
            del self.cache[user_id]

    async def disconnect(self):
        """Disconnect from the database."""
        if self.db is not None:
            await self.db.close()
            self.db = None

    async def connect(self):
        """Connect to the database."""
        if self.db is None:
            self.db = await aiosqlite.connect(self.db_name)
        return self.db

    async def setup_database(self):
        """Create the users table if it doesn't exist."""
        db = await self.connect()
        await db.execute(f'''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            user_name TEXT,
            message_history TEXT,
            model TEXT DEFAULT '{self.provider_config["models"]["default"]}',
            system_prompt TEXT DEFAULT '{self.provider_config["models"]["system_prompt"]}',
            temperature REAL DEFAULT {self.provider_config["models"]["temperature"]},
            top_p REAL DEFAULT {self.provider_config["models"]["top_p"]},
            max_tokens INTEGER DEFAULT {self.provider_config["models"]["max_tokens"]},
            language TEXT DEFAULT '{self.config["language"]}',
            speaker TEXT DEFAULT '{self.provider_config["tts"]["speaker"]}',
            is_admin BOOLEAN DEFAULT 0,
            is_whitelisted BOOLEAN DEFAULT 0,
            is_blacklisted BOOLEAN DEFAULT 0,
            last_request TIMESTAMP
        )
        ''')
        await db.commit()

    async def get_user_data(self, user_id: int) -> UserData:
        """
        Retrieve user data from cache or database.

        Args:
            user_id (int): The ID of the user.

        Returns:
            UserData: The user data object, or None if not found.
        """
        if user_id in self.cache:
            return self.cache[user_id]

        db = await self.connect()
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            user_data = await cursor.fetchone()
    
        if user_data:
            user_data_obj = UserData(
                user_id=user_data[0],
                user_name=user_data[1],
                message_history=json.loads(user_data[2]),
                model=user_data[3],
                system_prompt=user_data[4],
                temperature=user_data[5],
                top_p=user_data[6],
                max_tokens=user_data[7],
                language=user_data[8],
                speaker=user_data[9],
                is_admin=user_data[10],
                is_whitelisted=user_data[11],
                is_blacklisted=user_data[12],
                last_request=datetime.fromisoformat(user_data[13]) if user_data[13] else None
            )
            self.cache[user_id] = user_data_obj
            return user_data_obj
        return None

    async def update_user_data(self, user_data: UserData):
        """
        Update or insert user data in the database and cache.

        Args:
            user_data (UserData): The user data object to update.
        """
        db = await self.connect()
        data = user_data.to_dict()
        msg_history = data['message_history'][-self.config['max_message_history_num']:]
        data['message_history'] = json.dumps(msg_history)
        data['last_request'] = data['last_request'].isoformat() if data['last_request'] else None
        columns = ', '.join(data.keys())
        placeholders = ':' + ', :'.join(data.keys())
        query = f'INSERT OR REPLACE INTO users ({columns}) VALUES ({placeholders})'
        await db.execute(query, data), 
        await db.commit()
        self.cache[user_data.user_id] = user_data

    async def create_user(self, user_id: int, user_name: str):
        """
        Create a new user in the database.

        Args:
            user_id (int): The ID of the new user.
        """
        user_data = UserData(user_id=user_id, user_name=user_name)
        await self.update_user_data(user_data)

    async def set_admin(self, user_id: int, is_admin: bool):
        """
        Set or unset admin status for a user.

        Args:
            user_id (int): The ID of the user.
            is_admin (bool): True to set as admin, False to unset.
        """
        db = await self.connect()
        await db.execute('UPDATE users SET is_admin = ? WHERE user_id = ?', (is_admin, user_id))
        await db.commit()
        self.invalidate_cache(user_id)
        
    async def set_whitelist(self, user_id: int, is_whitelisted: bool):
        """
        Add or remove a user from the whitelist.

        Args:
            user_id (int): The ID of the user.
            is_whitelisted (bool): True to whitelist, False to remove from whitelist.
        """
        db = await self.connect()
        await db.execute('UPDATE users SET is_whitelisted = ? WHERE user_id = ?', (is_whitelisted, user_id))
        await db.commit()
        self.invalidate_cache(user_id)

    async def set_blacklist(self, user_id: int, is_blacklisted: bool):
        """
        Add or remove a user from the blacklist.

        Args:
            user_id (int): The ID of the user.
            is_blacklisted (bool): True to blacklist, False to remove from blacklist.
        """
        db = await self.connect()
        await db.execute('UPDATE users SET is_blacklisted = ? WHERE user_id = ?', (is_blacklisted, user_id))
        await db.commit()
        self.invalidate_cache(user_id)

    async def get_all_users(self):
        """
        Retrieve all user IDs from the database.

        Returns:
            list: A list of all user IDs.
        """
        db = await self.connect()
        async with db.execute('SELECT user_id FROM users') as cursor:
            return [row[0] for row in await cursor.fetchall()]        
            
    async def get_admins(self):
        """
        Retrieve all admin user IDs from the database.

        Returns:
            list: A list of admin user IDs.
        """
        db = await self.connect()
        async with db.execute('SELECT user_id FROM users WHERE is_admin = 1') as cursor:
            return [row[0] for row in await cursor.fetchall()]

    async def get_user_by_username(self, username: str):
        """
        Retrieve user data by username.

        Args:
            username (str): The username to search for.

        Returns:
            UserData: The user data object if found, None otherwise.
        """
        db = await self.connect()
        async with db.execute('SELECT * FROM users WHERE user_name = ?', (username,)) as cursor:
            user_data = await cursor.fetchone()
        if user_data:
            return UserData(*user_data)
        return None
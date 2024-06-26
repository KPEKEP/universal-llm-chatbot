from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from datetime import datetime
from utils.config import load_config

config = load_config()
provider_config = config["providers"][config["provider"]]

@dataclass
class UserData:
    """
    Represents user data and preferences for AI interactions.
    """
    user_id: int
    message_history: List[Dict[str, str]] = field(default_factory=list)
    model: str = provider_config["models"]["default"]
    system_prompt: str = provider_config["models"]["system_prompt"]
    temperature: float = provider_config["models"]["temperature"]
    top_p: float = provider_config["models"]["top_p"]
    max_tokens: int = provider_config["models"]["max_tokens"]
    language: str = config["language"]
    speaker: str = provider_config["tts"]["speaker"]
    is_admin: bool = False
    is_whitelisted: bool = False
    is_blacklisted: bool = False
    last_request: Optional[datetime] = None

    def to_dict(self):
        """
        Convert the UserData instance to a dictionary.

        Returns:
            dict: A dictionary representation of the UserData instance.
        """
        return asdict(self)
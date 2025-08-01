"""
Client manager service for centralizing active_clients access and client-user relationships.

This service provides a centralized way to manage active client connections,
their state, and client-user relationships, allowing API endpoints to access
this information without tight coupling to the main.py module.
"""

import logging
import uuid
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from advanced_omi_backend.client import ClientState
    from advanced_omi_backend.users import User

logger = logging.getLogger(__name__)

# Global client-to-user mappings
# These will be initialized by main.py
_client_to_user_mapping: Dict[str, str] = {}  # Active clients only
_all_client_user_mappings: Dict[str, str] = {}  # All clients including disconnected


class ClientManager:
    """
    Centralized manager for active client connections and client-user relationships.

    This service provides thread-safe access to active client information
    and client-user relationship management for use in API endpoints and other services.
    """

    def __init__(self):
        self._active_clients: Dict[str, "ClientState"] = {}
        self._initialized = False

    def initialize(self, active_clients_dict: Dict[str, "ClientState"]):
        """
        Initialize the client manager with a reference to the active_clients dict.

        This should be called from main.py during startup to provide access
        to the global active_clients dictionary.
        """
        self._active_clients = active_clients_dict
        self._initialized = True
        logger.info("ClientManager initialized with active_clients reference")

    def is_initialized(self) -> bool:
        """Check if the client manager has been initialized."""
        return self._initialized

    def get_client(self, client_id: str) -> Optional["ClientState"]:
        """
        Get a specific client by ID.

        Args:
            client_id: The client ID to lookup

        Returns:
            ClientState object if found, None if client not found

        Raises:
            RuntimeError: If ClientManager is not initialized
        """
        if not self._initialized:
            logger.error("ClientManager not initialized, cannot get client")
            raise RuntimeError(
                "ClientManager not initialized - call initialize() first before accessing clients"
            )
        return self._active_clients.get(client_id)

    def has_client(self, client_id: str) -> bool:
        """
        Check if a client is currently active.

        Args:
            client_id: The client ID to check

        Returns:
            True if client is active, False otherwise
        """
        if not self._initialized:
            logger.warning("ClientManager not initialized, cannot check client")
            return False
        return client_id in self._active_clients

    def is_client_active(self, client_id: str) -> bool:
        """
        Check if a client is currently active (alias for has_client).

        Args:
            client_id: The client ID to check

        Returns:
            True if client is active, False otherwise
        """
        return self.has_client(client_id)

    def get_all_clients(self) -> Dict[str, "ClientState"]:
        """
        Get all active clients.

        Returns:
            Dictionary of client_id -> ClientState mappings
        """
        if not self._initialized:
            logger.warning("ClientManager not initialized, returning empty dict")
            return {}
        return self._active_clients.copy()

    def get_client_count(self) -> int:
        """
        Get the number of active clients.

        Returns:
            Number of active clients
        """
        if not self._initialized:
            logger.warning("ClientManager not initialized, returning 0")
            return 0
        return len(self._active_clients)

    def get_client_info_summary(self) -> list:
        """
        Get summary information about all active clients.

        Returns:
            List of client info dictionaries suitable for API responses
        """
        if not self._initialized:
            logger.warning("ClientManager not initialized, returning empty list")
            return []

        client_info = []
        for client_id, client_state in self._active_clients.items():
            current_audio_uuid = client_state.current_audio_uuid
            client_data = {
                "client_id": client_id,
                "connected": getattr(client_state, "connected", True),
                "current_audio_uuid": current_audio_uuid,
                "last_transcript_time": client_state.last_transcript_time,
                "conversation_start_time": client_state.conversation_start_time,
                "has_active_conversation": current_audio_uuid is not None,
                "conversation_transcripts_count": len(
                    getattr(client_state, "conversation_transcripts", [])
                ),
            }
            client_info.append(client_data)

        return client_info

    # Client-user relationship methods
    def client_belongs_to_user(self, client_id: str, user_id: str) -> bool:
        """
        Check if a client belongs to a specific user.

        Args:
            client_id: The client ID to check
            user_id: The user ID to check ownership against

        Returns:
            True if the client belongs to the user, False otherwise
        """
        # Check in all mappings (includes disconnected clients)
        mapped_user_id = _all_client_user_mappings.get(client_id)
        if mapped_user_id is None:
            logger.warning(f"Client {client_id} not found in user mapping")
            return False

        return mapped_user_id == user_id

    def get_user_clients_all(self, user_id: str) -> list[str]:
        """
        Get all client IDs (active and inactive) that belong to a specific user.

        Args:
            user_id: The user ID to get clients for

        Returns:
            List of client IDs belonging to the user
        """
        return [
            client_id
            for client_id, mapped_user_id in _all_client_user_mappings.items()
            if mapped_user_id == user_id
        ]

    def get_user_clients_active(self, user_id: str) -> list[str]:
        """
        Get active client IDs that belong to a specific user.

        Args:
            user_id: The user ID to get clients for

        Returns:
            List of active client IDs belonging to the user
        """
        return [
            client_id
            for client_id, mapped_user_id in _client_to_user_mapping.items()
            if mapped_user_id == user_id
        ]


# Global instance
_client_manager: Optional[ClientManager] = None


def get_client_manager() -> ClientManager:
    """
    Get the global client manager instance.

    Returns:
        ClientManager singleton instance
    """
    global _client_manager
    if _client_manager is None:
        _client_manager = ClientManager()
    return _client_manager


def init_client_manager(active_clients_dict: Dict[str, "ClientState"]):
    """
    Initialize the global client manager with active_clients reference.

    This should be called from main.py during startup.

    Args:
        active_clients_dict: Reference to the global active_clients dictionary
    """
    client_manager = get_client_manager()
    client_manager.initialize(active_clients_dict)
    return client_manager


# Client-user relationship initialization and utility functions
def init_client_user_mapping(
    active_mapping_dict: Dict[str, str], all_mapping_dict: Optional[Dict[str, str]] = None
):
    """
    Initialize the client-user mapping with references to the global mappings.

    This should be called from main.py during startup.

    Args:
        active_mapping_dict: Reference to the active client_to_user_mapping dictionary
        all_mapping_dict: Reference to the all_client_user_mappings dictionary (optional)
    """
    global _client_to_user_mapping, _all_client_user_mappings
    _client_to_user_mapping = active_mapping_dict
    if all_mapping_dict is not None:
        _all_client_user_mappings = all_mapping_dict
    logger.info("Client-user mapping initialized")


def register_client_user_mapping(client_id: str, user_id: str):
    """
    Register a client-user mapping for active clients.

    Args:
        client_id: The client ID
        user_id: The user ID that owns this client
    """
    _client_to_user_mapping[client_id] = user_id
    logger.info(f"✅ Registered active client {client_id} to user {user_id}")
    logger.info(f"📊 Active client mappings: {len(_client_to_user_mapping)} total")


def unregister_client_user_mapping(client_id: str):
    """
    Unregister a client-user mapping from active clients.

    Args:
        client_id: The client ID to unregister
    """
    if client_id in _client_to_user_mapping:
        user_id = _client_to_user_mapping.pop(client_id)
        logger.info(f"❌ Unregistered active client {client_id} from user {user_id}")
        logger.info(f"📊 Active client mappings: {len(_client_to_user_mapping)} remaining")
    else:
        logger.warning(f"⚠️ Attempted to unregister non-existent client {client_id}")


def track_client_user_relationship(client_id: str, user_id: str):
    """
    Track that a client belongs to a user (persists after disconnection for database queries).

    Args:
        client_id: The client ID
        user_id: The user ID that owns this client
    """
    _all_client_user_mappings[client_id] = user_id
    logger.debug(f"Tracked client {client_id} relationship to user {user_id}")


def client_belongs_to_user(client_id: str, user_id: str) -> bool:
    """
    Check if a client belongs to a specific user.

    Args:
        client_id: The client ID to check
        user_id: The user ID to check ownership against

    Returns:
        True if the client belongs to the user, False otherwise
    """
    # Check in all mappings (includes disconnected clients)
    mapped_user_id = _all_client_user_mappings.get(client_id)
    if mapped_user_id is None:
        logger.warning(f"Client {client_id} not found in user mapping")
        return False

    return mapped_user_id == user_id


def get_user_clients_all(user_id: str) -> list[str]:
    """
    Get all client IDs (active and inactive) that belong to a specific user.

    Args:
        user_id: The user ID to get clients for

    Returns:
        List of client IDs belonging to the user
    """
    return [
        client_id
        for client_id, mapped_user_id in _all_client_user_mappings.items()
        if mapped_user_id == user_id
    ]


def get_user_clients_active(user_id: str) -> list[str]:
    """
    Get active client IDs that belong to a specific user.

    Args:
        user_id: The user ID to get clients for

    Returns:
        List of active client IDs belonging to the user
    """
    logger.debug(f"🔍 Looking for active clients for user {user_id}")
    logger.debug(f"🔍 Available mappings: {_client_to_user_mapping}")

    user_clients = [
        client_id
        for client_id, mapped_user_id in _client_to_user_mapping.items()
        if mapped_user_id == user_id
    ]

    logger.debug(f"🔍 Found {len(user_clients)} active clients for user {user_id}: {user_clients}")
    return user_clients


def get_client_owner(client_id: str) -> Optional[str]:
    """
    Get the user ID that owns a specific client.

    Args:
        client_id: The client ID to look up

    Returns:
        User ID if found, None otherwise
    """
    return _all_client_user_mappings.get(client_id)


# FastAPI dependency function
async def get_client_manager_dependency() -> ClientManager:
    """
    FastAPI dependency to inject the client manager into route handlers.

    Usage:
        @router.get("/some-endpoint")
        async def some_endpoint(client_manager: ClientManager = Depends(get_client_manager_dependency)):
            clients = client_manager.get_all_clients()
            ...
    """
    client_manager = get_client_manager()
    if not client_manager.is_initialized():
        logger.error("ClientManager dependency requested but not initialized")
        # In a real application, you might want to raise an exception here
        # For now, we'll return the uninitialized manager and let the caller handle it
    return client_manager


def generate_client_id(user: "User", device_name: Optional[str] = None) -> str:
    """
    Generate a unique client_id in the format: user_id_suffix-device_suffix[-counter]

    This function checks both the database (user.registered_clients) and active
    connections to ensure no conflicts with existing or currently connected clients.

    Args:
        user: The User object
        device_name: Optional device name (e.g., 'havpe', 'phone', 'tablet')

    Returns:
        client_id in format: user_id_suffix-device_suffix or user_id_suffix-device_suffix-N for duplicates
    """
    # Use last 6 characters of MongoDB ObjectId as user identifier
    user_id_suffix = str(user.id)[-6:]

    if device_name:
        # Sanitize device name: lowercase, alphanumeric + hyphens only, max 10 chars
        sanitized_device = "".join(c for c in device_name.lower() if c.isalnum() or c == "-")[:10]
        base_client_id = f"{user_id_suffix}-{sanitized_device}"

        # Check for existing client IDs in database
        existing_client_ids = user.get_client_ids()

        # Also check active clients to prevent conflicts with currently connected clients
        client_manager = get_client_manager()
        active_client_ids = set()
        if client_manager.is_initialized():
            active_client_ids = set(client_manager.get_all_clients().keys())

        # Combine both sets of existing IDs
        all_existing_ids = set(existing_client_ids) | active_client_ids

        # If base client_id doesn't exist anywhere, use it
        if base_client_id not in all_existing_ids:
            return base_client_id

        # If it exists, find the next available counter
        counter = 2
        while f"{base_client_id}-{counter}" in all_existing_ids:
            counter += 1

        return f"{base_client_id}-{counter}"
    else:
        # Generate UUID-based suffix if no device name provided
        uuid_suffix = str(uuid.uuid4())[:8]  # Use first 8 chars of UUID for readability
        return f"{user_id_suffix}-{uuid_suffix}"

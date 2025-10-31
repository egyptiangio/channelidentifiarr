#!/usr/bin/env python3
"""
Simple Settings Manager for Channel Identifiarr
Handles persistent storage of application settings in a JSON file
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

import dotenv
dotenv.load_dotenv()

class SettingsManager:
    """
    Manages application settings in a JSON file.
    Security via file permissions (600 - owner read/write only).
    """

    def __init__(self, settings_path: str = None):
        """
        Initialize the settings manager.

        Args:
            settings_path: Path to settings file (default: /data/settings.json)
        """
        self.settings_path = settings_path or os.environ.get(
            'SETTINGS_PATH',
            '/data/settings.json'
        )
        self._ensure_settings_dir()

    def _ensure_settings_dir(self):
        """Ensure the settings directory exists"""
        settings_dir = os.path.dirname(self.settings_path)
        if settings_dir:
            Path(settings_dir).mkdir(parents=True, exist_ok=True)

    def load_settings(self) -> Dict[str, Any]:
        """
        Load settings from file. Falls back to environment variables if file doesn't exist.

        Returns:
            Dictionary of settings
        """
        # Try to load from file
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, 'r') as f:
                    settings = json.load(f)
                logger.info(f"Settings loaded from {self.settings_path}")
                return settings
            except Exception as e:
                logger.error(f"Error loading settings: {e}")

        # Fallback to environment variables
        settings = self._load_from_env()
        if settings:
            logger.info("Settings loaded from environment variables")
        else:
            logger.info("No settings found, using defaults")

        return settings

    def save_settings(self, settings: Dict[str, Any]) -> bool:
        """
        Save settings to file with restrictive permissions.

        Args:
            settings: Dictionary of settings to save

        Returns:
            True if successful, False otherwise
        """
        try:
            # Write to file
            with open(self.settings_path, 'w') as f:
                json.dump(settings, f, indent=2)

            # Set restrictive permissions (owner read/write only)
            os.chmod(self.settings_path, 0o600)

            logger.info(f"Settings saved to {self.settings_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False

    def update_settings(self, updates: Dict[str, Any]) -> bool:
        """
        Update specific settings without overwriting everything.

        Args:
            updates: Dictionary of settings to update (supports nested updates)

        Returns:
            True if successful, False otherwise
        """
        current_settings = self.load_settings()

        # Deep merge the updates
        merged_settings = self._deep_merge(current_settings, updates)

        return self.save_settings(merged_settings)

    def _deep_merge(self, base: Dict, updates: Dict) -> Dict:
        """Deep merge two dictionaries"""
        result = base.copy()
        for key, value in updates.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _load_from_env(self) -> Dict[str, Any]:
        """
        Load settings from environment variables as fallback.
        """
        settings = {}

        # Dispatcharr settings
        if os.environ.get('DISPATCHARR_URL'):
            settings['dispatcharr'] = {
                'url': os.environ.get('DISPATCHARR_URL'),
                'username': os.environ.get('DISPATCHARR_USERNAME', ''),
                'password': os.environ.get('DISPATCHARR_PASSWORD', '')
            }

        # Emby settings
        if os.environ.get('EMBY_URL'):
            settings['emby'] = {
                'url': os.environ.get('EMBY_URL'),
                'username': os.environ.get('EMBY_USERNAME', ''),
                'password': os.environ.get('EMBY_PASSWORD', '')
            }

        # Database settings
        if os.environ.get('DATABASE_PATH'):
            settings['database'] = {
                'path': os.environ.get('DATABASE_PATH')
            }

        return settings

    def get_setting(self, path: str, default: Any = None) -> Any:
        """
        Get a specific setting by path (e.g., 'dispatcharr.url')

        Args:
            path: Dot-separated path to setting
            default: Default value if not found

        Returns:
            Setting value or default
        """
        settings = self.load_settings()
        keys = path.split('.')

        current = settings
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current

    def delete_settings(self) -> bool:
        """Delete the settings file"""
        try:
            if os.path.exists(self.settings_path):
                os.remove(self.settings_path)
                logger.info(f"Settings file deleted: {self.settings_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting settings: {e}")
            return False


# Global settings manager instance
_settings_manager = None


def get_settings_manager() -> SettingsManager:
    """Get the global settings manager instance"""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager

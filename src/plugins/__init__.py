"""
Plugins System
===============
Bazowe klasy i manager dla systemu wtyczek
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class PluginStatus(Enum):
    READY = "ready"
    NOT_CONFIGURED = "not_configured"
    ERROR = "error"


@dataclass
class PluginResult:
    """Wynik wykonania pluginu"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    source: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "source": self.source,
            "timestamp": self.timestamp
        }


class BasePlugin(ABC):
    """Bazowa klasa dla wszystkich wtyczek"""
    
    name: str = "Base Plugin"
    description: str = "Base plugin class"
    icon: str = "🔌"
    category: str = "general"
    requires_api_key: bool = False
    api_key_env: Optional[str] = None
    
    def __init__(self):
        self._api_key: Optional[str] = None
        if self.api_key_env:
            self._api_key = os.getenv(self.api_key_env)
    
    @property
    def status(self) -> PluginStatus:
        """Sprawdza status pluginu"""
        if self.requires_api_key and not self._api_key:
            return PluginStatus.NOT_CONFIGURED
        return PluginStatus.READY
    
    def is_configured(self) -> bool:
        """Czy plugin jest skonfigurowany"""
        return self.status == PluginStatus.READY
    
    def configure(self, api_key: str):
        """Konfiguruje plugin z API key"""
        self._api_key = api_key
    
    @abstractmethod
    async def execute(self, **kwargs) -> PluginResult:
        """Wykonuje akcję pluginu"""
        pass
    
    def get_info(self) -> Dict[str, Any]:
        """Zwraca informacje o pluginie"""
        return {
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "category": self.category,
            "requires_api_key": self.requires_api_key,
            "api_key_env": self.api_key_env,
            "status": self.status.value,
            "is_configured": self.is_configured()
        }


class PluginManager:
    """Manager wtyczek"""
    
    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}
    
    def register(self, plugin_id: str, plugin: BasePlugin):
        """Rejestruje plugin"""
        self._plugins[plugin_id] = plugin
    
    def get(self, plugin_id: str) -> Optional[BasePlugin]:
        """Pobiera plugin"""
        return self._plugins.get(plugin_id)
    
    def list_all(self) -> List[Dict[str, Any]]:
        """Lista wszystkich pluginów"""
        return [
            {"id": pid, **plugin.get_info()}
            for pid, plugin in self._plugins.items()
        ]
    
    def get_configured(self) -> List[BasePlugin]:
        """Zwraca skonfigurowane pluginy"""
        return [p for p in self._plugins.values() if p.is_configured()]


# Globalny manager
plugin_manager = PluginManager()


def get_plugin_manager() -> PluginManager:
    return plugin_manager

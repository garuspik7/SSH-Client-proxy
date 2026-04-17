"""Менеджер управления всеми туннелями."""

import logging
import threading
from typing import Dict, List, Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor

from .config import AppConfig, TunnelConfig, Settings
from .tunnel import Tunnel, TunnelStatus


logger = logging.getLogger(__name__)


class TunnelManager:
    """Менеджер для управления множеством SSH туннелей."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.settings = config.settings
        self.tunnels: Dict[str, Tunnel] = {}
        
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=10)
        
        # Callbacks
        self.on_tunnel_status_change: Optional[Callable[[str, TunnelStatus], None]] = None
        self.on_tunnel_error: Optional[Callable[[str, str], None]] = None
        
        # Инициализируем туннели из конфигурации
        self._init_tunnels()

    def _init_tunnels(self) -> None:
        """Инициализирует туннели из конфигурации."""
        for tunnel_config in self.config.tunnels:
            tunnel = Tunnel(tunnel_config, self.settings)
            tunnel.on_status_change = self._on_status_change
            tunnel.on_error = self._on_error
            self.tunnels[tunnel_config.id] = tunnel
            logger.debug(f"Initialized tunnel: {tunnel_config.name}")

    def _on_status_change(self, tunnel_id: str, status: TunnelStatus) -> None:
        """Обработчик изменения статуса туннеля."""
        logger.info(f"Tunnel {tunnel_id} status changed to {status.value}")
        
        if self.on_tunnel_status_change:
            try:
                self.on_tunnel_status_change(tunnel_id, status)
            except Exception as e:
                logger.error(f"Error in tunnel status change callback: {e}")

    def _on_error(self, tunnel_id: str, error_message: str) -> None:
        """Обработчик ошибок туннеля."""
        logger.error(f"Tunnel {tunnel_id} error: {error_message}")
        
        if self.on_tunnel_error:
            try:
                self.on_tunnel_error(tunnel_id, error_message)
            except Exception as e:
                logger.error(f"Error in tunnel error callback: {e}")

    def start_all(self) -> Dict[str, bool]:
        """Запускает все включенные туннели."""
        results = {}
        
        with self._lock:
            for tunnel_id, tunnel in self.tunnels.items():
                if tunnel.config.enabled:
                    logger.info(f"Starting tunnel: {tunnel.name}")
                    future = self._executor.submit(tunnel.start)
                    results[tunnel_id] = future.result(timeout=30)
                else:
                    results[tunnel_id] = False
                    logger.debug(f"Skipping disabled tunnel: {tunnel.name}")
        
        return results

    def stop_all(self) -> None:
        """Останавливает все туннели."""
        with self._lock:
            for tunnel_id, tunnel in self.tunnels.items():
                logger.info(f"Stopping tunnel: {tunnel.name}")
                tunnel.stop()

    def start_tunnel(self, tunnel_id: str) -> bool:
        """Запускает конкретный туннель."""
        with self._lock:
            if tunnel_id not in self.tunnels:
                logger.error(f"Tunnel {tunnel_id} not found")
                return False
            
            tunnel = self.tunnels[tunnel_id]
            return tunnel.start()

    def stop_tunnel(self, tunnel_id: str) -> None:
        """Останавливает конкретный туннель."""
        with self._lock:
            if tunnel_id not in self.tunnels:
                logger.error(f"Tunnel {tunnel_id} not found")
                return
            
            tunnel = self.tunnels[tunnel_id]
            tunnel.stop()

    def restart_tunnel(self, tunnel_id: str) -> bool:
        """Перезапускает конкретный туннель."""
        with self._lock:
            if tunnel_id not in self.tunnels:
                logger.error(f"Tunnel {tunnel_id} not found")
                return False
            
            tunnel = self.tunnels[tunnel_id]
            return tunnel.restart()

    def get_tunnel_status(self, tunnel_id: str) -> Optional[TunnelStatus]:
        """Возвращает статус конкретного туннеля."""
        with self._lock:
            if tunnel_id not in self.tunnels:
                return None
            
            return self.tunnels[tunnel_id].get_status()

    def get_all_statuses(self) -> Dict[str, TunnelStatus]:
        """Возвращает статусы всех туннелей."""
        statuses = {}
        with self._lock:
            for tunnel_id, tunnel in self.tunnels.items():
                statuses[tunnel_id] = tunnel.get_status()
        return statuses

    def get_tunnel_info(self, tunnel_id: str) -> Optional[Dict[str, Any]]:
        """Возвращает информацию о туннеле."""
        with self._lock:
            if tunnel_id not in self.tunnels:
                return None
            
            return self.tunnels[tunnel_id].get_info()

    def get_all_info(self) -> List[Dict[str, Any]]:
        """Возвращает информацию обо всех туннелях."""
        info_list = []
        with self._lock:
            for tunnel in self.tunnels.values():
                info_list.append(tunnel.get_info())
        return info_list

    def get_enabled_tunnels(self) -> List[str]:
        """Возвращает список ID включенных туннелей."""
        return [
            tunnel_id for tunnel_id, tunnel in self.tunnels.items()
            if tunnel.config.enabled
        ]

    def get_disabled_tunnels(self) -> List[str]:
        """Возвращает список ID отключенных туннелей."""
        return [
            tunnel_id for tunnel_id, tunnel in self.tunnels.items()
            if not tunnel.config.enabled
        ]

    def add_tunnel(self, config: TunnelConfig) -> bool:
        """Добавляет новый туннель."""
        with self._lock:
            if config.id in self.tunnels:
                logger.error(f"Tunnel {config.id} already exists")
                return False
            
            tunnel = Tunnel(config, self.settings)
            tunnel.on_status_change = self._on_status_change
            tunnel.on_error = self._on_error
            self.tunnels[config.id] = tunnel
            logger.info(f"Added tunnel: {config.name}")
            return True

    def remove_tunnel(self, tunnel_id: str) -> bool:
        """Удаляет туннель."""
        with self._lock:
            if tunnel_id not in self.tunnels:
                logger.error(f"Tunnel {tunnel_id} not found")
                return False
            
            tunnel = self.tunnels[tunnel_id]
            tunnel.stop()
            del self.tunnels[tunnel_id]
            logger.info(f"Removed tunnel: {tunnel_id}")
            return True

    def enable_tunnel(self, tunnel_id: str) -> bool:
        """Включает туннель."""
        with self._lock:
            if tunnel_id not in self.tunnels:
                return False
            
            self.tunnels[tunnel_id].config.enabled = True
            logger.info(f"Enabled tunnel: {tunnel_id}")
            return True

    def disable_tunnel(self, tunnel_id: str) -> bool:
        """Отключает туннель."""
        with self._lock:
            if tunnel_id not in self.tunnels:
                return False
            
            self.tunnels[tunnel_id].config.enabled = False
            if self.tunnels[tunnel_id].get_status() != TunnelStatus.STOPPED:
                self.tunnels[tunnel_id].stop()
            logger.info(f"Disabled tunnel: {tunnel_id}")
            return True

    def shutdown(self) -> None:
        """Корректно завершает работу менеджера."""
        logger.info("Shutting down tunnel manager...")
        self.stop_all()
        self._executor.shutdown(wait=True)
        logger.info("Tunnel manager shut down complete")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()

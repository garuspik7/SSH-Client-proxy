"""Модуль управления SSH туннелями."""

import logging
import threading
import time
from typing import Optional, Callable, Dict, Any
from enum import Enum
from sshtunnel import SSHTunnelForwarder

from .config import TunnelConfig, Settings
from .ssh_client import SSHConnection


logger = logging.getLogger(__name__)


class TunnelStatus(Enum):
    """Статусы туннеля."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    RECONNECTING = "reconnecting"


class Tunnel:
    """Класс для управления отдельным SSH туннелем."""

    def __init__(self, config: TunnelConfig, settings: Settings):
        self.config = config
        self.settings = settings
        self.tunnel_id = config.id
        self.name = config.name
        
        self.status = TunnelStatus.STOPPED
        self.ssh_connection: Optional[SSHConnection] = None
        self.tunnel_forwarder: Optional[SSHTunnelForwarder] = None
        self.proxy_server = None
        
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._reconnect_attempts = 0
        
        # Callbacks
        self.on_status_change: Optional[Callable[[str, TunnelStatus], None]] = None
        self.on_error: Optional[Callable[[str, str], None]] = None

    def start(self) -> bool:
        """Запускает туннель."""
        if self.status in [TunnelStatus.RUNNING, TunnelStatus.STARTING]:
            logger.warning(f"Tunnel {self.name} is already running")
            return True

        logger.info(f"Starting tunnel: {self.name}")
        self._set_status(TunnelStatus.STARTING)
        
        try:
            # Создаем SSH подключение
            self.ssh_connection = SSHConnection(
                host=self.config.ssh.host,
                port=self.config.ssh.port,
                username=self.config.ssh.username,
                password=self.config.ssh.password,
                private_key=self.config.ssh.private_key,
                passphrase=self.config.ssh.passphrase,
                known_hosts_file=self.settings.known_hosts_file,
                timeout=self.settings.timeout
            )
            
            # Подключаемся
            if not self.ssh_connection.connect():
                self._set_status(TunnelStatus.ERROR)
                self._report_error("Failed to connect to SSH server")
                return False
            
            # Создаем туннель
            self.tunnel_forwarder = SSHTunnelForwarder(
                (self.config.ssh.host, self.config.ssh.port),
                ssh_username=self.config.ssh.username,
                ssh_password=self.config.ssh.password if not self.config.ssh.private_key else None,
                ssh_pkey=self.config.ssh.private_key if self.config.ssh.private_key and 
                    os.path.exists(self.config.ssh.private_key) else None,
                ssh_private_key_password=self.config.ssh.passphrase,
                remote_bind_address=(
                    self.config.forwarding.remote_host,
                    self.config.forwarding.remote_port
                ),
                local_bind_address=('127.0.0.1', self.config.forwarding.local_port),
                logger=logger
            )
            
            # Запускаем туннель
            self.tunnel_forwarder.start()
            
            logger.info(
                f"Tunnel {self.name} started: "
                f"127.0.0.1:{self.config.forwarding.local_port} -> "
                f"{self.config.forwarding.remote_host}:{self.config.forwarding.remote_port}"
            )
            
            self._reconnect_attempts = 0
            self._set_status(TunnelStatus.RUNNING)
            
            # Запускаем мониторинг в отдельном потоке
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting tunnel {self.name}: {e}")
            self._set_status(TunnelStatus.ERROR)
            self._report_error(str(e))
            self.stop()
            return False

    def stop(self) -> None:
        """Останавливает туннель."""
        if self.status == TunnelStatus.STOPPED:
            return

        logger.info(f"Stopping tunnel: {self.name}")
        self._set_status(TunnelStatus.STOPPING)
        
        self._stop_event.set()
        
        # Останавливаем прокси сервер
        if self.proxy_server:
            try:
                self.proxy_server.stop()
            except Exception as e:
                logger.warning(f"Error stopping proxy for {self.name}: {e}")
            finally:
                self.proxy_server = None
        
        # Останавливаем туннель
        if self.tunnel_forwarder:
            try:
                self.tunnel_forwarder.stop()
            except Exception as e:
                logger.warning(f"Error stopping tunnel forwarder for {self.name}: {e}")
            finally:
                self.tunnel_forwarder = None
        
        # Отключаемся от SSH
        if self.ssh_connection:
            self.ssh_connection.disconnect()
            self.ssh_connection = None
        
        self._set_status(TunnelStatus.STOPPED)
        logger.info(f"Tunnel {self.name} stopped")

    def restart(self) -> bool:
        """Перезапускает туннель."""
        self.stop()
        time.sleep(1)
        return self.start()

    def get_status(self) -> TunnelStatus:
        """Возвращает текущий статус туннеля."""
        return self.status

    def get_info(self) -> Dict[str, Any]:
        """Возвращает информацию о туннеле."""
        return {
            'id': self.tunnel_id,
            'name': self.name,
            'status': self.status.value,
            'local_port': self.config.forwarding.local_port,
            'remote_host': self.config.forwarding.remote_host,
            'remote_port': self.config.forwarding.remote_port,
            'proxy_type': self.config.proxy.type if self.config.proxy.enabled else None,
            'proxy_port': self.config.proxy.port if self.config.proxy.enabled else None,
            'reconnect_attempts': self._reconnect_attempts
        }

    def _set_status(self, status: TunnelStatus) -> None:
        """Устанавливает статус и уведомляет callback."""
        old_status = self.status
        self.status = status
        
        if self.on_status_change:
            try:
                self.on_status_change(self.tunnel_id, status)
            except Exception as e:
                logger.error(f"Error in status change callback: {e}")

    def _report_error(self, error_message: str) -> None:
        """Сообщает об ошибке через callback."""
        if self.on_error:
            try:
                self.on_error(self.tunnel_id, error_message)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")

    def _monitor_loop(self) -> None:
        """Мониторинг состояния туннеля и авто-переподключение."""
        while not self._stop_event.is_set():
            try:
                # Проверяем состояние туннеля
                if self.status == TunnelStatus.RUNNING:
                    is_active = self._check_tunnel_health()
                    
                    if not is_active:
                        logger.warning(f"Tunnel {self.name} connection lost")
                        
                        if self.settings.auto_reconnect:
                            self._handle_reconnect()
                        else:
                            self._set_status(TunnelStatus.ERROR)
                            self._report_error("Connection lost and auto-reconnect is disabled")
                            break
                
                time.sleep(5)  # Проверка каждые 5 секунд
                
            except Exception as e:
                logger.error(f"Error in monitor loop for {self.name}: {e}")
                time.sleep(5)

    def _check_tunnel_health(self) -> bool:
        """Проверяет здоровье туннеля."""
        try:
            if not self.tunnel_forwarder:
                return False
            
            # Проверяем активность туннеля
            if not self.tunnel_forwarder.is_active:
                return False
            
            # Проверяем SSH подключение
            if self.ssh_connection and not self.ssh_connection.is_connected():
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Health check failed for {self.name}: {e}")
            return False

    def _handle_reconnect(self) -> None:
        """Обрабатывает переподключение."""
        self._set_status(TunnelStatus.RECONNECTING)
        
        while self._reconnect_attempts < self.settings.max_reconnect_attempts:
            if self._stop_event.is_set():
                break
            
            self._reconnect_attempts += 1
            logger.info(
                f"Attempting to reconnect {self.name} "
                f"(attempt {self._reconnect_attempts}/{self.settings.max_reconnect_attempts})"
            )
            
            try:
                # Пробуем переподключиться
                if self.restart():
                    logger.info(f"Successfully reconnected {self.name}")
                    return
            except Exception as e:
                logger.error(f"Reconnection attempt failed for {self.name}: {e}")
            
            # Ждем перед следующей попыткой
            wait_time = min(
                self.settings.reconnect_delay * self._reconnect_attempts,
                60  # Максимум 60 секунд
            )
            
            if not self._stop_event.wait(wait_time):
                continue
        
        # Все попытки исчерпаны
        self._set_status(TunnelStatus.ERROR)
        self._report_error(
            f"Max reconnection attempts ({self.settings.max_reconnect_attempts}) exceeded"
        )


# Импортируем os для проверки существования файла ключа
import os

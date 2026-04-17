"""Модуль конфигурации для SSH Tunnel Manager."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class SSHConfig:
    """Конфигурация SSH подключения."""
    host: str
    port: int = 22
    username: str = ""
    password: Optional[str] = None
    private_key: Optional[str] = None
    passphrase: Optional[str] = None

    def __post_init__(self):
        if self.private_key:
            self.private_key = os.path.expanduser(self.private_key)


@dataclass
class ForwardingConfig:
    """Конфигурация проброса портов."""
    local_port: int
    remote_host: str = "localhost"
    remote_port: int = 80


@dataclass
class ProxyConfig:
    """Конфигурация прокси сервера."""
    type: str = "socks5"  # socks5 или http
    enabled: bool = True
    port: Optional[int] = None


@dataclass
class TunnelConfig:
    """Конфигурация одного туннеля."""
    id: str
    name: str
    enabled: bool = True
    ssh: SSHConfig = field(default_factory=lambda: SSHConfig(host=""))
    forwarding: ForwardingConfig = field(default_factory=lambda: ForwardingConfig(local_port=8080))
    proxy: ProxyConfig = field(default_factory=ProxyConfig)


@dataclass
class Settings:
    """Общие настройки приложения."""
    log_level: str = "INFO"
    log_file: str = "logs/tunnels.log"
    auto_reconnect: bool = True
    reconnect_delay: int = 5
    max_reconnect_attempts: int = 10
    known_hosts_file: str = "~/.ssh/known_hosts"
    timeout: int = 30

    def __post_init__(self):
        self.log_file = os.path.expanduser(self.log_file)
        self.known_hosts_file = os.path.expanduser(self.known_hosts_file)


@dataclass
class AppConfig:
    """Основная конфигурация приложения."""
    tunnels: List[TunnelConfig] = field(default_factory=list)
    settings: Settings = field(default_factory=Settings)


class ConfigLoader:
    """Загрузчик конфигурации из JSON файла."""

    @staticmethod
    def load(config_path: str) -> AppConfig:
        """Загружает конфигурацию из JSON файла."""
        config_path = os.path.expanduser(config_path)
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return ConfigLoader._parse_config(data)

    @staticmethod
    def _parse_config(data: Dict[str, Any]) -> AppConfig:
        """Парсит данные конфигурации."""
        tunnels = []
        for tunnel_data in data.get('tunnels', []):
            tunnel = ConfigLoader._parse_tunnel(tunnel_data)
            tunnels.append(tunnel)

        settings_data = data.get('settings', {})
        settings = Settings(
            log_level=settings_data.get('log_level', 'INFO'),
            log_file=settings_data.get('log_file', 'logs/tunnels.log'),
            auto_reconnect=settings_data.get('auto_reconnect', True),
            reconnect_delay=settings_data.get('reconnect_delay', 5),
            max_reconnect_attempts=settings_data.get('max_reconnect_attempts', 10),
            known_hosts_file=settings_data.get('known_hosts_file', '~/.ssh/known_hosts'),
            timeout=settings_data.get('timeout', 30)
        )

        return AppConfig(tunnels=tunnels, settings=settings)

    @staticmethod
    def _parse_tunnel(data: Dict[str, Any]) -> TunnelConfig:
        """Парсит конфигурацию туннеля."""
        ssh_data = data.get('ssh', {})
        ssh = SSHConfig(
            host=ssh_data.get('host', ''),
            port=ssh_data.get('port', 22),
            username=ssh_data.get('username', ''),
            password=ssh_data.get('password'),
            private_key=ssh_data.get('private_key'),
            passphrase=ssh_data.get('passphrase')
        )

        forwarding_data = data.get('forwarding', {})
        forwarding = ForwardingConfig(
            local_port=forwarding_data.get('local_port', 8080),
            remote_host=forwarding_data.get('remote_host', 'localhost'),
            remote_port=forwarding_data.get('remote_port', 80)
        )

        proxy_data = data.get('proxy', {})
        proxy = ProxyConfig(
            type=proxy_data.get('type', 'socks5'),
            enabled=proxy_data.get('enabled', True),
            port=proxy_data.get('port')
        )

        return TunnelConfig(
            id=data.get('id', ''),
            name=data.get('name', 'Unnamed Tunnel'),
            enabled=data.get('enabled', True),
            ssh=ssh,
            forwarding=forwarding,
            proxy=proxy
        )

    @staticmethod
    def save(config: AppConfig, config_path: str) -> None:
        """Сохраняет конфигурацию в JSON файл."""
        config_path = os.path.expanduser(config_path)
        
        data = {
            'tunnels': [ConfigLoader._serialize_tunnel(t) for t in config.tunnels],
            'settings': {
                'log_level': config.settings.log_level,
                'log_file': config.settings.log_file,
                'auto_reconnect': config.settings.auto_reconnect,
                'reconnect_delay': config.settings.reconnect_delay,
                'max_reconnect_attempts': config.settings.max_reconnect_attempts,
                'known_hosts_file': config.settings.known_hosts_file,
                'timeout': config.settings.timeout
            }
        }

        # Создаем директорию если не существует
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _serialize_tunnel(tunnel: TunnelConfig) -> Dict[str, Any]:
        """Сериализует конфигурацию туннеля."""
        return {
            'id': tunnel.id,
            'name': tunnel.name,
            'enabled': tunnel.enabled,
            'ssh': {
                'host': tunnel.ssh.host,
                'port': tunnel.ssh.port,
                'username': tunnel.ssh.username,
                'password': tunnel.ssh.password,
                'private_key': tunnel.ssh.private_key,
                'passphrase': tunnel.ssh.passphrase
            },
            'forwarding': {
                'local_port': tunnel.forwarding.local_port,
                'remote_host': tunnel.forwarding.remote_host,
                'remote_port': tunnel.forwarding.remote_port
            },
            'proxy': {
                'type': tunnel.proxy.type,
                'enabled': tunnel.proxy.enabled,
                'port': tunnel.proxy.port
            }
        }

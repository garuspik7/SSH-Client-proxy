"""SSH клиент для управления подключениями."""

import logging
import os
from typing import Optional, Callable
from paramiko import SSHClient, AutoAddPolicy, RejectPolicy, AuthenticationException, SSHException


logger = logging.getLogger(__name__)


class SSHConnection:
    """Класс для управления SSH подключением."""

    def __init__(
        self,
        host: str,
        port: int = 22,
        username: str = "",
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        passphrase: Optional[str] = None,
        known_hosts_file: Optional[str] = None,
        timeout: int = 30
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key = private_key
        self.passphrase = passphrase
        self.known_hosts_file = os.path.expanduser(known_hosts_file) if known_hosts_file else None
        self.timeout = timeout
        
        self.client: Optional[SSHClient] = None
        self.connected = False

    def connect(self) -> bool:
        """Устанавливает SSH подключение."""
        try:
            self.client = SSHClient()
            
            # Настройка проверки хостов
            if self.known_hosts_file and os.path.exists(self.known_hosts_file):
                self.client.load_host_keys(self.known_hosts_file)
                self.client.set_missing_host_key_policy(RejectPolicy())
            else:
                # Если файл known_hosts не существует, создаем его и принимаем ключи
                if self.known_hosts_file:
                    os.makedirs(os.path.dirname(self.known_hosts_file), exist_ok=True)
                    open(self.known_hosts_file, 'a').close()
                    self.client.load_host_keys(self.known_hosts_file)
                self.client.set_missing_host_key_policy(AutoAddPolicy())
            
            # Подготовка ключа аутентификации
            pkey = None
            if self.private_key and os.path.exists(self.private_key):
                key_types = [
                    ('rsa', lambda k, p: k.from_private_key_file(k, password=p)),
                    ('dsa', lambda k, p: k.from_private_key_file(k, password=p)),
                    ('ecdsa', lambda k, p: k.from_private_key_file(k, password=p)),
                    ('ed25519', lambda k, p: k.from_private_key_file(k, password=p))
                ]
                
                for key_name, loader in key_types:
                    try:
                        from paramiko import RSAKey, DSSKey, ECDSAKey, Ed25519Key
                        key_class = {
                            'rsa': RSAKey,
                            'dsa': DSSKey,
                            'ecdsa': ECDSAKey,
                            'ed25519': Ed25519Key
                        }[key_name]
                        pkey = loader(key_class, self.passphrase)
                        logger.debug(f"Loaded {key_name} key: {self.private_key}")
                        break
                    except (SSHException, FileNotFoundError):
                        continue
            
            # Подключение
            logger.info(f"Connecting to {self.host}:{self.port} as {self.username}")
            
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password if not pkey else None,
                pkey=pkey,
                passphrase=self.passphrase if pkey else None,
                timeout=self.timeout,
                allow_agent=True,
                look_for_keys=True
            )
            
            self.connected = True
            logger.info(f"Successfully connected to {self.host}:{self.port}")
            return True
            
        except AuthenticationException as e:
            logger.error(f"Authentication failed for {self.host}: {e}")
            self.connected = False
            return False
        except SSHException as e:
            logger.error(f"SSH error connecting to {self.host}: {e}")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to {self.host}: {e}")
            self.connected = False
            return False

    def disconnect(self) -> None:
        """Закрывает SSH подключение."""
        if self.client:
            try:
                self.client.close()
                logger.info(f"Disconnected from {self.host}")
            except Exception as e:
                logger.warning(f"Error disconnecting from {self.host}: {e}")
            finally:
                self.client = None
                self.connected = False

    def get_client(self) -> Optional[SSHClient]:
        """Возвращает SSH клиент."""
        return self.client

    def is_connected(self) -> bool:
        """Проверяет статус подключения."""
        if not self.client:
            return False
        try:
            transport = self.client.get_transport()
            return transport is not None and transport.is_active()
        except Exception:
            return False

    def test_connection(self) -> bool:
        """Тестирует подключение без установления соединения."""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.error(f"Connection test failed for {self.host}:{self.port}: {e}")
            return False

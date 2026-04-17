"""Модуль прокси серверов (SOCKS5 и HTTP)."""

import logging
import socket
import threading
import struct
from typing import Optional, Dict, Any
from enum import Enum


logger = logging.getLogger(__name__)


class ProxyType(Enum):
    """Типы прокси серверов."""
    SOCKS5 = "socks5"
    HTTP = "http"


class SOCKS5Server:
    """SOCKS5 прокси сервер."""

    def __init__(self, host: str = '127.0.0.1', port: int = 1080, 
                 remote_host: str = 'localhost', remote_port: int = 80):
        self.host = host
        self.port = port
        self.remote_host = remote_host
        self.remote_port = remote_port
        
        self.server_socket: Optional[socket.socket] = None
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._clients: list = []

    def start(self) -> bool:
        """Запускает SOCKS5 сервер."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)
            
            self.running = True
            self._thread = threading.Thread(target=self._accept_loop, daemon=True)
            self._thread.start()
            
            logger.info(f"SOCKS5 proxy started on {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start SOCKS5 proxy: {e}")
            return False

    def stop(self) -> None:
        """Останавливает SOCKS5 сервер."""
        self.running = False
        
        # Закрываем клиентские соединения
        for client in self._clients[:]:
            try:
                client.close()
            except:
                pass
        self._clients.clear()
        
        # Закрываем серверный сокет
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
        
        logger.info("SOCKS5 proxy stopped")

    def _accept_loop(self) -> None:
        """Цикл принятия соединений."""
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                self._clients.append(client_socket)
                
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, addr),
                    daemon=True
                )
                client_thread.start()
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Error accepting connection: {e}")
                break

    def _handle_client(self, client_socket: socket.socket, addr: tuple) -> None:
        """Обрабатывает клиентское соединение."""
        try:
            # Читаем приветствие
            greeting = client_socket.recv(2)
            if len(greeting) < 2 or greeting[0] != 0x05:
                client_socket.close()
                return
            
            # Читаем методы аутентификации
            nmethods = greeting[1]
            methods = client_socket.recv(nmethods)
            
            # Отправляем ответ (без аутентификации)
            client_socket.sendall(b'\x05\x00')
            
            # Читаем запрос
            request = client_socket.recv(4)
            if len(request) < 4:
                client_socket.close()
                return
            
            version, cmd, rsv, atype = request
            
            if version != 0x05:
                client_socket.close()
                return
            
            # Определяем адрес назначения
            dest_addr = None
            dest_port = None
            
            if atype == 0x01:  # IPv4
                dest_addr = socket.inet_ntoa(client_socket.recv(4))
                dest_port = struct.unpack('>H', client_socket.recv(2))[0]
            elif atype == 0x03:  # Domain name
                domain_len = client_socket.recv(1)[0]
                dest_addr = client_socket.recv(domain_len).decode('utf-8')
                dest_port = struct.unpack('>H', client_socket.recv(2))[0]
            elif atype == 0x04:  # IPv6
                dest_addr = socket.inet_ntop(socket.AF_INET6, client_socket.recv(16))
                dest_port = struct.unpack('>H', client_socket.recv(2))[0]
            else:
                client_socket.close()
                return
            
            logger.debug(f"SOCKS5 request: {dest_addr}:{dest_port} (cmd={cmd})")
            
            # CONNECT команда (0x01)
            if cmd == 0x01:
                # Подключаемся к удаленному хосту через SSH туннель
                # В данном случае мы просто перенаправляем на настроенный remote_host:remote_port
                try:
                    # Создаем соединение с целевым хостом
                    target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    target_socket.connect((self.remote_host, self.remote_port))
                    
                    # Отправляем успех
                    response = b'\x05\x00\x00\x01' + socket.inet_aton('0.0.0.0') + struct.pack('>H', 0)
                    client_socket.sendall(response)
                    
                    # Пересылаем данные в обе стороны
                    self._relay_data(client_socket, target_socket)
                    
                except Exception as e:
                    logger.error(f"Failed to connect to target: {e}")
                    response = b'\x05\x01\x00\x01' + socket.inet_aton('0.0.0.0') + struct.pack('>H', 0)
                    client_socket.sendall(response)
            else:
                # Другие команды не поддерживаются
                response = b'\x05\x07\x00\x01' + socket.inet_aton('0.0.0.0') + struct.pack('>H', 0)
                client_socket.sendall(response)
            
        except Exception as e:
            logger.error(f"Error handling SOCKS5 client: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
            if client_socket in self._clients:
                self._clients.remove(client_socket)

    def _relay_data(self, client: socket.socket, target: socket.socket) -> None:
        """Пересылает данные между сокетами."""
        client.setblocking(False)
        target.setblocking(False)
        
        while self.running:
            try:
                # Client -> Target
                try:
                    data = client.recv(4096)
                    if data:
                        target.sendall(data)
                    elif not data:
                        break
                except BlockingIOError:
                    pass
                
                # Target -> Client
                try:
                    data = target.recv(4096)
                    if data:
                        client.sendall(data)
                    elif not data:
                        break
                except BlockingIOError:
                    pass
                    
            except Exception as e:
                logger.debug(f"Relay error: {e}")
                break
            
            threading.Event().wait(0.01)
        
        client.close()
        target.close()


class HTTPProxyServer:
    """HTTP прокси сервер."""

    def __init__(self, host: str = '127.0.0.1', port: int = 8080,
                 remote_host: str = 'localhost', remote_port: int = 80):
        self.host = host
        self.port = port
        self.remote_host = remote_host
        self.remote_port = remote_port
        
        self.server_socket: Optional[socket.socket] = None
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._clients: list = []

    def start(self) -> bool:
        """Запускает HTTP прокси сервер."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)
            
            self.running = True
            self._thread = threading.Thread(target=self._accept_loop, daemon=True)
            self._thread.start()
            
            logger.info(f"HTTP proxy started on {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start HTTP proxy: {e}")
            return False

    def stop(self) -> None:
        """Останавливает HTTP прокси сервер."""
        self.running = False
        
        for client in self._clients[:]:
            try:
                client.close()
            except:
                pass
        self._clients.clear()
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
        
        logger.info("HTTP proxy stopped")

    def _accept_loop(self) -> None:
        """Цикл принятия соединений."""
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                self._clients.append(client_socket)
                
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, addr),
                    daemon=True
                )
                client_thread.start()
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Error accepting connection: {e}")
                break

    def _handle_client(self, client_socket: socket.socket, addr: tuple) -> None:
        """Обрабатывает клиентское соединение."""
        try:
            request = client_socket.recv(4096).decode('utf-8', errors='ignore')
            
            if not request:
                return
            
            lines = request.split('\r\n')
            if not lines:
                return
            
            method_line = lines[0].split(' ')
            if len(method_line) < 3:
                return
            
            method = method_line[0]
            
            logger.debug(f"HTTP {method} request from {addr}")
            
            if method == 'CONNECT':
                # HTTPS проксирование
                self._handle_connect(client_socket, method_line, lines)
            else:
                # HTTP проксирование
                self._handle_http(client_socket, request)
                
        except Exception as e:
            logger.error(f"Error handling HTTP client: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
            if client_socket in self._clients:
                self._clients.remove(client_socket)

    def _handle_connect(self, client_socket: socket.socket, 
                       method_line: list, lines: list) -> None:
        """Обрабатывает CONNECT запрос."""
        try:
            # Парсим адрес
            target = method_line[1]
            if ':' in target:
                host, port = target.rsplit(':', 1)
                port = int(port)
            else:
                host = target
                port = 80
            
            logger.debug(f"HTTP CONNECT to {host}:{port}")
            
            # Подключаемся к целевому хосту
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_socket.connect((self.remote_host, self.remote_port))
            
            # Отправляем успех
            client_socket.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            
            # Пересылаем данные
            self._relay_data(client_socket, target_socket)
            
        except Exception as e:
            logger.error(f"CONNECT failed: {e}")
            client_socket.sendall(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')

    def _handle_http(self, client_socket: socket.socket, request: str) -> None:
        """Обрабатывает HTTP запрос."""
        try:
            # Для простоты пересылаем запрос на удаленный сервер
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_socket.connect((self.remote_host, self.remote_port))
            target_socket.sendall(request.encode('utf-8'))
            
            # Читаем ответ
            response = target_socket.recv(4096)
            client_socket.sendall(response)
            
            target_socket.close()
            
        except Exception as e:
            logger.error(f"HTTP request failed: {e}")
            client_socket.sendall(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')

    def _relay_data(self, client: socket.socket, target: socket.socket) -> None:
        """Пересылает данные между сокетами."""
        client.setblocking(False)
        target.setblocking(False)
        
        while self.running:
            try:
                # Client -> Target
                try:
                    data = client.recv(4096)
                    if data:
                        target.sendall(data)
                    elif not data:
                        break
                except BlockingIOError:
                    pass
                
                # Target -> Client
                try:
                    data = target.recv(4096)
                    if data:
                        client.sendall(data)
                    elif not data:
                        break
                except BlockingIOError:
                    pass
                    
            except Exception as e:
                logger.debug(f"Relay error: {e}")
                break
            
            threading.Event().wait(0.01)
        
        client.close()
        target.close()


class ProxyManager:
    """Менеджер прокси серверов."""

    @staticmethod
    def create_proxy(proxy_type: str, host: str, port: int,
                    remote_host: str, remote_port: int):
        """Создает прокси сервер указанного типа."""
        if proxy_type.lower() == 'socks5':
            return SOCKS5Server(host, port, remote_host, remote_port)
        elif proxy_type.lower() == 'http':
            return HTTPProxyServer(host, port, remote_host, remote_port)
        else:
            raise ValueError(f"Unknown proxy type: {proxy_type}")

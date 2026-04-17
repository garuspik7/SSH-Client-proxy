"""Графический интерфейс для SSH Tunnel Manager."""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import logging
import sys
import threading
import os
from pathlib import Path
from typing import Optional, Dict

from .config import ConfigLoader, AppConfig, TunnelConfig, SSHConfig, ForwardingConfig, ProxyConfig
from .manager import TunnelManager
from .tunnel import TunnelStatus


class StatusIndicator(ttk.Frame):
    """Индикатор статуса туннеля."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.canvas = tk.Canvas(self, width=20, height=20, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, padx=5)
        
        self.indicator = self.canvas.create_oval(2, 2, 18, 18, fill='gray')
        
        self.status_colors = {
            'stopped': 'gray',
            'starting': 'yellow',
            'running': '#00ff00',
            'stopping': 'orange',
            'error': 'red',
            'reconnecting': 'cyan'
        }
    
    def set_status(self, status: str):
        """Устанавливает цвет индикатора по статусу."""
        color = self.status_colors.get(status.lower(), 'gray')
        self.canvas.itemconfig(self.indicator, fill=color)


class TunnelCard(ttk.Frame):
    """Карточка туннеля в интерфейсе."""
    
    def __init__(self, parent, tunnel_info: dict, on_start, on_stop, on_restart, on_edit, on_delete):
        super().__init__(parent, padding=10)
        self.configure(relief=tk.RAISED, borderwidth=1)
        
        self.tunnel_id = tunnel_info['id']
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_restart = on_restart
        self.on_edit = on_edit
        self.on_delete = on_delete
        
        self._create_widgets(tunnel_info)
    
    def _create_widgets(self, info: dict):
        """Создает виджеты карточки."""
        # Верхняя строка с названием и статусом
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.status_indicator = StatusIndicator(top_frame)
        self.status_indicator.pack(side=tk.LEFT)
        
        name_label = ttk.Label(
            top_frame, 
            text=info['name'],
            font=('Arial', 12, 'bold')
        )
        name_label.pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        self.status_label = ttk.Label(
            top_frame,
            text=info['status'].upper(),
            font=('Arial', 9)
        )
        self.status_label.pack(side=tk.RIGHT)
        
        # Информация о туннеле
        info_frame = ttk.Frame(self)
        info_frame.pack(fill=tk.X, pady=5)
        
        forwarding_text = f"📍 {info['local_port']} → {info['remote_host']}:{info['remote_port']}"
        ttk.Label(info_frame, text=forwarding_text).pack(anchor=tk.W)
        
        if info.get('proxy_type'):
            proxy_text = f"🌐 {info['proxy_type'].upper()} proxy :{info['proxy_port']}"
            ttk.Label(info_frame, text=proxy_text, foreground='blue').pack(anchor=tk.W)
        
        # Кнопки управления
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.start_btn = ttk.Button(
            btn_frame, text="▶ Start", command=self._on_start, width=8
        )
        self.start_btn.pack(side=tk.LEFT, padx=2)
        
        self.stop_btn = ttk.Button(
            btn_frame, text="⏹ Stop", command=self._on_stop, width=8
        )
        self.stop_btn.pack(side=tk.LEFT, padx=2)
        
        self.restart_btn = ttk.Button(
            btn_frame, text="🔄 Restart", command=self._on_restart, width=10
        )
        self.restart_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            btn_frame, text="✏ Edit", command=self._on_edit, width=8
        ).pack(side=tk.RIGHT, padx=2)
        
        ttk.Button(
            btn_frame, text="🗑 Delete", command=self._on_delete, width=8
        ).pack(side=tk.RIGHT, padx=2)
        
        # Обновление состояния кнопок
        self._update_buttons(info['status'])
    
    def update_status(self, status: str):
        """Обновляет отображение статуса."""
        self.status_indicator.set_status(status)
        self.status_label.config(text=status.upper())
        self._update_buttons(status)
    
    def _update_buttons(self, status: str):
        """Обновляет состояние кнопок."""
        is_running = status.lower() in ['running', 'starting', 'reconnecting']
        self.start_btn.config(state=tk.DISABLED if is_running else tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL if is_running else tk.DISABLED)
    
    def _on_start(self):
        self.on_start(self.tunnel_id)
    
    def _on_stop(self):
        self.on_stop(self.tunnel_id)
    
    def _on_restart(self):
        self.on_restart(self.tunnel_id)
    
    def _on_edit(self):
        self.on_edit(self.tunnel_id)
    
    def _on_delete(self):
        if messagebox.askyesno("Confirm", "Delete this tunnel?"):
            self.on_delete(self.tunnel_id)


class TunnelDialog(tk.Toplevel):
    """Диалог создания/редактирования туннеля."""
    
    def __init__(self, parent, tunnel_data: Optional[dict] = None):
        super().__init__(parent)
        self.title("Edit Tunnel" if tunnel_data else "New Tunnel")
        self.geometry("600x700")
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        self.tunnel_data = tunnel_data
        
        self._create_widgets()
        
        if tunnel_data:
            self._populate_fields(tunnel_data)
        
        self.wait_window()
    
    def _create_widgets(self):
        """Создает виджеты диалога."""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Основное
        section = ttk.LabelFrame(main_frame, text="General", padding=10)
        section.pack(fill=tk.X, pady=5)
        
        ttk.Label(section, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(section, textvariable=self.name_var, width=40).grid(row=0, column=1, pady=5)
        
        ttk.Label(section, text="ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.id_var = tk.StringVar()
        ttk.Entry(section, textvariable=self.id_var, width=40).grid(row=1, column=1, pady=5)
        
        ttk.Label(section, text="Enabled:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(section, variable=self.enabled_var).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # SSH
        section = ttk.LabelFrame(main_frame, text="SSH Connection", padding=10)
        section.pack(fill=tk.X, pady=5)
        
        ttk.Label(section, text="Host:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.host_var = tk.StringVar()
        ttk.Entry(section, textvariable=self.host_var, width=40).grid(row=0, column=1, pady=5)
        
        ttk.Label(section, text="Port:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.port_var = tk.StringVar(value="22")
        ttk.Entry(section, textvariable=self.port_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(section, text="Username:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.username_var = tk.StringVar()
        ttk.Entry(section, textvariable=self.username_var, width=40).grid(row=2, column=1, pady=5)
        
        ttk.Label(section, text="Password:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.password_var = tk.StringVar()
        ttk.Entry(section, textvariable=self.password_var, show="*", width=40).grid(row=3, column=1, pady=5)
        
        ttk.Label(section, text="Private Key:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.key_var = tk.StringVar()
        key_frame = ttk.Frame(section)
        key_frame.grid(row=4, column=1, sticky=tk.W, pady=5)
        ttk.Entry(key_frame, textvariable=self.key_var, width=35).pack(side=tk.LEFT)
        ttk.Button(key_frame, text="Browse", command=self._browse_key).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(section, text="Passphrase:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.passphrase_var = tk.StringVar()
        ttk.Entry(section, textvariable=self.passphrase_var, show="*", width=40).grid(row=5, column=1, pady=5)
        
        # Forwarding
        section = ttk.LabelFrame(main_frame, text="Port Forwarding", padding=10)
        section.pack(fill=tk.X, pady=5)
        
        ttk.Label(section, text="Local Port:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.local_port_var = tk.StringVar()
        ttk.Entry(section, textvariable=self.local_port_var, width=10).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(section, text="Remote Host:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.remote_host_var = tk.StringVar(value="localhost")
        ttk.Entry(section, textvariable=self.remote_host_var, width=40).grid(row=1, column=1, pady=5)
        
        ttk.Label(section, text="Remote Port:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.remote_port_var = tk.StringVar()
        ttk.Entry(section, textvariable=self.remote_port_var, width=10).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Proxy
        section = ttk.LabelFrame(main_frame, text="Proxy Server", padding=10)
        section.pack(fill=tk.X, pady=5)
        
        self.proxy_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(section, text="Enable Proxy", variable=self.proxy_enabled_var).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Label(section, text="Type:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.proxy_type_var = tk.StringVar(value="socks5")
        proxy_combo = ttk.Combobox(section, textvariable=self.proxy_type_var, values=["socks5", "http"], width=15, state="readonly")
        proxy_combo.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(section, text="Port:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.proxy_port_var = tk.StringVar()
        ttk.Entry(section, textvariable=self.proxy_port_var, width=10).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Кнопки
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=20)
        
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
    
    def _browse_key(self):
        """Открывает диалог выбора файла ключа."""
        filename = filedialog.askopenfilename(
            title="Select Private Key",
            filetypes=[("All files", "*.*")]
        )
        if filename:
            self.key_var.set(filename)
    
    def _populate_fields(self, data: dict):
        """Заполняет поля данными туннеля."""
        self.name_var.set(data['name'])
        self.id_var.set(data['id'])
        self.enabled_var.set(True)  # По умолчанию включен
        
        ssh = data.get('ssh', {})
        self.host_var.set(ssh.get('host', ''))
        self.port_var.set(str(ssh.get('port', 22)))
        self.username_var.set(ssh.get('username', ''))
        self.password_var.set(ssh.get('password') or '')
        self.key_var.set(ssh.get('private_key') or '')
        self.passphrase_var.set(ssh.get('passphrase') or '')
        
        fwd = data.get('forwarding', {})
        self.local_port_var.set(str(fwd.get('local_port', 8080)))
        self.remote_host_var.set(fwd.get('remote_host', 'localhost'))
        self.remote_port_var.set(str(fwd.get('remote_port', 80)))
        
        proxy = data.get('proxy', {})
        self.proxy_enabled_var.set(proxy.get('enabled', False))
        self.proxy_type_var.set(proxy.get('type', 'socks5'))
        self.proxy_port_var.set(str(proxy.get('port') or 1080))
    
    def _save(self):
        """Сохраняет данные и закрывает диалог."""
        try:
            self.result = {
                'id': self.id_var.get().strip() or self.name_var.get().strip().lower().replace(' ', '_'),
                'name': self.name_var.get().strip(),
                'enabled': self.enabled_var.get(),
                'ssh': {
                    'host': self.host_var.get().strip(),
                    'port': int(self.port_var.get()),
                    'username': self.username_var.get().strip(),
                    'password': self.password_var.get() or None,
                    'private_key': self.key_var.get().strip() or None,
                    'passphrase': self.passphrase_var.get() or None
                },
                'forwarding': {
                    'local_port': int(self.local_port_var.get()),
                    'remote_host': self.remote_host_var.get().strip(),
                    'remote_port': int(self.remote_port_var.get())
                },
                'proxy': {
                    'type': self.proxy_type_var.get(),
                    'enabled': self.proxy_enabled_var.get(),
                    'port': int(self.proxy_port_var.get()) if self.proxy_enabled_var.get() else None
                }
            }
            
            # Валидация
            if not self.result['name'] or not self.result['ssh']['host']:
                messagebox.showerror("Error", "Name and Host are required")
                return
            
            self.destroy()
            
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid value: {e}")


class LogHandler(logging.Handler):
    """Обработчик логов для GUI."""
    
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.setLevel(logging.INFO)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.setFormatter(formatter)
    
    def emit(self, record):
        """Отправляет лог в текстовое поле."""
        msg = self.format(record)
        self.text_widget.insert(tk.END, msg + '\n')
        self.text_widget.see(tk.END)


class SSHManagerGUI:
    """Основной класс графического интерфейса."""
    
    def __init__(self, config_path: str = 'config/tunnels.json'):
        self.config_path = config_path
        self.config: Optional[AppConfig] = None
        self.manager: Optional[TunnelManager] = None
        self.tunnel_cards: Dict[str, TunnelCard] = {}
        
        self._setup_window()
        self._load_config()
        self._create_ui()
        self._start_update_loop()
    
    def _setup_window(self):
        """Настраивает главное окно."""
        self.root = tk.Tk()
        self.root.title("SSH Tunnel Manager")
        self.root.geometry("1000x800")
        self.root.minsize(800, 600)
        
        # Настройка стиля
        style = ttk.Style()
        style.theme_use('clam')
        
        # Обработка закрытия
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _load_config(self):
        """Загружает конфигурацию."""
        try:
            self.config = ConfigLoader.load(self.config_path)
            logging.basicConfig(level=getattr(logging, self.config.settings.log_level))
        except FileNotFoundError:
            self.config = AppConfig()
            messagebox.showwarning("Warning", f"Config file not found: {self.config_path}\nCreating new configuration.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load config: {e}")
            self.config = AppConfig()
    
    def _create_ui(self):
        """Создает пользовательский интерфейс."""
        # Главный контейнер
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Верхняя панель
        top_panel = ttk.Frame(main_container)
        top_panel.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(top_panel, text="➕ Add Tunnel", command=self._add_tunnel).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_panel, text="▶ Start All", command=self._start_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_panel, text="⏹ Stop All", command=self._stop_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_panel, text="💾 Save Config", command=self._save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_panel, text="📂 Load Config", command=self._load_config_dialog).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(top_panel, text=f"Config: {self.config_path}").pack(side=tk.RIGHT)
        
        # Панель туннелей
        tunnels_frame = ttk.LabelFrame(main_container, text="Tunnels", padding=10)
        tunnels_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Canvas с прокруткой для туннелей
        self.tunnels_canvas = tk.Canvas(tunnels_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tunnels_frame, orient=tk.VERTICAL, command=self.tunnels_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.tunnels_canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.tunnels_canvas.configure(scrollregion=self.tunnels_canvas.bbox("all"))
        )
        
        self.tunnels_canvas.create_window((0, 0), window=self.scrollable_frame, anchor=tk.NW)
        self.tunnels_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.tunnels_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind mouse wheel
        self.tunnels_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Панель логов
        logs_frame = ttk.LabelFrame(main_container, text="Logs", padding=10)
        logs_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.log_text = scrolledtext.ScrolledText(logs_frame, height=10, wrap=tk.WORD)
        self.log_text.pack(fill=tk.X)
        
        # Добавляем обработчик логов
        log_handler = LogHandler(self.log_text)
        logging.getLogger().addHandler(log_handler)
        logging.getLogger().setLevel(logging.INFO)
        
        # Статус бар
        self.status_bar = ttk.Label(main_container, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X)
        
        # Загрузка существующих туннелей
        self._refresh_tunnels()
    
    def _on_mousewheel(self, event):
        self.tunnels_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def _refresh_tunnels(self):
        """Обновляет список туннелей."""
        # Очищаем существующие карточки
        for card in self.tunnel_cards.values():
            card.destroy()
        self.tunnel_cards.clear()
        
        # Создаем новые карточки
        for tunnel_config in self.config.tunnels:
            self._add_tunnel_card(tunnel_config)
    
    def _add_tunnel_card(self, tunnel_config):
        """Добавляет карточку туннеля."""
        info = {
            'id': tunnel_config.id,
            'name': tunnel_config.name,
            'status': 'stopped',
            'local_port': tunnel_config.forwarding.local_port,
            'remote_host': tunnel_config.forwarding.remote_host,
            'remote_port': tunnel_config.forwarding.remote_port,
            'proxy_type': tunnel_config.proxy.type if tunnel_config.proxy.enabled else None,
            'proxy_port': tunnel_config.proxy.port if tunnel_config.proxy.enabled else None
        }
        
        card = TunnelCard(
            self.scrollable_frame,
            info,
            on_start=self._start_tunnel,
            on_stop=self._stop_tunnel,
            on_restart=self._restart_tunnel,
            on_edit=self._edit_tunnel,
            on_delete=self._delete_tunnel
        )
        card.pack(fill=tk.X, pady=5)
        self.tunnel_cards[tunnel_config.id] = card
    
    def _add_tunnel(self):
        """Открывает диалог добавления туннеля."""
        dialog = TunnelDialog(self.root)
        if dialog.result:
            # Создаем конфигурацию туннеля
            data = dialog.result
            tunnel_config = TunnelConfig(
                id=data['id'],
                name=data['name'],
                enabled=data['enabled'],
                ssh=SSHConfig(
                    host=data['ssh']['host'],
                    port=data['ssh']['port'],
                    username=data['ssh']['username'],
                    password=data['ssh']['password'],
                    private_key=data['ssh']['private_key'],
                    passphrase=data['ssh']['passphrase']
                ),
                forwarding=ForwardingConfig(
                    local_port=data['forwarding']['local_port'],
                    remote_host=data['forwarding']['remote_host'],
                    remote_port=data['forwarding']['remote_port']
                ),
                proxy=ProxyConfig(
                    type=data['proxy']['type'],
                    enabled=data['proxy']['enabled'],
                    port=data['proxy']['port']
                )
            )
            
            self.config.tunnels.append(tunnel_config)
            self._add_tunnel_card(tunnel_config)
            self.status_bar.config(text=f"Added tunnel: {data['name']}")
    
    def _edit_tunnel(self, tunnel_id: str):
        """Открывает диалог редактирования туннеля."""
        # Находим конфигурацию
        tunnel_config = None
        for tc in self.config.tunnels:
            if tc.id == tunnel_id:
                tunnel_config = tc
                break
        
        if not tunnel_config:
            return
        
        # Преобразуем в словарь
        data = {
            'id': tunnel_config.id,
            'name': tunnel_config.name,
            'ssh': {
                'host': tunnel_config.ssh.host,
                'port': tunnel_config.ssh.port,
                'username': tunnel_config.ssh.username,
                'password': tunnel_config.ssh.password,
                'private_key': tunnel_config.ssh.private_key,
                'passphrase': tunnel_config.ssh.passphrase
            },
            'forwarding': {
                'local_port': tunnel_config.forwarding.local_port,
                'remote_host': tunnel_config.forwarding.remote_host,
                'remote_port': tunnel_config.forwarding.remote_port
            },
            'proxy': {
                'type': tunnel_config.proxy.type,
                'enabled': tunnel_config.proxy.enabled,
                'port': tunnel_config.proxy.port
            }
        }
        
        dialog = TunnelDialog(self.root, data)
        if dialog.result:
            # Обновляем конфигурацию
            result = dialog.result
            tunnel_config.name = result['name']
            tunnel_config.enabled = result['enabled']
            tunnel_config.ssh.host = result['ssh']['host']
            tunnel_config.ssh.port = result['ssh']['port']
            tunnel_config.ssh.username = result['ssh']['username']
            tunnel_config.ssh.password = result['ssh']['password']
            tunnel_config.ssh.private_key = result['ssh']['private_key']
            tunnel_config.ssh.passphrase = result['ssh']['passphrase']
            tunnel_config.forwarding.local_port = result['forwarding']['local_port']
            tunnel_config.forwarding.remote_host = result['forwarding']['remote_host']
            tunnel_config.forwarding.remote_port = result['forwarding']['remote_port']
            tunnel_config.proxy.type = result['proxy']['type']
            tunnel_config.proxy.enabled = result['proxy']['enabled']
            tunnel_config.proxy.port = result['proxy']['port']
            
            # Обновляем карточку
            self._refresh_tunnels()
            self.status_bar.config(text=f"Updated tunnel: {result['name']}")
    
    def _delete_tunnel(self, tunnel_id: str):
        """Удаляет туннель."""
        if self.manager:
            self.manager.stop_tunnel(tunnel_id)
        
        self.config.tunnels = [t for t in self.config.tunnels if t.id != tunnel_id]
        del self.tunnel_cards[tunnel_id]
        self._refresh_tunnels()
        self.status_bar.config(text=f"Deleted tunnel: {tunnel_id}")
    
    def _start_tunnel(self, tunnel_id: str):
        """Запускает туннель."""
        if not self.manager:
            self._init_manager()
        
        def run():
            try:
                result = self.manager.start_tunnel(tunnel_id)
                self.root.after(0, lambda: self._on_tunnel_action(tunnel_id, result))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        
        threading.Thread(target=run, daemon=True).start()
    
    def _stop_tunnel(self, tunnel_id: str):
        """Останавливает туннель."""
        if self.manager:
            self.manager.stop_tunnel(tunnel_id)
            self._on_tunnel_action(tunnel_id, True)
    
    def _restart_tunnel(self, tunnel_id: str):
        """Перезапускает туннель."""
        if not self.manager:
            self._init_manager()
        
        def run():
            try:
                result = self.manager.restart_tunnel(tunnel_id)
                self.root.after(0, lambda: self._on_tunnel_action(tunnel_id, result))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        
        threading.Thread(target=run, daemon=True).start()
    
    def _start_all(self):
        """Запускает все туннели."""
        if not self.manager:
            self._init_manager()
        
        def run():
            try:
                self.manager.start_all()
                self.root.after(0, lambda: self.status_bar.config(text="Started all tunnels"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        
        threading.Thread(target=run, daemon=True).start()
    
    def _stop_all(self):
        """Останавливает все туннели."""
        if self.manager:
            self.manager.stop_all()
            self.status_bar.config(text="Stopped all tunnels")
    
    def _init_manager(self):
        """Инициализирует менеджер туннелей."""
        self.manager = TunnelManager(self.config)
        
        def on_status_change(tunnel_id, status):
            self.root.after(0, lambda: self._update_tunnel_status(tunnel_id, status.value))
        
        self.manager.on_tunnel_status_change = on_status_change
    
    def _on_tunnel_action(self, tunnel_id: str, success: bool):
        """Обработчик завершения действия с туннелем."""
        if success:
            self.status_bar.config(text=f"Tunnel {tunnel_id}: OK")
        else:
            self.status_bar.config(text=f"Tunnel {tunnel_id}: Failed")
    
    def _update_tunnel_status(self, tunnel_id: str, status: str):
        """Обновляет статус туннеля в UI."""
        if tunnel_id in self.tunnel_cards:
            self.tunnel_cards[tunnel_id].update_status(status)
    
    def _save_config(self):
        """Сохраняет конфигурацию."""
        try:
            ConfigLoader.save(self.config, self.config_path)
            messagebox.showinfo("Success", "Configuration saved!")
            self.status_bar.config(text=f"Saved: {self.config_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
    
    def _load_config_dialog(self):
        """Открывает диалог загрузки конфигурации."""
        filename = filedialog.askopenfilename(
            title="Select Configuration File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.config_path = filename
            try:
                self.config = ConfigLoader.load(filename)
                self._refresh_tunnels()
                self.status_bar.config(text=f"Loaded: {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load: {e}")
    
    def _start_update_loop(self):
        """Запускает цикл обновления статусов."""
        def update():
            if self.manager:
                for tunnel_id, card in self.tunnel_cards.items():
                    status = self.manager.get_tunnel_status(tunnel_id)
                    if status:
                        card.update_status(status.value)
            self.root.after(1000, update)
        
        self.root.after(1000, update)
    
    def _on_close(self):
        """Обработчик закрытия окна."""
        if self.manager:
            self.manager.shutdown()
        self.root.destroy()
    
    def run(self):
        """Запускает приложение."""
        self.root.mainloop()


def main():
    """Точка входа GUI."""
    import argparse
    
    parser = argparse.ArgumentParser(description='SSH Tunnel Manager GUI')
    parser.add_argument('-c', '--config', default='config/tunnels.json',
                       help='Path to configuration file')
    args = parser.parse_args()
    
    app = SSHManagerGUI(args.config)
    app.run()


if __name__ == '__main__':
    main()

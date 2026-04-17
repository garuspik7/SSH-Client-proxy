# SSH Tunnel Manager

Многопоточный SSH-клиент с поддержкой нескольких туннелей и локальных прокси-серверов.

## 📋 Возможности

- ✅ **Несколько одновременных туннелей** — управляйте множеством SSH-подключений
- ✅ **Локальный порт форвардинг** — пробрасывайте локальные порты на удалённые серверы
- ✅ **SOCKS5 и HTTP прокси** — каждый туннель может работать как прокси-сервер
- ✅ **Поддержка аутентификации** — пароли и SSH ключи (RSA, DSA, ECDSA, Ed25519)
- ✅ **Авто-переподключение** — восстановление соединения при разрыве
- ✅ **Логирование** — подробные логи всех событий
- ✅ **Проверка хостов** — поддержка known_hosts для безопасности
- ✅ **Графический интерфейс** — удобный GUI для управления туннелями
- ✅ **CLI интерфейс** — управление из командной строки
- ✅ **Кроссплатформенность** — работает на Windows, macOS, Linux

## 📁 Структура проекта

```
ssh_tunnel_manager/
├── src/
│   ├── __init__.py          # Пакет
│   ├── main.py              # CLI интерфейс
│   ├── gui.py               # Графический интерфейс (Tkinter)
│   ├── config.py            # Конфигурация (загрузка/сохранение JSON)
│   ├── ssh_client.py        # SSH клиент (Paramiko)
│   ├── tunnel.py            # Управление отдельным туннелем
│   ├── proxy.py             # Прокси серверы (SOCKS5/HTTP)
│   └── manager.py           # Менеджер всех туннелей
├── config/
│   └── tunnels.json         # Конфигурационный файл
├── logs/                    # Директория для логов
├── requirements.txt         # Зависимости Python
└── README.md               # Документация
```

## 🚀 Установка

### 1. Клонирование или загрузка проекта

```bash
cd ssh_tunnel_manager
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

Или вручную:

```bash
pip install paramiko sshtunnel
```

### 3. Проверка установки

```bash
python -m src.main --help
```

## 📝 Конфигурация

Создайте файл конфигурации `config/tunnels.json`:

```json
{
  "tunnels": [
    {
      "id": "production",
      "name": "Production Server",
      "enabled": true,
      "ssh": {
        "host": "example.com",
        "port": 22,
        "username": "user",
        "password": null,
        "private_key": "~/.ssh/id_rsa",
        "passphrase": null
      },
      "forwarding": {
        "local_port": 8080,
        "remote_host": "localhost",
        "remote_port": 80
      },
      "proxy": {
        "type": "socks5",
        "enabled": true,
        "port": 9090
      }
    }
  ],
  "settings": {
    "log_level": "INFO",
    "log_file": "logs/tunnels.log",
    "auto_reconnect": true,
    "reconnect_delay": 5,
    "max_reconnect_attempts": 10,
    "known_hosts_file": "~/.ssh/known_hosts",
    "timeout": 30
  }
}
```

### Параметры конфигурации

#### Туннель
| Параметр | Описание |
|----------|----------|
| `id` | Уникальный идентификатор туннеля |
| `name` | Отображаемое имя |
| `enabled` | Включён ли туннель по умолчанию |

#### SSH подключение
| Параметр | Описание |
|----------|----------|
| `host` | Адрес SSH сервера |
| `port` | Порт SSH (по умолчанию 22) |
| `username` | Имя пользователя |
| `password` | Пароль (или `null` для ключа) |
| `private_key` | Путь к приватному ключу |
| `passphrase` | Парольная фраза для ключа |

#### Проброс портов
| Параметр | Описание |
|----------|----------|
| `local_port` | Локальный порт |
| `remote_host` | Удалённый хост (относительно SSH сервера) |
| `remote_port` | Удалённый порт |

#### Прокси
| Параметр | Описание |
|----------|----------|
| `type` | Тип прокси: `socks5` или `http` |
| `enabled` | Включить прокси |
| `port` | Порт прокси сервера |

## 💻 Использование

### CLI режим

#### Показать статус туннелей
```bash
python -m src.main --status
```

#### Запустить все включённые туннели
```bash
python -m src.main --start-all
```

#### Интерактивный режим
```bash
python -m src.main --interactive
```

Команды интерактивного режима:
- `start <id>` — запустить туннель
- `stop <id>` — остановить туннель
- `restart <id>` — перезапустить туннель
- `enable <id>` — включить туннель
- `disable <id>` — отключить туннель
- `status` — показать статусы
- `quit` — выйти

#### Полный список опций
```bash
python -m src.main --help
```

```
options:
  -c CONFIG, --config CONFIG      Путь к конфигурации
  -l LEVEL, --log-level LEVEL     Уровень логирования
  -f FILE, --log-file FILE        Файл логов
  -s, --start-all                 Запустить все туннели
  -i, --interactive               Интерактивный режим
  --status                        Показать статус и выйти
```

### GUI режим

Для запуска графического интерфейса:

```bash
python -m src.gui
```

Или с указанием конфигурации:

```bash
python -m src.gui --config config/tunnels.json
```

#### Возможности GUI:
- 📊 Визуальные карточки туннелей с индикаторами статуса
- ▶️/⏹ Кнопки запуска/остановки для каждого туннеля
- ✏️ Редактирование туннелей через диалоговое окно

---

## 📦 Компиляция в .exe (Windows)

### Автоматическая сборка

1. Скопируйте проект на Windows машину
2. Дважды кликните на `build_windows.bat`
3. Готовые файлы появятся в папке `dist\`:
   - `SSH_Tunnel_Manager.exe` — GUI версия
   - `SSH_Tunnel_CLI.exe` — CLI версия

### Ручная сборка

```powershell
# Установка зависимостей
pip install paramiko sshtunnel pyinstaller

# GUI версия
pyinstaller --onefile --windowed --name "SSH_Tunnel_Manager" --add-data "config;tunnels.json" src/gui.py

# CLI версия
pyinstaller --onefile --name "SSH_Tunnel_CLI" src/main.py
```

Подробная инструкция: [BUILD_WINDOWS.md](BUILD_WINDOWS.md)

#### Возможности GUI (продолжение):
- ➕ Добавление новых туннелей
- 🗑 Удаление туннелей
- 💾 Сохранение конфигурации
- 📂 Загрузка других конфигов
- 📝 Панель логов в реальном времени

## 🔒 Безопасность

### SSH ключи
Поддерживаются все типы ключей Paramiko:
- RSA
- DSA
- ECDSA
- Ed25519

### Known Hosts
При первом подключении ключ сервера автоматически добавляется в `known_hosts`.
При повторных подключениях ключ проверяется.

### Хранение паролей
⚠️ **Важно**: Пароли в конфигурационном файле хранятся в открытом виде.
Для продакшена рекомендуется:
1. Использовать SSH ключи вместо паролей
2. Защищать файл конфигурации правами доступа (chmod 600)
3. Использовать переменные окружения для чувствительных данных

## 🛠 Примеры использования

### Пример 1: Доступ к веб-серверу
```json
{
  "id": "web",
  "name": "Web Server",
  "ssh": {"host": "web.example.com", "username": "deploy"},
  "forwarding": {"local_port": 8080, "remote_port": 80},
  "proxy": {"type": "socks5", "enabled": true, "port": 9090}
}
```
После запуска: `http://localhost:8080` → веб-сервер на удалённой машине

### Пример 2: Доступ к базе данных
```json
{
  "id": "db",
  "name": "Database",
  "ssh": {"host": "db.example.com", "username": "admin"},
  "forwarding": {"local_port": 3307, "remote_port": 3306}
}
```
Подключение: `mysql -h 127.0.0.1 -P 3307 -u root`

### Пример 3: SOCKS5 прокси через сервер
```json
{
  "id": "proxy",
  "name": "Proxy Tunnel",
  "ssh": {"host": "vpn.example.com", "username": "user"},
  "forwarding": {"local_port": 1080, "remote_port": 1080},
  "proxy": {"type": "socks5", "enabled": true, "port": 1080}
}
```
Настройте браузер на использование SOCKS5 прокси `localhost:1080`

## 🧩 Модульная архитектура

Проект разделён на независимые модули:

| Модуль | Описание |
|--------|----------|
| `config.py` | Загрузка/сохранение конфигурации, dataclass'ы |
| `ssh_client.py` | Обёртка над Paramiko для SSH подключений |
| `tunnel.py` | Класс Tunnel с мониторингом и авто-переподключением |
| `proxy.py` | Реализация SOCKS5 и HTTP прокси серверов |
| `manager.py` | TunnelManager для управления множеством туннелей |
| `main.py` | CLI интерфейс с argparse |
| `gui.py` | Графический интерфейс на Tkinter |

## ⚙️ Настройки

В секции `settings` конфигурационного файла:

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `log_level` | INFO | Уровень логирования |
| `log_file` | logs/tunnels.log | Файл для логов |
| `auto_reconnect` | true | Авто-переподключение |
| `reconnect_delay` | 5 | Задержка перед переподключением (сек) |
| `max_reconnect_attempts` | 10 | Максимум попыток переподключения |
| `known_hosts_file` | ~/.ssh/known_hosts | Файл known_hosts |
| `timeout` | 30 | Таймаут подключения (сек) |

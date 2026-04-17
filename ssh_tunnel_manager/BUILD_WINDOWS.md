# Инструкция по компиляции для Windows

## Текущая сборка

Сборка выполнена в среде Linux. Получены исполняемые файлы:
- `dist/SSH_Tunnel_Manager` — GUI версия (7.0 MB)
- `dist/SSH_Tunnel_CLI` — CLI версия (7.0 MB)

**Важно:** Эти файлы скомпилированы под Linux. Для Windows нужна отдельная компиляция.

---

## Способ 1: Компиляция на Windows (рекомендуется)

### Требования на Windows машине:
1. Установите Python 3.8+ с [python.org](https://www.python.org/downloads/)
2. Откройте PowerShell или CMD от имени администратора

### Шаги компиляции:

```powershell
# 1. Клонируйте репозиторий (если ещё не клонирован)
git clone <URL_репозитория>
cd ssh_tunnel_manager

# 2. Создайте виртуальное окружение
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Установите зависимости
pip install paramiko sshtunnel pyinstaller

# 4. Скомпилируйте GUI версию
pyinstaller --onefile --windowed --name "SSH_Tunnel_Manager" --add-data "config;tunnels.json" src/gui.py

# 5. Скомпилируйте CLI версию
pyinstaller --onefile --name "SSH_Tunnel_CLI" src/main.py
```

### Результат:
Файлы появятся в папке `dist/`:
- `SSH_Tunnel_Manager.exe` — графический интерфейс
- `SSH_Tunnel_CLI.exe` — консольная версия

---

## Способ 2: Кросс-компиляция через Docker (для продвинутых)

Если у вас нет Windows, но есть Docker:

```bash
# Используйте образ wine для кросс-компиляции
docker run --rm -it -v $(pwd):/app python:3.11-windowsservercore bash

# Внутри контейнера выполните те же команды что в Способе 1
```

---

## Способ 3: Запуск без компиляции (самый простой)

Если компиляция не обязательна, можно запускать напрямую:

### На Windows:

```powershell
# 1. Установите Python 3.8+
# 2. Откройте PowerShell в папке проекта

python -m venv venv
.\venv\Scripts\Activate.ps1
pip install paramiko sshtunnel

# Запуск GUI
python -m src.gui

# Запуск CLI
python -m src.main --status
```

---

## Структура дистрибутива для Windows

После компиляции рекомендуемая структура:

```
ssh_tunnel_manager_windows/
├── SSH_Tunnel_Manager.exe    # GUI приложение
├── SSH_Tunnel_CLI.exe        # CLI приложение
├── config/
│   └── tunnels.json          # Файл конфигурации
├── logs/                     # Логи (создаётся автоматически)
└── README_Windows.md         # Эта инструкция
```

---

## Решение проблем

### Ошибка: "tkinter not found" при компиляции GUI
Убедитесь, что установили Python с опцией **tcl/tk support**:
- При установке Python отметьте галочку "Install tk"
- Или переустановите Python с полным набором компонентов

### Ошибка: "Module not found: paramiko"
```powershell
pip install --upgrade paramiko sshtunnel
```

### Антивирус блокирует .exe файл
Добавьте папку с программой в исключения антивируса.
Либо подпишите сертификатом (требуется для распространения).

### Программа не запускается дважды кликом
Запустите через CMD для просмотра ошибки:
```powershell
.\SSH_Tunnel_Manager.exe
```

---

## Автозагрузка в Windows

Чтобы туннели запускались автоматически:

1. Нажмите `Win + R`, введите `shell:startup`
2. Создайте ярлык для `SSH_Tunnel_Manager.exe`
3. В свойствах ярлыка добавьте аргументы если нужно

Или используйте Планировщик заданий (Task Scheduler).

---

## Контакты и поддержка

При возникновении проблем:
1. Проверьте логи в папке `logs/`
2. Запустите с флагом `--debug` для подробной информации
3. Убедитесь что порты не заняты другими программами

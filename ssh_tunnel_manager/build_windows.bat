@echo off
echo ========================================
echo SSH Tunnel Manager - Windows Build Script
echo ========================================
echo.

REM Проверка Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python не найден! Установите Python 3.8+ с python.org
    pause
    exit /b 1
)

echo [OK] Python найден
python --version
echo.

REM Создание виртуального окружения
if not exist "venv" (
    echo [INFO] Создание виртуального окружения...
    python -m venv venv
) else (
    echo [INFO] Виртуальное окружение уже существует
)

REM Активация виртуального окружения
echo [INFO] Активация виртуального окружения...
call venv\Scripts\activate.bat

REM Установка зависимостей
echo [INFO] Установка зависимостей...
pip install --upgrade pip
pip install paramiko sshtunnel pyinstaller

REM Очистка предыдущих сборок
if exist "dist" (
    echo [INFO] Очистка предыдущих сборок...
    rmdir /s /q dist
)
if exist "build" (
    rmdir /s /q build
)

REM Компиляция GUI версии
echo.
echo ========================================
echo Компиляция GUI версии...
echo ========================================
pyinstaller --onefile --windowed --name "SSH_Tunnel_Manager" --add-data "config;tunnels.json" src\gui.py

if %errorlevel% neq 0 (
    echo [ERROR] Ошибка компиляции GUI!
    pause
    exit /b 1
)

REM Компиляция CLI версии
echo.
echo ========================================
echo Компиляция CLI версии...
echo ========================================
pyinstaller --onefile --name "SSH_Tunnel_CLI" src\main.py

if %errorlevel% neq 0 (
    echo [ERROR] Ошибка компиляции CLI!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Сборка завершена успешно!
echo ========================================
echo.
echo Файлы в папке dist\:
dir /b dist\*.exe
echo.
echo Для запуска:
echo   - GUI: dist\SSH_Tunnel_Manager.exe
echo   - CLI: dist\SSH_Tunnel_CLI.exe
echo.

pause

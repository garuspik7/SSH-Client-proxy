"""CLI интерфейс для SSH Tunnel Manager."""

import argparse
import logging
import sys
import signal
import time
from pathlib import Path

from .config import ConfigLoader, AppConfig
from .manager import TunnelManager
from .tunnel import TunnelStatus


def setup_logging(log_level: str = 'INFO', log_file: str = None):
    """Настраивает логирование."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


def print_status(manager: TunnelManager):
    """Выводит статус всех туннелей."""
    print("\n" + "=" * 60)
    print("SSH TUNNEL STATUS")
    print("=" * 60)
    
    info_list = manager.get_all_info()
    
    if not info_list:
        print("No tunnels configured.")
        return
    
    for info in info_list:
        status_icon = {
            'running': '🟢',
            'stopped': '⚫',
            'starting': '🟡',
            'stopping': '🟠',
            'error': '🔴',
            'reconnecting': '🔄'
        }.get(info['status'], '⚪')
        
        enabled_icon = '✓' if manager.tunnels[info['id']].config.enabled else '✗'
        
        print(f"\n{status_icon} [{enabled_icon}] {info['name']} ({info['id']})")
        print(f"   Status: {info['status'].upper()}")
        print(f"   Forwarding: 127.0.0.1:{info['local_port']} -> "
              f"{info['remote_host']}:{info['remote_port']}")
        
        if info['proxy_type']:
            print(f"   Proxy: {info['proxy_type'].upper()} on port {info['proxy_port']}")
        
        if info['reconnect_attempts'] > 0:
            print(f"   Reconnect attempts: {info['reconnect_attempts']}")
    
    print("\n" + "=" * 60)


def interactive_mode(manager: TunnelManager):
    """Интерактивный режим управления."""
    print("\nInteractive mode. Commands:")
    print("  start <id>     - Start tunnel")
    print("  stop <id>      - Stop tunnel")
    print("  restart <id>   - Restart tunnel")
    print("  enable <id>    - Enable tunnel")
    print("  disable <id>   - Disable tunnel")
    print("  status         - Show all statuses")
    print("  quit           - Exit")
    
    while True:
        try:
            cmd = input("\n> ").strip().split()
            
            if not cmd:
                continue
            
            action = cmd[0].lower()
            
            if action == 'quit' or action == 'exit':
                break
            
            elif action == 'status':
                print_status(manager)
            
            elif action in ['start', 'stop', 'restart', 'enable', 'disable']:
                if len(cmd) < 2:
                    print("Error: Tunnel ID required")
                    continue
                
                tunnel_id = cmd[1]
                
                if action == 'start':
                    result = manager.start_tunnel(tunnel_id)
                    print(f"Start {'successful' if result else 'failed'}")
                
                elif action == 'stop':
                    manager.stop_tunnel(tunnel_id)
                    print("Stop command sent")
                
                elif action == 'restart':
                    result = manager.restart_tunnel(tunnel_id)
                    print(f"Restart {'successful' if result else 'failed'}")
                
                elif action == 'enable':
                    result = manager.enable_tunnel(tunnel_id)
                    print(f"Enable {'successful' if result else 'failed'}")
                
                elif action == 'disable':
                    result = manager.disable_tunnel(tunnel_id)
                    print(f"Disable {'successful' if result else 'failed'}")
            
            else:
                print(f"Unknown command: {action}")
        
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Точка входа CLI."""
    parser = argparse.ArgumentParser(
        description='SSH Tunnel Manager - Manage multiple SSH tunnels and proxies'
    )
    
    parser.add_argument(
        '-c', '--config',
        default='config/tunnels.json',
        help='Path to configuration file (default: config/tunnels.json)'
    )
    
    parser.add_argument(
        '-l', '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )
    
    parser.add_argument(
        '-f', '--log-file',
        default=None,
        help='Log file path'
    )
    
    parser.add_argument(
        '-s', '--start-all',
        action='store_true',
        help='Start all enabled tunnels immediately'
    )
    
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='Run in interactive mode'
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show tunnel statuses and exit'
    )
    
    args = parser.parse_args()
    
    # Настройка логирования
    setup_logging(args.log_level, args.log_file)
    logger = logging.getLogger(__name__)
    
    try:
        # Загрузка конфигурации
        logger.info(f"Loading configuration from {args.config}")
        config = ConfigLoader.load(args.config)
        
        # Создание менеджера
        manager = TunnelManager(config)
        
        # Обработка сигналов
        def signal_handler(sig, frame):
            logger.info("Received shutdown signal")
            manager.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Показ статуса
        if args.status:
            print_status(manager)
            manager.shutdown()
            return
        
        # Запуск всех туннелей
        if args.start_all:
            logger.info("Starting all enabled tunnels")
            results = manager.start_all()
            
            for tunnel_id, success in results.items():
                status = "✓" if success else "✗"
                print(f"{status} {tunnel_id}")
            
            if not args.interactive:
                # Ожидаем завершения
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
        
        # Интерактивный режим
        elif args.interactive:
            print_status(manager)
            interactive_mode(manager)
        
        else:
            # Режим по умолчанию - показать статус и выйти
            print_status(manager)
            print("\nUse --start-all to start tunnels or --interactive for control")
        
        # Завершение работы
        manager.shutdown()
        
    except FileNotFoundError as e:
        logger.error(str(e))
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

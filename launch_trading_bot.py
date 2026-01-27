#!/usr/bin/env python3
"""
Grid Trading Bot Web Launcher

Combined launcher that provides both CLI interface and web dashboard
for the grid trading bot.
"""

import sys
import os
import threading
import time
import webbrowser
from datetime import datetime

def run_web_dashboard():
    """Run the grid trading web dashboard in a separate thread"""
    try:
        from web_dashboard_grid_trading import socketio, app, load_bot_config
        print("🚀 Initializing Grid Trading web dashboard...")
        if load_bot_config():
            print("✅ Bot configuration loaded")
            print("🌐 Starting web server on http://localhost:5001")
            def open_browser():
                time.sleep(2)
                try:
                    webbrowser.open('http://localhost:5001')
                    print("📱 Browser opened automatically")
                except:
                    print("📱 Please open http://localhost:5001 in your browser")
            browser_thread = threading.Thread(target=open_browser)
            browser_thread.daemon = True
            browser_thread.start()
            socketio.run(app, debug=False, host='0.0.0.0', port=5001)
        else:
            print("❌ Failed to initialize bot configuration")
            return False
    except ImportError as e:
        print(f"❌ Missing web dependencies: {e}")
        print("💡 Install with: pip install flask flask-cors flask-socketio eventlet")
        return False
    except Exception as e:
        print(f"❌ Error starting web dashboard: {e}")
        return False

def run_web_dashboard_supertrend():
    """Run the supertrend web dashboard in a separate thread"""
    try:
        from web_dashboard_supertrend import socketio, app, load_bot_config
        print("🚀 Initializing Supertrend web dashboard...")
        if load_bot_config():
            print("✅ Supertrend bot configuration loaded")
            print("🌐 Starting web server on http://localhost:5002")
            def open_browser():
                time.sleep(2)
                try:
                    webbrowser.open('http://localhost:5002')
                    print("📱 Browser opened automatically")
                except:
                    print("📱 Please open http://localhost:5002 in your browser")
            browser_thread = threading.Thread(target=open_browser)
            browser_thread.daemon = True
            browser_thread.start()
            socketio.run(app, debug=False, host='0.0.0.0', port=5002)
        else:
            print("❌ Failed to initialize supertrend bot configuration")
            return False
    except ImportError as e:
        print(f"❌ Missing web dependencies: {e}")
        print("💡 Install with: pip install flask flask-cors flask-socketio eventlet")
        return False
    except Exception as e:
        print(f"❌ Error starting supertrend web dashboard: {e}")
        return False

def run_cli_interface():
    """Run the original grid CLI interface"""
    try:
        from run_grid_bot import main
        main()
    except KeyboardInterrupt:
        print("\n👋 CLI interface closed")
    except Exception as e:
        print(f"❌ Error in CLI interface: {e}")

def run_cli_interface_supertrend():
    """Run the supertrend CLI interface"""
    try:
        from run_supertrend_bot import main
        main()
    except KeyboardInterrupt:
        print("\n👋 Supertrend CLI interface closed")
    except Exception as e:
        print(f"❌ Error in Supertrend CLI interface: {e}")

def main():
    """Main launcher with options for Grid and Supertrend bots"""
    print("=" * 60)
    print("🤖 TRADING BOT LAUNCHER (Grid & Supertrend)")
    print("=" * 60)
    print()
    print("Choose your bot and interface:")
    print("1. 🌐 Grid Web Dashboard (Recommended)")
    print("2. 💻 Grid Command Line Interface")
    print("3. 🚀 Grid: Both (Web + CLI in background)")
    print("4. 🌐 Supertrend Web Dashboard")
    print("5. 💻 Supertrend Command Line Interface")
    print("6. 🚀 Supertrend: Both (Web + CLI in background)")
    print("7. ❌ Exit")
    print()
    try:
        choice = input("Select option (1-7): ").strip()
        if choice == '1':
            if not os.path.exists('grid_config.json'):
                print("❌ Configuration file 'grid_config.json' not found!")
                print("Please run the CLI interface first to set up your configuration.")
                sys.exit(1)
            print("\n🌐 Starting Grid Web Dashboard...")
            run_web_dashboard()
        elif choice == '2':
            if not os.path.exists('grid_config.json'):
                print("❌ Configuration file 'grid_config.json' not found!")
                print("Please run the CLI interface first to set up your configuration.")
                sys.exit(1)
            print("\n💻 Starting Grid CLI Interface...")
            run_cli_interface()
        elif choice == '3':
            if not os.path.exists('grid_config.json'):
                print("❌ Configuration file 'grid_config.json' not found!")
                print("Please run the CLI interface first to set up your configuration.")
                sys.exit(1)
            print("\n🚀 Starting both Grid interfaces...")
            web_thread = threading.Thread(target=run_web_dashboard)
            web_thread.daemon = True
            web_thread.start()
            time.sleep(3)
            run_cli_interface()
        elif choice == '4':
            if not os.path.exists('supertrend_config.json'):
                print("❌ Configuration file 'supertrend_config.json' not found!")
                print("Please run the Supertrend CLI interface first to set up your configuration.")
                sys.exit(1)
            print("\n🌐 Starting Supertrend Web Dashboard...")
            run_web_dashboard_supertrend()
        elif choice == '5':
            if not os.path.exists('supertrend_config.json'):
                print("❌ Configuration file 'supertrend_config.json' not found!")
                print("Please run the Supertrend CLI interface first to set up your configuration.")
                sys.exit(1)
            print("\n💻 Starting Supertrend CLI Interface...")
            run_cli_interface_supertrend()
        elif choice == '6':
            if not os.path.exists('supertrend_config.json'):
                print("❌ Configuration file 'supertrend_config.json' not found!")
                print("Please run the Supertrend CLI interface first to set up your configuration.")
                sys.exit(1)
            print("\n🚀 Starting both Supertrend interfaces...")
            web_thread = threading.Thread(target=run_web_dashboard_supertrend)
            web_thread.daemon = True
            web_thread.start()
            time.sleep(3)
            run_cli_interface_supertrend()
        elif choice == '7':
            print("👋 Goodbye!")
            sys.exit(0)
        else:
            print("❌ Invalid choice. Please select 1-7.")
            main()  # Restart
    except KeyboardInterrupt:
        print("\n\n🛑 Launcher interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

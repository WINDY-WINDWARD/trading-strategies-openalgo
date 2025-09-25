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
    """Run the web dashboard in a separate thread"""
    try:
        from web_dashboard import socketio, app, load_bot_config
        
        print("🚀 Initializing web dashboard...")
        if load_bot_config():
            print("✅ Bot configuration loaded")
            print("🌐 Starting web server on http://localhost:5001")
            
            # Open browser after a short delay
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
            
            # Start the web server
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

def run_cli_interface():
    """Run the original CLI interface"""
    try:
        from run_grid_bot import main
        main()
    except KeyboardInterrupt:
        print("\n👋 CLI interface closed")
    except Exception as e:
        print(f"❌ Error in CLI interface: {e}")

def main():
    """Main launcher with options"""
    print("=" * 60)
    print("🤖 GRID TRADING BOT LAUNCHER")
    print("=" * 60)
    print()
    
    # Check if configuration exists
    if not os.path.exists('grid_config.json'):
        print("❌ Configuration file 'grid_config.json' not found!")
        print("Please run the CLI interface first to set up your configuration.")
        sys.exit(1)
    
    print("Choose your interface:")
    print("1. 🌐 Web Dashboard (Recommended)")
    print("2. 💻 Command Line Interface")
    print("3. 🚀 Both (Web + CLI in background)")
    print("4. ❌ Exit")
    print()
    
    try:
        choice = input("Select option (1-4): ").strip()
        
        if choice == '1':
            print("\n🌐 Starting Web Dashboard...")
            print("Features: Real-time charts, TradingView integration, performance tracking")
            run_web_dashboard()
            
        elif choice == '2':
            print("\n💻 Starting CLI Interface...")
            run_cli_interface()
            
        elif choice == '3':
            print("\n🚀 Starting both interfaces...")
            print("Web dashboard will open in browser, CLI will run in background")
            
            # Start web dashboard in a thread
            web_thread = threading.Thread(target=run_web_dashboard)
            web_thread.daemon = True
            web_thread.start()
            
            # Give web server time to start
            time.sleep(3)
            
            # Run CLI interface in main thread
            run_cli_interface()
            
        elif choice == '4':
            print("👋 Goodbye!")
            sys.exit(0)
            
        else:
            print("❌ Invalid choice. Please select 1-4.")
            main()  # Restart
            
    except KeyboardInterrupt:
        print("\n\n🛑 Launcher interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

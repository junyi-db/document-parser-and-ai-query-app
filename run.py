#!/usr/bin/env python3
"""
Simple script to run the Streamlit PDF Parser app
"""

import os
import sys
import subprocess
from config import Config

def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import streamlit
        import databricks.sdk
        import pandas
        import PIL
        print("✅ All dependencies are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

def check_config():
    """Check Databricks configuration."""
    status = Config.get_config_status()
    
    print("\n🔧 Configuration Status:")
    print(f"Databricks Host: {'✅' if status['databricks_host_configured'] else '❌'}")
    print(f"Databricks Token: {'✅' if status['databricks_token_configured'] else '❌'}")
    print(f"Default Warehouse: {'✅' if status['default_warehouse_configured'] else '⚠️  (can be set in UI)'}")
    
    if not status['databricks_host_configured'] or not status['databricks_token_configured']:
        print("\n⚠️  Please configure Databricks credentials:")
        print("Environment variables:")
        print("  export DATABRICKS_HOST='https://your-workspace.cloud.databricks.com'")
        print("  export DATABRICKS_TOKEN='your-token'")
        print("\nOr create ~/.databrickscfg file - see README.md for details")
        return False
    
    return True

def main():
    """Main function to run the app."""
    print("🚀 Starting PDF Parser App with Databricks AI")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check configuration (non-blocking)
    check_config()
    
    print("\n🌐 Starting Streamlit app...")
    print("The app will open in your default web browser")
    print("Press Ctrl+C to stop the application")
    print("=" * 50)
    
    try:
        # Run streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.headless", "false",
            "--browser.gatherUsageStats", "false"
        ])
    except KeyboardInterrupt:
        print("\n\n👋 Application stopped by user")
    except Exception as e:
        print(f"\n❌ Error running app: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
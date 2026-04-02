#!/usr/bin/env python3
"""
Jogi Vault — Web UI entry point.
Run: python vault/ui.py  OR  make vault-ui  OR  docker-compose up vault-ui
Then: http://localhost:5111
"""
import os
import sys

# Ensure vault package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("VAULT_UI_PORT", 5111))
    print("\n  Jogi Vault UI -> http://localhost:{}\n".format(port))
    app.run(host="0.0.0.0", port=port, debug=False)

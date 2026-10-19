"""
Production server runner for DEBUNK.IT using Waitress (Windows-friendly WSGI server).
Designed for seamless integration with Cloudflare Tunnel.
"""
import os
import sys
import logging
from waitress import serve
from debunkit_app import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("debunkit.server")

PORT = int(os.environ.get("PORT", 5000))
HOST = os.environ.get("HOST", "127.0.0.1")
THREADS = int(os.environ.get("THREADS", 6))

if __name__ == "__main__":
    print("=" * 60)
    print("  DEBUNK.IT — Production Server (Waitress WSGI)")
    print(f"  Local Address : http://{HOST}:{PORT}")
    print(f"  Worker Threads: {THREADS}")
    print("=" * 60)
    print(f"[*] Point Cloudflare Tunnel to: http://{HOST}:{PORT}")
    print("[*] Server is running. Press Ctrl+C to stop.\n")
    
    serve(app, host=HOST, port=PORT, threads=THREADS)

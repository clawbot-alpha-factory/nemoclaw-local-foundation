#!/usr/bin/env python3
"""
Run the Command Center backend.
Usage: python run.py [--host HOST] [--port PORT] [--reload]
"""

import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="NemoClaw Command Center Backend")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8100, help="Bind port")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Startup script for Railway deployment.
Reads PORT from environment and starts uvicorn.
"""
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting server on port {port}")
    uvicorn.run("server:app", host="0.0.0.0", port=port)

#!/usr/bin/env python3
"""
CCP API Server Entry Point

Usage:
    python server.py [--host HOST] [--port PORT] [--reload]

Examples:
    python server.py
    python server.py --port 8080
    python server.py --reload  # Development mode
"""
import sys
import os
from dotenv import load_dotenv

load_dotenv()


def main():
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="CCP API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers")

    args = parser.parse_args()

    print(f"""
CCP API Server v2.0.0
=====================
Host: {args.host}
Port: {args.port}
Reload: {args.reload}

Core Endpoints:
  - GET  /              - API info
  - GET  /health        - Health check
  - GET  /stats         - System statistics

Task Execution:
  - POST /tasks         - Create task
  - GET  /tasks/{{id}}    - Get task status
  - POST /tasks/batch   - Batch tasks

LangGraph Workflow (v2):
  - POST /workflow      - Run LangGraph workflow
  - GET  /workflow/{{id}} - Get workflow status
  - GET  /workflows     - List workflows

Human-in-the-Loop (v2):
  - GET  /approvals          - List approval requests
  - GET  /approvals/{{id}}     - Get approval request
  - POST /approvals/{{id}}/approve - Approve request
  - POST /approvals/{{id}}/reject  - Reject request
  - GET  /approvals/stats    - Approval statistics

Thought Log (v2):
  - GET  /thoughts         - List thought chains
  - GET  /thoughts/{{id}}    - Get thought chain
  - GET  /thoughts/stats   - Thought log stats
  - POST /thoughts/export  - Export to file

Experience Store:
  - GET  /experiences      - List experiences
  - POST /experiences/export - Export experiences
  - POST /replay           - Run simulation

WebSocket:
  - WS   /ws/events        - Real-time event stream

Docs: http://{args.host}:{args.port}/docs
""")

    uvicorn.run(
        "src.api.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
    )


if __name__ == "__main__":
    main()

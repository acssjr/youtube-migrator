"""Run from backend: uv run python manage_download_engine.py status|update|rollback."""
import argparse
import json
from app.services.download_engine import download_engine

parser = argparse.ArgumentParser()
parser.add_argument("action", choices=["status", "update", "rollback"])
args = parser.parse_args()
success = True
if args.action == "update":
    success = download_engine.update()
elif args.action == "rollback":
    success = download_engine.rollback()
print(json.dumps({"success": success, **download_engine.status()}, ensure_ascii=False, indent=2))
raise SystemExit(0 if success else 1)

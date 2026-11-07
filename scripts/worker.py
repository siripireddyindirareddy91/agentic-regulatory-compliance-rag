"""Run from repository root: python -m scripts.worker; Ctrl+C to stop."""
import time
from backend.app.models import Session
from backend.app.jobs import schedule,run_one
while True:
    with Session() as db:schedule(db)
    if not run_one():time.sleep(3)

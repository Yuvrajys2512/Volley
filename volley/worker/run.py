"""Entrypoint for the multi-tenant worker process: `python -m volley.worker.run`.
This is what Railway's worker service runs."""

from volley.worker.scheduler import main_loop

if __name__ == "__main__":
    main_loop()

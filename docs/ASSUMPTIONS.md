# Assumptions

- **[A7] Local startup does not reset demo data.** `./dev.sh` starts Postgres, applies migrations, and starts both servers. Run `PYTHONPATH=backend backend/.venv/bin/python -m seed.seed --reset` explicitly when a clean demo dataset is needed, so ordinary startup cannot erase local work.

# Docker usage

## Build and run

From the project root:

```bash
docker compose up --build
```

The API will be available at:

- http://127.0.0.1:8000
- http://127.0.0.1:8000/docs

## Stop the container

```bash
docker compose down
```

## Run the demo

```bash
docker compose exec api python scripts/demo.py
```

## Notes

- The container uses the default mock LLM mode, so no API key is required.
- Data is persisted in the local `data/` directory.

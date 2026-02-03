# Mainserver

Central orchestration service for a modular fruit detection and defect analysis pipeline.

**Requirements:** Python >= 3.10

## Overview

The **mainserver** is the single orchestrator in the system. It:

1. Monitors weight readings from a scale to detect when fruit is placed or removed.
2. Triggers image capture and runs detection pipelines when weight stabilizes.
3. Sends cropped fruit images to a defect detector (in parallel).
4. Aggregates results and publishes them to a UI service and a main online server.

All external modules (Weight, Camera, FruitDetector, DefectDetector, UI, MainServer) are passive HTTP services that respond to Brain's requests—they never initiate workflow calls.

## Project Structure

```
app/
├── api/             # FastAPI routes (health, manual triggers)
├── core/
│   ├── state_machine.py   # Weight-based state machine (IDLE ↔ ACTIVE)
│   ├── orchestrator.py    # Pipeline coordinator
│   └── image_ops.py       # Image cropping utilities
├── models/          # Pydantic schemas for all data contracts
├── services/        # HTTP clients for external services
├── config.py        # Settings (env-based via pydantic-settings)
├── dependencies.py  # FastAPI dependency injection
├── logging.py       # Structured logging setup
└── main.py          # Application factory
tests/
├── test_state_machine.py
└── test_orchestrator.py
```

## Configuration

Environment variables (or `.env` file):

| Variable               | Default                  | Description                          |
|------------------------|--------------------------|--------------------------------------|
| `APP_ENV`              | `dev`                    | `dev`, `prod`, or `test`             |
| `LOG_LEVEL`            | `INFO`                   | Logging verbosity                    |
| `WEIGHT_SERVICE_URL`   | `http://localhost:8100`  | Weight service base URL              |
| `CAMERA_SERVICE_URL`   | `http://localhost:8200`  | Camera service base URL              |
| `FRUIT_DETECTOR_URL`   | `http://localhost:8300`  | Fruit detector base URL              |
| `DEFECT_DETECTOR_URL`  | `http://localhost:8400`  | Defect detector base URL             |
| `UI_SERVICE_URL`       | `http://localhost:8500`  | UI service base URL                  |
| `MAIN_SERVER_URL <--unused`      | `http://localhost:8600`  | Main server base URL                 |
| `MIN_FRUIT_WEIGHT`     | `30.0`                   | Minimum weight (g) to trigger scan   |
| `SIGNIFICANT_DELTA`    | `20.0`                   | Weight change (g) to re-trigger scan |
| `WEIGHT_NOISE_EPSILON` | `5.0`                    | Max jitter (g) for stability check   |
| `STABLE_WINDOW_MS`     | `400`                    | Window (ms) for stability averaging  |
| `MIN_SCAN_INTERVAL_MS` | `2000`                   | Cooldown (ms) between scans          |
| `WEIGHT_POLL_INTERVAL_MS` | `150`                 | Polling interval (ms) for weight     |
| `ENABLE_WEIGHT_POLLING` | `true`                  | Set `false` in dev to rely on manual scans |

## Running

```bash
# Create and activate virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (using pip or your package manager)
pip install -e ".[test]"

# Start the service
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

## Testing

```bash
pytest tests/ -v
```

## API Endpoints

| Method | Path              | Description                              |
|--------|-------------------|------------------------------------------|
| GET    | `/healthz`        | Liveness probe                           |
| POST   | `/trigger-scan`   | Manually trigger a scan (for debugging)  |
| GET    | `/docs`           | Interactive API documentation (Swagger)  |
| GET    | `/redoc`          | Alternative API documentation (ReDoc)    |

**Manual Scan Request Body:**
```json
{
  "weight_grams": 150.5
}
```

## Architecture Notes

- **State Machine**: Explicit `IDLE` ↔ `ACTIVE` transitions based on stable weight readings.
- **Parallel Defect Detection**: Once bounding boxes are known, crops are sent concurrently.
- **Strict Validation**: All incoming/outgoing JSON is validated via Pydantic models.
- **Binary Image Transport**: Images are sent as `multipart/form-data`, never Base64 in JSON.
- **Graceful Error Handling**: Individual detector failures don't crash the pipeline; errors are logged with context.

## Docker

### Building the Image

```bash
docker build -t brain-service:latest .
```

### Running the Container

Basic run (with default settings):

```bash
docker run --rm -p 8000:8000 brain-service:latest
```

With environment variables for external services:

```bash
docker run --rm -p 8000:8000 \
  -e SERVICE_PORT=8000 \
  -e APP_ENV=prod \
  -e LOG_LEVEL=INFO \
  -e WEIGHT_SERVICE_URL=http://weight-service:8100 \
  -e CAMERA_SERVICE_URL=http://camera-service:8200 \
  -e FRUIT_DETECTOR_URL=http://fruit-detector:8300 \
  -e DEFECT_DETECTOR_URL=http://defect-detector:8400 \
  -e UI_SERVICE_URL=http://ui-service:8500 \
  -e MAIN_SERVER_URL=http://main-server:8600 \
  -e ENABLE_WEIGHT_POLLING=true \
  brain-service:latest
```

### Using Docker Compose

For local development with docker-compose:

```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f brain-service

# Stop the service
docker-compose down
```

Create a `.env` file to override defaults:

```env
SERVICE_PORT=8000
APP_ENV=dev
LOG_LEVEL=DEBUG
ENABLE_WEIGHT_POLLING=false
WEIGHT_SERVICE_URL=http://localhost:8100
CAMERA_SERVICE_URL=http://localhost:8200
FRUIT_DETECTOR_URL=http://localhost:8300
DEFECT_DETECTOR_URL=http://localhost:8400
UI_SERVICE_URL=http://localhost:8500
MAIN_SERVER_URL=http://localhost:8600
```

### Health Check

The service exposes a health endpoint at `/healthz`:

```bash
curl http://localhost:8000/healthz
# Returns: {"status": "ok"}
```

### Required Environment Variables

When running in Docker alongside other services, configure these URLs:

| Variable              | Description                  | Default                     |
|-----------------------|------------------------------|-----------------------------|
| `SERVICE_PORT`        | Port the service listens on  | `8000`                      |
| `WEIGHT_SERVICE_URL`  | Weight service endpoint      | `http://localhost:8100`     |
| `CAMERA_SERVICE_URL`  | Camera service endpoint      | `http://localhost:8200`     |
| `FRUIT_DETECTOR_URL`  | Fruit detector endpoint      | `http://localhost:8300`     |
| `DEFECT_DETECTOR_URL` | Defect detector endpoint     | `http://localhost:8400`     |
| `UI_SERVICE_URL`      | UI service endpoint          | `http://localhost:8500`     |
| `MAIN_SERVER_URL`     | Main server endpoint         | `http://localhost:8600`     |


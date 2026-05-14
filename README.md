# Wyolo Manager - Optuna Study Orchestrator

This component is the **central orchestrator** of the cluster. It coordinates hyperparameter optimization studies using **Optuna**, suggesting values and dispatching trials to workers via Celery.

---

## 🏗️ Project Structure

```text
.
├── src/                    # Application source code
│   ├── celery_config.py    # Celery app and routing config
│   ├── user_orchestrator.py # Main orchestration logic
│   └── config.yaml         # Default configuration
├── gradio/                 # Gradio UI source code
│   └── app.py              # UI implementation
├── docker/                 # Docker configuration
│   ├── Dockerfile          # Manager container definition
│   └── Dockerfile.gradio   # UI container definition
├── tests/                  # Unit and integration tests
├── Makefile                # Management commands
├── docker-compose.yml      # Orchestration for the manager
├── control_host.env        # Environment variables (local only)
└── requirements.txt        # Python dependencies
```

---

## 🚀 Quick Start

### 1. Setup Environment
Create and configure your local environment file:
```bash
make setup
```
Edit `control_host.env` and set the `REDIS_URL` to point to your Redis broker.

### 2. Build and Run
```bash
# Build the images
make build

# Start the orchestrator and UI
make up
```

The Gradio UI will be available at `http://localhost:7860`.

### 3. Management
*   **Logs**: `make logs`
*   **Stop**: `make down`
*   **Clean**: `make clean`

---

## 🛠️ Architecture

### Main Flow
1.  **User** uploads a YAML configuration via the **Gradio UI**.
2.  **UI** sends a `manage_study` task to the `managers` queue.
3.  **Manager** creates or loads an Optuna study.
4.  **Optuna** suggests hyperparameters for a trial.
5.  **Manager** dispatches a `train_on_gpu` task to the configured worker queue.
6.  **GPU Worker** executes the training and returns the metric (accuracy).
7.  **Manager** updates the study and repeats until `n_trials` is reached.
8.  **Manager** returns the best parameters found.

---

## ⚙️ Configuration

The manager expects a configuration object in the `manage_study` task. Example:

```yaml
sweeper:
  study_name: "yolo_optimization"
  direction: "maximize"
  n_trials: 50
  target_worker_queue: "gpus_high"
  search_space:
    train:
      lr0: ["loguniform", 1e-5, 1e-2]
      imgsz: ["range", 320, 640, 32]
```

---

**William R.** - AI Leader & Solutions Architect

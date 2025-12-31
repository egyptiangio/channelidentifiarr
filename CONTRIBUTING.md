# Contributing to ChannelIdentifiarr

Thank you for your interest. We welcome contributions.

---

## Building the Docker image
From the root project dir: ```docker build .```

## Backend Development with VSCode and UV

### 🖥️ UV Setup

1. [**Install UV**](https://docs.astral.sh/uv/getting-started/installation/)
2. Change directory to the backend folder and run:
    ```sh
    uv venv
    ```
3. Install dependencies:
    ```sh
    uv pip install -r requirements.txt
    ```

### 🛠️ App Setup

1. **Download** `channelidentifiarr.db`
2. **Create a `.env` file**. Example:
    ```env
    CHANNELIDENTIFIARR_BACKEND_LOG_LEVEL=DEBUG
    CHANNELIDENTIFIARR_DATABASE_PATH=./channelidentifiarr.db
    CHANNELIDENTIFIARR_FRONTEND_PATH=frontend
    CHANNELIDENTIFIARR_SETTINGS_PATH=./settings.json
    ```

### ▶️ Running in VSCode

1. Set the Python interpreter to the `.venv` folder created by UV
2. Use **Run/Debug** on `app.py`


# Contributing to ChannelIdentifiarr

Thank you for your interest. We welcome contributions.

---

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
    BACKEND_LOG_LEVEL=DEBUG
    DATABASE_PATH=./channelidentifiarr.db
    FRONTEND_PATH=frontend
    SETTINGS_PATH=./settings.json
    ```

### ▶️ Running in VSCode

1. Set the Python interpreter to the `.venv` folder created by UV
2. Use **Run/Debug** on `app.py`


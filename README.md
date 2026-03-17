# Backend API

This is the Flask backend for the WOLF AI application. It provides a RESTful API for all the application's features.

## Setup

### 1. Prerequisites

-   Python 3.8+
-   `pip` and `venv`

### 2. Installation

1.  **Clone the repository and navigate to the `backend` directory.**

2.  **Create and activate a virtual environment:**

    ```bash
    python -m venv venv
    ```

    -   On macOS/Linux: `source venv/bin/activate`
    -   On Windows: `venv\Scripts\activate`

3.  **Install the dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

### 3. Environment Variables

Create a file named `.env` in the `backend` directory and add the following variables.

**Required for development:**

```env
# A random, secret string for signing sessions and other security purposes.
# You can generate one with: python -c 'import secrets; print(secrets.token_hex(24))'
SECRET_KEY=your_secret_key
JWT_SECRET=your_jwt_secret_key

# The password for the default admin user (email: admin@wolf.ai)
# This is required for the initial database seeding.
ADMIN_PASS=your_strong_admin_password
```

**Optional for core functionality:**

```env
# API keys for different AI models
GROQ_API_KEY=
HF_API_TOKEN=
OPENROUTER_API_KEY=

# Google OAuth credentials for social login
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

### 4. Database Initialization

Before running the application for the first time, you need to create the database tables and seed the initial data (like the admin user).

Run the following command:

```bash
flask init-db
```

This will create a `wolf.db` SQLite file in the `backend` directory.

### 5. Running the Server

To start the development server, run:

```bash
flask run
```

The API will be available at `http://127.0.0.1:5000`.

## API Endpoints

The API is organized into several blueprints:

-   `/api/auth`: User authentication (register, login, me, Google OAuth).
-   `/api/chat`: Handling chat messages.
-   `/api/generate-image`: Image generation.
-   `/api/conversations`: Managing chat conversations.
-   `/api/upload`: File uploads.
-   `/api/admin`: Admin-only endpoints for stats, logs, settings, and user management.

All protected endpoints expect an `Authorization: Bearer <token>` header.

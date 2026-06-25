# Approve Bot

A production-ready Telegram bot for managing item assignments, approvals, and rejections.

## Features

### Admin Panel
- **Upload TXT**: Bulk upload items (removes empty lines and duplicates).
- **Stats**: View real-time counts for Pending, Assigned, Approved, and Rejected items.
- **Export**: Export items as `.txt` files based on their status.
- **Recent Activity**: View the last 10 user actions.
- **Clear Lists**: Reset Approved or Rejected lists.

### User Panel
- **Request Item**: Get the next available pending item.
- **Safety**: Only one item can be assigned at a time.
- **Approve/Reject**: Easy-to-use inline buttons for quick resolution.

## Tech Stack
- **Python 3.10+**
- **python-telegram-bot**: Modern async library for Telegram.
- **SQLAlchemy**: Database ORM with SQLite (thread-safe).
- **Dotenv**: Environment variable management.

## Setup Instructions

### 1. Prerequisites
- Python installed on your system.
- A Telegram Bot Token (get it from [@BotFather](https://t.me/botfather)).
- Your Telegram User ID (get it from [@userinfobot](https://t.me/userinfobot)).

### 2. Installation
1. Clone or download this repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### 3. Configuration
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and fill in your details:
   - `TELEGRAM_BOT_TOKEN`: Your bot token.
   - `ADMIN_IDS`: Comma-separated IDs of admin users (e.g., `123456,789012`).

### 4. Running the Bot
```bash
python main.py
```

## Folder Structure
- `database/`: Models and database manager.
- `handlers/`: Logic for admin and user interactions.
- `utils/`: Helpers and decorators.
- `config.py`: Configuration loader.
- `main.py`: Entry point.

## Safety & Race Conditions
The bot uses SQLAlchemy's `scoped_session` and `with_for_update()` to ensure that:
- Two users never receive the same item.
- Race conditions are prevented during item assignment.
- Data integrity is maintained across concurrent requests.

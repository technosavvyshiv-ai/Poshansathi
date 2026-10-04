"""PoshanSathi application entry point.

Run the development server with::

    python app.py
    # or
    flask --app app.py run
"""

from __future__ import annotations

from app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)

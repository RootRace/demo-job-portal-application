from app import create_app
from app.services.db import init_db, migrate_users_table
import os

app = create_app()

with app.app_context():
    init_db()
    migrate_users_table()

port = int(os.environ.get("PORT", 5000))

app.run(host="0.0.0.0", port=port, debug=True)

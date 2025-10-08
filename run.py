from app import create_app
from app.services.db import init_db
import os

app = create_app()

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
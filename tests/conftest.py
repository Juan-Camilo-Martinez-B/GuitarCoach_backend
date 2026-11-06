"""Las pruebas unitarias no deben heredar USE_DATABASE del .env local."""

import os

os.environ["USE_DATABASE"] = "false"
os.environ["GROQ_API_KEY"] = ""
os.environ["REDIS_URL"] = ""

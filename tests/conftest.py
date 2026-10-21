"""Las pruebas unitarias no deben heredar USE_DATABASE del .env local."""

import os

os.environ["USE_DATABASE"] = "false"

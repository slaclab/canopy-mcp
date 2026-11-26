"""Shared test setup for the canopy-mcp suite.

Some tests import canopy modules (the converter, the formula engine, the color
scheme), which read their settings when first imported.
"""

import os
from unittest.mock import patch

# Prevent pydantic-settings from reading the developer's local .env file.
# Tests must be deterministic regardless of .env contents. Env-var-based tests
# (monkeypatch.setenv) still work because EnvSettingsSource is a separate path.
patch("pydantic_settings.sources.providers.dotenv.dotenv_values", return_value={}).start()

# Seed an API-key registry before any canopy settings are read.
os.environ["CANOPY_API_KEYS"] = "test-read:read@*,test-write:read+write@*,test-admin:admin@*"

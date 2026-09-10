"""Test-only redirection of third-party application data into writable workspace."""
import os
from pathlib import Path
import platformdirs
root = os.environ.get('CORRLOG_TEST_APPDATA')
if root:
    platformdirs.user_data_path = lambda appname=None, *a, **kw: Path(root) / 'data' / (appname or '')
    platformdirs.user_cache_path = lambda appname=None, *a, **kw: Path(root) / 'cache' / (appname or '')

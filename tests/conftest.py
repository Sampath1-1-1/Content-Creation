import sys
from pathlib import Path

# Make `import studio` work when running `pytest` from the project folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

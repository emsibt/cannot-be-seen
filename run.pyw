"""Entry point. Run with pythonw to avoid a console window:

    .venv\\Scripts\\pythonw.exe run.pyw
"""

import sys

from cbs.app import main

if __name__ == "__main__":
    sys.exit(main())

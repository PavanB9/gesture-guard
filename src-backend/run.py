"""PyInstaller entry point.

Kept as a thin wrapper at the package root so the frozen binary imports the
``app`` package cleanly (relative imports inside ``app`` resolve correctly).
"""

from app.main import main

if __name__ == "__main__":
    main()

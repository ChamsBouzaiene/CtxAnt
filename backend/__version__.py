"""Single source of truth for the app version.

Kept in its own module (not just a constant in ``config.py`` or ``main.py``)
because:
  - The PyInstaller spec imports it to stamp CFBundleShortVersionString.
  - The in-app updater compares it against the remote ``latest.json`` feed.
  - Bumping a version should touch exactly one file so release PRs are clean.

Semver: MAJOR.MINOR.PATCH. No pre-release suffixes for now — we ship from
``main`` and cut a tag per release. If we ever want betas, add a
``-beta.N`` suffix and teach updater._newer() to honour it.
"""

__version__ = "0.1.0"

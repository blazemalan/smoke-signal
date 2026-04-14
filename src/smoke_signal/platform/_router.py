"""Platform dispatch — import the right backend based on OS."""

import sys

if sys.platform == "win32":
    from smoke_signal.platform._windows import *  # noqa: F401,F403
elif sys.platform == "darwin":
    from smoke_signal.platform._macos import *  # noqa: F401,F403
else:
    # Linux and others use the macOS-like backend (subprocess open, fcntl, etc.)
    from smoke_signal.platform._macos import *  # noqa: F401,F403

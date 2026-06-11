import tkinter as tk
from smoke_signal.setup_wizard import SetupWizard
from smoke_signal.watcher.dashboard import DashboardWindow

w = SetupWizard()
# Attempt to initialize and build steps without blocking
# Actually SetupWizard requires user interaction... let's mock it

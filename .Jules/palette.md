## 2026-06-11 - Add Enter Key Support for Text Entries
**Learning:** Users instinctively press "Enter" after typing in a single-line text input field, especially for actions like search, verify, or quick submit. In desktop GUI applications like Tkinter, this behavior doesn't happen automatically and requires explicit key bindings.
**Action:** Always bind the `<Return>` event to the primary action associated with a `tk.Entry` widget to reduce reliance on mouse clicks and improve keyboard accessibility.

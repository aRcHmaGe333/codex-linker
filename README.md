# Codex Linker

Codex VSCode produces clickable links that open invalid browser paths instead of workspace files.
This repo reproduces that failure and provides a working implementation that fixes it.
It makes file and folder paths clickable in VS Code text documents, and includes a demo chat panel that proves the renderer side.

## Contents

- `extension.js` — the extension
- `build_vsix.bat` — builds the `.vsix`
- `DEMO_TRANSCRIPT.md` — sample chat-like output with paths
- `PATCH.md` — integration note for a chat renderer
- `README.md` — exact use flow

## Fastest path

1. Extract this zip anywhere.
2. Double-click `build_vsix.bat`.
3. If npm asks to continue, reply `Y`.
4. Wait for `codex-linker-0.1.0.vsix` to appear in the same folder.
5. In VS Code press `Ctrl+Shift+P`.
6. Run `Extensions: Install from VSIX`.
7. Pick `codex-linker-0.1.0.vsix`.
8. Restart VS Code.
9. Press `Ctrl+Shift+P` and run `Codex Linker: Open Demo Chat`.

## What to expect

Inside the demo chat, these should be clickable when they exist on your machine or inside the current workspace:

- `file:///C:/...`
- `C:\...`
- `src/file.py`
- `src/file.py:123`
- `folder/subfolder/`

## Text-document behavior

Open any `.md` or `.txt` file, paste paths like the examples above, then Ctrl+click them.

## Notes

- No terminal step is required unless you prefer running the `.bat` from a terminal.
- This repo does not modify the official Codex extension.
- The demo chat is there to prove the feature and give you something concrete to publish or show.

## IP Claim

This repository includes the IPClaim toolkit and an explicit claim file. See `CLAIM.md` and the `IPClaim/` folder for the license templates, verification instructions, and the timestamping workflow.

# PATCH

This repo proves two pieces separately:

1. Text-surface linkification through a VS Code `DocumentLinkProvider`
2. Chat-renderer linkification through a webview that turns paths into command URIs

## Integration target

Any chat extension renderer that already owns its own output surface.

## Capability

Detect and link:

- `file:///C:/...`
- `C:\...`
- `relative/path.py`
- `relative/path.py:123`
- folder paths when they exist

## Minimal integration idea

In the extension's chat output pipeline:

- run message text through a path matcher
- resolve against current workspace
- emit clickable anchors or command URIs
- open files at line or reveal folders in OS

## Practical point

This does not depend on Copilot internals.
It is ordinary extension-side code.

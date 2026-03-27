const vscode = require('vscode');
const path = require('path');
const fs = require('fs');

function activate(context) {
  const linkProvider = {
    provideDocumentLinks(document) {
      const text = document.getText();
      const matches = collectMatches(text, getWorkspaceBase());
      return matches.map(match => {
        const start = document.positionAt(match.start);
        const end = document.positionAt(match.end);
        const target = buildCommandUri(match);
        return new vscode.DocumentLink(new vscode.Range(start, end), target);
      });
    }
  };

  context.subscriptions.push(
    vscode.languages.registerDocumentLinkProvider(
      [{ scheme: 'file' }, { scheme: 'untitled' }],
      linkProvider
    )
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('codexLinker.openDemoChat', () => openDemoChat(context))
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('codexLinker.openTranscript', async () => {
      const folder = context.extensionUri;
      const transcriptUri = vscode.Uri.joinPath(folder, 'DEMO_TRANSCRIPT.md');
      const doc = await vscode.workspace.openTextDocument(transcriptUri);
      await vscode.window.showTextDocument(doc, { preview: false });
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('codexLinker.openPath', async (payload) => {
      try {
        if (!payload || !payload.path) {
          vscode.window.showErrorMessage('Codex Linker: missing path.');
          return;
        }
        const rawPath = payload.path;
        const line = Math.max(1, Number(payload.line || 1));
        const absolutePath = resolvePath(rawPath, getWorkspaceBase());

        if (!absolutePath || !fs.existsSync(absolutePath)) {
          vscode.window.showErrorMessage(`Codex Linker: path not found: ${rawPath}`);
          return;
        }

        const stat = fs.statSync(absolutePath);
        if (stat.isDirectory()) {
          const uri = vscode.Uri.file(absolutePath);
          await vscode.commands.executeCommand('revealFileInOS', uri);
          return;
        }

        const uri = vscode.Uri.file(absolutePath);
        const doc = await vscode.workspace.openTextDocument(uri);
        const editor = await vscode.window.showTextDocument(doc, { preview: false });
        const zeroBasedLine = Math.max(0, line - 1);
        const position = new vscode.Position(zeroBasedLine, 0);
        editor.selection = new vscode.Selection(position, position);
        editor.revealRange(new vscode.Range(position, position));
      } catch (error) {
        vscode.window.showErrorMessage(`Codex Linker: ${error && error.message ? error.message : String(error)}`);
      }
    })
  );
}

function deactivate() {}

function openDemoChat(context) {
  const panel = vscode.window.createWebviewPanel(
    'codexLinkerDemo',
    'Codex Linker Demo Chat',
    vscode.ViewColumn.One,
    {
      enableCommandUris: true
    }
  );

  const transcriptPath = vscode.Uri.joinPath(context.extensionUri, 'DEMO_TRANSCRIPT.md');
  const transcript = fs.readFileSync(transcriptPath.fsPath, 'utf8');
  panel.webview.html = buildDemoHtml(transcript, getWorkspaceBase());
}

function buildDemoHtml(transcript, workspaceBase) {
  const escaped = escapeHtml(transcript);
  const html = linkifyHtml(escaped, workspaceBase);
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
body { font-family: var(--vscode-font-family); color: var(--vscode-editor-foreground); background: var(--vscode-editor-background); padding: 16px; line-height: 1.45; }
pre { white-space: pre-wrap; word-break: break-word; }
a { color: var(--vscode-textLink-foreground); text-decoration: none; }
a:hover { text-decoration: underline; }
.note { margin-bottom: 14px; opacity: 0.85; }
</style>
</head>
<body>
<div class="note">Demo chat output with clickable file and folder paths.</div>
<pre>${html}</pre>
</body>
</html>`;
}

function linkifyHtml(escapedText, workspaceBase) {
  const matches = collectMatches(unescapeHtml(escapedText), workspaceBase);
  if (matches.length === 0) return escapedText;

  let out = '';
  let cursor = 0;
  for (const match of matches) {
    out += escapedText.slice(cursor, match.start);
    const visible = escapedText.slice(match.start, match.end);
    const href = buildCommandUri(match).toString().replace(/"/g, '&quot;');
    out += `<a href="${href}">${visible}</a>`;
    cursor = match.end;
  }
  out += escapedText.slice(cursor);
  return out;
}

function buildCommandUri(match) {
  const args = encodeURIComponent(JSON.stringify([{ path: match.path, line: match.line || 1 }]));
  return vscode.Uri.parse(`command:codexLinker.openPath?${args}`);
}

function getWorkspaceBase() {
  return vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders.length
    ? vscode.workspace.workspaceFolders[0].uri.fsPath
    : '';
}

function collectMatches(text, workspaceBase) {
  const found = [];
  const seen = new Set();

  const regexes = [
    { type: 'fileuri', regex: /file:\/\/\/[A-Za-z]:\/[^\s)\]"'`<>]+/g },
    { type: 'winabs', regex: /[A-Za-z]:\\[^\r\n\t"'`<>]+/g },
    { type: 'rel', regex: /(?:(?:\.{1,2}\/)|(?:[A-Za-z0-9_\-]+\/))[A-Za-z0-9_./\-]+/g }
  ];

  for (const item of regexes) {
    let match;
    while ((match = item.regex.exec(text)) !== null) {
      const raw = match[0].replace(/[),.;]+$/, '');
      const endTrim = match[0].length - raw.length;
      const parsed = splitLineSuffix(raw, item.type === 'winabs');
      const resolved = resolvePath(parsed.path, workspaceBase);

      if (!resolved || !fs.existsSync(resolved)) continue;

      const key = `${match.index}:${parsed.path}:${parsed.line}`;
      if (seen.has(key)) continue;
      seen.add(key);

      found.push({
        start: match.index,
        end: match.index + raw.length,
        path: parsed.path,
        line: parsed.line
      });

      if (endTrim > 0) {
        item.regex.lastIndex -= endTrim;
      }
    }
  }

  found.sort((a, b) => a.start - b.start);

  // remove overlaps
  const filtered = [];
  let lastEnd = -1;
  for (const item of found) {
    if (item.start < lastEnd) continue;
    filtered.push(item);
    lastEnd = item.end;
  }
  return filtered;
}

function splitLineSuffix(raw, isWindowsAbsolute) {
  if (raw.startsWith('file:///')) {
    const m = raw.match(/^(file:\/\/\/[A-Za-z]:\/.+?)(?::(\d+))?$/);
    if (m) return { path: m[1], line: Number(m[2] || 1) };
    return { path: raw, line: 1 };
  }

  if (isWindowsAbsolute) {
    const m = raw.match(/^([A-Za-z]:\\.+?)(?::(\d+))?$/);
    if (m) return { path: m[1], line: Number(m[2] || 1) };
    return { path: raw, line: 1 };
  }

  const m = raw.match(/^(.+?)(?::(\d+))?$/);
  return { path: m ? m[1] : raw, line: m && m[2] ? Number(m[2]) : 1 };
}

function resolvePath(rawPath, workspaceBase) {
  if (!rawPath) return '';
  if (rawPath.startsWith('file:///')) {
    const withoutScheme = rawPath.replace(/^file:\/\/\//, '');
    return path.normalize(withoutScheme);
  }
  if (/^[A-Za-z]:\\/.test(rawPath)) {
    return path.normalize(rawPath);
  }
  if (/^(?:\.{1,2}\/|[A-Za-z0-9_\-]+\/)/.test(rawPath)) {
    if (!workspaceBase) return '';
    return path.normalize(path.join(workspaceBase, rawPath));
  }
  return '';
}

function escapeHtml(value) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function unescapeHtml(value) {
  return value
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&');
}

module.exports = { activate, deactivate };
let vscode;
function getVscode() {
  if (!vscode) {
    vscode = require('vscode');
  }
  return vscode;
}

const PRIMARY_COMMAND = 'promptOptimizer.optimizeSelection';
const COPY_COMMAND = 'promptOptimizer.copyOptimizedPrompt';
const REPLACE_COMMAND = 'promptOptimizer.replaceSelectionWithOptimized';
const INSERT_COMMAND = 'promptOptimizer.insertOptimizedBelow';
const LEGACY_COPY_COMMAND = 'promptOptimizer.copySelectionAndOpenOfficialOptimizer';
const LEGACY_OPEN_COMMAND = 'promptOptimizer.openOfficialOptimizer';
const PRESETS = ['General', 'Codex task', 'Bug report', 'Research request'];
const stateByEditor = new Map();

function getConfig() {
  return getVscode().workspace.getConfiguration('promptOptimizer');
}

function getSelection(editor) {
  if (!editor || !editor.selection || editor.selection.isEmpty) {
    return { editor, text: '', selection: editor ? editor.selection : undefined };
  }
  return {
    editor,
    text: editor.document.getText(editor.selection),
    selection: editor.selection
  };
}

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function extractCodeBlocks(text) {
  const blocks = [];
  const replaced = text.replace(/```[\s\S]*?```/g, (match) => {
    const token = `__CODE_BLOCK_${blocks.length}__`;
    blocks.push(match);
    return token;
  });
  return { text: replaced, blocks };
}

function restoreCodeBlocks(text, blocks) {
  return blocks.reduce((current, block, index) => current.replace(new RegExp(escapeRegExp(`__CODE_BLOCK_${index}__`), 'g'), block), text);
}

function splitLines(text) {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => Boolean(line) && !/^__CODE_BLOCK_\d+__$/.test(line));
}

function unique(items) {
  return [...new Set(items.filter(Boolean))];
}

function detectConstraints(lines) {
  const patterns = /(must|should|do not|don't|avoid|never|only|exactly|without|keep|preserve|required)/i;
  return unique(lines.filter((line) => patterns.test(line)));
}

function detectDeliverables(lines) {
  const patterns = /(return|deliver|output|respond|provide|include|format|write|generate|summarize|report|list|show)/i;
  return unique(lines.filter((line) => patterns.test(line)));
}

function detectInputs(lines) {
  const patterns = /(http|https|path|file|repo|project|stack trace|error|log|code|snippet|selection|json|yaml|toml|md|markdown|image|screenshot)/i;
  return unique(lines.filter((line) => patterns.test(line)));
}

function summarizeObjective(lines, preset) {
  const first = lines.find((line) => line.length > 0) || 'Optimize the prompt.';
  if (preset === 'Bug report') {
    return first.match(/fix|bug|error|issue|failure/i) ? first : `Investigate and fix: ${first}`;
  }
  if (preset === 'Research request') {
    return first.match(/research|compare|find|analyze/i) ? first : `Research request: ${first}`;
  }
  if (preset === 'Codex task') {
    return first.match(/implement|update|refactor|verify|debug|install/i) ? first : `Codex task: ${first}`;
  }
  return first;
}

function buildPresetNotes(preset) {
  switch (preset) {
    case 'Codex task':
      return [
        'Prefer concrete implementation steps and explicit verification commands.',
        'Call out blockers, risks, and rollback paths rather than guessing.'
      ];
    case 'Bug report':
      return [
        'State the observed behavior, expected behavior, likely cause, and reproduction steps.',
        'Preserve exact error text and environment details.'
      ];
    case 'Research request':
      return [
        'Ask for sourced findings, comparisons, and a concise recommendation.',
        'Separate confirmed facts from inference.'
      ];
    default:
      return [
        'Clarify the objective, constraints, and desired output.',
        'Keep wording concise and action-oriented.'
      ];
  }
}

function renderSection(title, items, fallback) {
  const values = unique(items);
  if (!values.length && !fallback) {
    return '';
  }
  const body = values.length ? values.map((item) => `- ${item}`).join('\n') : `- ${fallback}`;
  return `## ${title}\n${body}`;
}

function optimizePrompt(rawText, preset) {
  const trimmed = rawText.trim();
  const { text: withoutCode, blocks } = extractCodeBlocks(trimmed);
  const lines = splitLines(withoutCode);
  const objective = summarizeObjective(lines, preset);
  const constraints = detectConstraints(lines);
  const deliverables = detectDeliverables(lines);
  const inputs = detectInputs(lines);
  const notes = buildPresetNotes(preset);
  const sections = [
    `# Optimized Prompt\n\n## Objective\n${objective}`,
    renderSection('Context', lines.slice(0, Math.min(lines.length, 6)), 'Use the provided selection as the source context.'),
    renderSection('Constraints', constraints, 'Preserve all explicit requirements, code blocks, and non-negotiable constraints.'),
    renderSection('Inputs', inputs, 'Use the selected text and any embedded code blocks as authoritative inputs.'),
    renderSection('Requested Output', deliverables, 'Return a direct, structured response with explicit next steps and verification details where relevant.'),
    renderSection('Optimization Notes', notes)
  ].filter((line) => Boolean(line) && !/^__CODE_BLOCK_\d+__$/.test(line));

  let optimized = sections.join('\n\n');
  if (blocks.length) {
    optimized += `\n\n## Preserved Code / Structured Content\n${blocks.join('\n\n')}`;
  }
  return restoreCodeBlocks(optimized, blocks);
}

function stateKey(editor) {
  if (!editor) {
    return '__global__';
  }
  return `${editor.document.uri.toString()}::${editor.selection.start.line}:${editor.selection.start.character}-${editor.selection.end.line}:${editor.selection.end.character}`;
}

async function choosePreset() {
  const config = getConfig();
  const defaultPreset = config.get('defaultPreset', 'General');
  const picks = PRESETS.map((label) => ({
    label,
    description: label === defaultPreset ? 'Default preset' : undefined
  }));
  const picked = await getVscode().window.showQuickPick(picks, {
    title: 'Optimize Prompt',
    placeHolder: 'Choose an optimization preset'
  });
  return picked ? picked.label : defaultPreset;
}

async function showDiff(original, optimized, languageId) {
  const left = await getVscode().workspace.openTextDocument({ language: languageId || 'markdown', content: original });
  const right = await getVscode().workspace.openTextDocument({ language: languageId || 'markdown', content: optimized });
  await getVscode().commands.executeCommand('vscode.diff', left.uri, right.uri, 'Prompt Optimizer: Original ↔ Optimized', { preview: true });
}

async function copyOptimizedText(optimized) {
  await getVscode().env.clipboard.writeText(optimized);
  getVscode().window.showInformationMessage('Optimized prompt copied to clipboard.');
}

async function replaceSelection(editor, selection, optimized) {
  await editor.edit((editBuilder) => {
    editBuilder.replace(selection, optimized);
  });
}

async function insertBelow(editor, selection, optimized) {
  const insertPos = selection.end;
  const prefix = selection.end.character === 0 ? '' : '\n';
  await editor.edit((editBuilder) => {
    editBuilder.insert(insertPos, `${prefix}${optimized}`);
  });
}

function rememberResult(editor, selection, preset, original, optimized) {
  stateByEditor.set(stateKey(editor), { editor, selection, preset, original, optimized, languageId: editor.document.languageId });
}

function getRememberedResult(editor) {
  return stateByEditor.get(stateKey(editor));
}

async function optimizeSelectionFlow({ preset: explicitPreset, autoCopy = false, autoReplace = false, autoInsert = false } = {}) {
  const editor = getVscode().window.activeTextEditor;
  const { text, selection } = getSelection(editor);
  if (!editor || !text.trim()) {
    getVscode().window.showWarningMessage('Select prompt text in the active editor first.');
    return;
  }
  const maxSelectionLength = Number(getConfig().get('maxSelectionLength', 50000));
  if (text.length > maxSelectionLength) {
    getVscode().window.showErrorMessage(`Selection is ${text.length} characters; increase promptOptimizer.maxSelectionLength or use a smaller selection.`);
    return;
  }

  const preset = explicitPreset || await choosePreset();
  const optimized = optimizePrompt(text, preset);
  rememberResult(editor, selection, preset, text, optimized);

  if (getConfig().get('openDiffByDefault', true)) {
    await showDiff(text, optimized, editor.document.languageId);
  }

  if (autoReplace) {
    await replaceSelection(editor, selection, optimized);
    return;
  }
  if (autoInsert) {
    await insertBelow(editor, selection, optimized);
    return;
  }
  if (autoCopy) {
    await copyOptimizedText(optimized);
    return;
  }

  const action = await getVscode().window.showInformationMessage(
    `Optimized prompt ready (${preset}).`,
    'Replace',
    'Insert Below',
    'Copy'
  );
  if (action === 'Replace') {
    await replaceSelection(editor, selection, optimized);
  } else if (action === 'Insert Below') {
    await insertBelow(editor, selection, optimized);
  } else if (action === 'Copy') {
    await copyOptimizedText(optimized);
  }
}

async function useRememberedOrOptimize(mode) {
  const editor = getVscode().window.activeTextEditor;
  const remembered = getRememberedResult(editor);
  if (remembered) {
    if (mode === 'copy') return copyOptimizedText(remembered.optimized);
    if (mode === 'replace') return replaceSelection(remembered.editor, remembered.selection, remembered.optimized);
    if (mode === 'insert') return insertBelow(remembered.editor, remembered.selection, remembered.optimized);
  }
  return optimizeSelectionFlow({
    autoCopy: mode === 'copy',
    autoReplace: mode === 'replace',
    autoInsert: mode === 'insert'
  });
}

function updateStatusBar(item) {
  const show = getConfig().get('showStatusBar', true);
  if (!show) {
    item.hide();
    return;
  }
  const editor = getVscode().window.activeTextEditor;
  const hasSelection = Boolean(getSelection(editor).text.trim());
  item.text = hasSelection ? '$(sparkle) Optimize Prompt' : '$(sparkle) Prompt Optimizer';
  item.tooltip = hasSelection
    ? 'Optimize the selected prompt locally and open an inline diff.'
    : 'Select text to optimize it locally.';
  item.command = PRIMARY_COMMAND;
  item.show();
}

function activate(context) {
  const statusBarItem = getVscode().window.createStatusBarItem(getVscode().StatusBarAlignment.Right, 1000);
  context.subscriptions.push(
    statusBarItem,
    getVscode().commands.registerCommand(PRIMARY_COMMAND, () => optimizeSelectionFlow()),
    getVscode().commands.registerCommand(COPY_COMMAND, () => useRememberedOrOptimize('copy')),
    getVscode().commands.registerCommand(REPLACE_COMMAND, () => useRememberedOrOptimize('replace')),
    getVscode().commands.registerCommand(INSERT_COMMAND, () => useRememberedOrOptimize('insert')),
    getVscode().commands.registerCommand(LEGACY_COPY_COMMAND, () => useRememberedOrOptimize('copy')),
    getVscode().commands.registerCommand(LEGACY_OPEN_COMMAND, () => optimizeSelectionFlow()),
    getVscode().window.onDidChangeActiveTextEditor(() => updateStatusBar(statusBarItem)),
    getVscode().window.onDidChangeTextEditorSelection(() => updateStatusBar(statusBarItem)),
    getVscode().workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration('promptOptimizer')) {
        updateStatusBar(statusBarItem);
      }
    })
  );
  updateStatusBar(statusBarItem);
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
  optimizePrompt
};

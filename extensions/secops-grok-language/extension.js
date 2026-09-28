const vscode = require('vscode');
const { formatSecOpsGrok } = require('./formatter');

/**
 * Activates the SecOps Grok language support extension.
 * Registers the document formatting edit provider for 'secopsgrok'.
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
    const provider = vscode.languages.registerDocumentFormattingEditProvider('secopsgrok', {
        provideDocumentFormattingEdits(document, options, token) {
            const text = document.getText();
            const formatted = formatSecOpsGrok(text, options);
            if (formatted === text) {
                return [];
            }
            const lastLineIndex = document.lineCount - 1;
            const lastLine = document.lineAt(lastLineIndex);
            const fullRange = new vscode.Range(
                new vscode.Position(0, 0),
                lastLine.range.end
            );
            return [vscode.TextEdit.replace(fullRange, formatted)];
        }
    });

    context.subscriptions.push(provider);
}

function deactivate() { }

module.exports = {
    activate,
    deactivate
};

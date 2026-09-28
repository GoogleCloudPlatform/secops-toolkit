/**
 * SecOps Grok Document Formatter
 *
 * Formats Google SecOps (Chronicle) Logstash Grok parser syntax:
 * - Configurable indentation (defaults to 4 spaces)
 * - Normalizes combined '} else {' and '} else if [...] {' placement
 * - Normalizes spacing around '=>', comparison operators, commas, and block braces
 * - Preserves embedded JavaScript in `code { javascript => `...` }` verbatim
 * - Collapses consecutive empty lines to a maximum of one blank line
 * - Ensures single trailing newline
 */

/**
 * Formats SecOps Grok parser text.
 * @param {string} text - The input document text.
 * @param {object} [options] - Formatting options (e.g. { tabSize: 4, insertSpaces: true }).
 * @returns {string} - The formatted document text.
 */
function formatSecOpsGrok(text, options) {
    const tabSize = (options && options.tabSize) || 4;
    const insertSpaces = options && options.insertSpaces !== undefined ? options.insertSpaces : true;
    const indentUnit = insertSpaces ? ' '.repeat(tabSize) : '\t';

    const rawLines = text.split(/\r?\n/);
    const preprocessedLines = [];

    // Prepass: Normalize and combine solitary '}' followed by 'else' or 'else if'
    // Also track multi-line backtick template literals (embedded JS)
    let inBacktick = false;

    for (let i = 0; i < rawLines.length; i++) {
        let line = rawLines[i];
        let trimmed = line.trim();

        // Check backtick toggles (verbatim JS code)
        if (!inBacktick && trimmed.includes('`')) {
            let btCount = (trimmed.match(/`/g) || []).length;
            if (btCount % 2 === 1) {
                inBacktick = true;
            }
            preprocessedLines.push(line);
            continue;
        } else if (inBacktick) {
            if (trimmed.includes('`')) {
                let btCount = (trimmed.match(/`/g) || []).length;
                if (btCount % 2 === 1) {
                    inBacktick = false;
                }
            }
            preprocessedLines.push(line);
            continue;
        }

        // Outside backticks: check if line starts with 'else' or 'else if'
        // and previous non-blank line in preprocessedLines was a lone '}'
        if (/^else(\s+if\b|\s*\{)/.test(trimmed)) {
            let j = preprocessedLines.length - 1;
            while (j >= 0 && preprocessedLines[j].trim() === '') {
                j--;
            }
            if (j >= 0 && preprocessedLines[j].trim() === '}') {
                preprocessedLines[j] = preprocessedLines[j].trimEnd() + ' ' + trimmed;
                // Pop any intervening blank lines
                while (preprocessedLines.length > j + 1) {
                    preprocessedLines.pop();
                }
                continue;
            }
        }

        preprocessedLines.push(line);
    }

    // Format lines and calculate indentation
    const resultLines = [];
    let indentLevel = 0;
    let insideBackticks = false;
    let consecutiveBlankLines = 0;

    for (let i = 0; i < preprocessedLines.length; i++) {
        let rawLine = preprocessedLines[i];
        let trimmed = rawLine.trim();

        // Verbatim block handling
        if (insideBackticks) {
            if (trimmed.includes('`')) {
                let btCount = (trimmed.match(/`/g) || []).length;
                if (btCount % 2 === 1) {
                    insideBackticks = false;
                }
            }
            resultLines.push(rawLine);
            consecutiveBlankLines = 0;
            continue;
        }

        // Empty line handling (collapse runs of multiple empty lines to max 1)
        if (trimmed === '') {
            if (consecutiveBlankLines === 0 && resultLines.length > 0) {
                resultLines.push('');
                consecutiveBlankLines++;
            }
            continue;
        }
        consecutiveBlankLines = 0;

        // Check if this line begins a backtick block
        if (trimmed.includes('`')) {
            let btCount = (trimmed.match(/`/g) || []).length;
            if (btCount % 2 === 1) {
                insideBackticks = true;
            }
        }

        // Normalize spacing within line (outside quotes and comments)
        let normalizedLine = normalizeLineSpacing(trimmed);

        // Calculate leading closing delimiters for this line
        let leadingCloses = countLeadingCloses(normalizedLine);
        let lineIndent = Math.max(0, indentLevel - leadingCloses);

        resultLines.push(indentUnit.repeat(lineIndent) + normalizedLine);

        // Update indentLevel for subsequent lines
        let netDelta = computeNetIndentDelta(normalizedLine);
        indentLevel = Math.max(0, indentLevel + netDelta);
    }

    // Trim trailing empty lines
    while (resultLines.length > 0 && resultLines[resultLines.length - 1] === '') {
        resultLines.pop();
    }

    return resultLines.join('\n') + '\n';
}

/**
 * Normalizes spacing inside a line outside quotes and comments.
 * @param {string} line - Trimmed single line of code.
 * @returns {string} - Formatted line.
 */
function normalizeLineSpacing(line) {
    if (line.startsWith('#')) {
        // Comment line: normalize space after '#' if followed immediately by alphanumeric text
        if (/^#[a-zA-Z0-9]/.test(line)) {
            return '# ' + line.slice(1);
        }
        return line;
    }

    // Tokenize line into strings, comments, and code
    let tokens = [];
    let i = 0;
    let len = line.length;
    let currentCode = '';

    while (i < len) {
        let char = line[i];

        if (char === '"' || char === "'") {
            if (currentCode) {
                tokens.push({ type: 'code', val: currentCode });
                currentCode = '';
            }
            let quote = char;
            let strVal = quote;
            i++;
            while (i < len) {
                let c = line[i];
                strVal += c;
                if (c === '\\') {
                    i++;
                    if (i < len) {
                        strVal += line[i];
                    }
                } else if (c === quote) {
                    i++;
                    break;
                }
                i++;
            }
            tokens.push({ type: 'string', val: strVal });
            continue;
        }

        if (char === '#' && (i === 0 || /\s/.test(line[i - 1]))) {
            if (currentCode) {
                tokens.push({ type: 'code', val: currentCode });
                currentCode = '';
            }
            tokens.push({ type: 'comment', val: line.slice(i) });
            break;
        }

        currentCode += char;
        i++;
    }

    if (currentCode) {
        tokens.push({ type: 'code', val: currentCode });
    }

    // Process code tokens for spacing (never touching string or comment contents)
    for (let t of tokens) {
        if (t.type === 'code') {
            let s = t.val;
            // Normalize =>
            s = s.replace(/\s*=>\s*/g, ' => ');
            // Normalize comparison operators: ==, !=, =~, !~, <=, >=
            s = s.replace(/\s*(==|!=|=~|!~|<=|>=)\s*/g, ' $1 ');
            // Normalize < and > when in comparison context (e.g. [field] < 100)
            s = s.replace(/(\])\s*(<|>)\s*(\d+)/g, '$1 $2 $3');
            // Normalize spacing before {
            s = s.replace(/([^\s{])\{/g, '$1 {');
            // Normalize spacing after } when followed by else
            s = s.replace(/\}\s*else/g, '} else');
            // Normalize commas: ensure single space after comma
            s = s.replace(/,\s*/g, ', ');
            // Collapse multiple spaces in code
            s = s.replace(/  +/g, ' ');
            t.val = s;
        }
    }

    let out = tokens.map(t => t.val).join('').trim();
    // Preserve empty blocks cleanly: e.g. "statedump {}"
    out = out.replace(/statedump\s*\{\s*\}/g, 'statedump {}');
    // Ensure single space before inline comments
    out = out.replace(/\s+#/, ' #');
    return out;
}

/**
 * Counts leading closing delimiters '}', ']', ')' on a line.
 * @param {string} line
 * @returns {number}
 */
function countLeadingCloses(line) {
    let count = 0;
    let i = 0;
    while (i < line.length) {
        let c = line[i];
        if (c === '}' || c === ']' || c === ')') {
            count++;
            i++;
            while (i < line.length && /\s/.test(line[i])) i++;
        } else {
            break;
        }
    }
    return count;
}

/**
 * Computes net change in open delimiters '{', '[', '(' vs '}', ']', ')'
 * outside strings and comments on a line.
 * @param {string} line
 * @returns {number}
 */
function computeNetIndentDelta(line) {
    let delta = 0;
    let inDQuote = false;
    let inSQuote = false;

    for (let i = 0; i < line.length; i++) {
        let c = line[i];
        if (c === '\\' && (inDQuote || inSQuote)) {
            i++;
            continue;
        }
        if (c === '"' && !inSQuote) {
            inDQuote = !inDQuote;
            continue;
        }
        if (c === "'" && !inDQuote) {
            inSQuote = !inSQuote;
            continue;
        }
        if (inDQuote || inSQuote) continue;

        if (c === '#') {
            break;
        }

        if (c === '{' || c === '[' || c === '(') {
            delta++;
        } else if (c === '}' || c === ']' || c === ')') {
            delta--;
        }
    }
    return delta;
}

module.exports = {
    formatSecOpsGrok
};

# Google SecOps Grok Language Support

Visual Studio Code extension providing syntax highlighting and automated document formatting for the Google Security Operations flavor of the Logstash Grok parser configuration files.

## Getting Started

### Option 1: Direct Copy to Extensions Directory

Copy the `secops-grok-language` folder directly into your VS Code extensions directory:

- Linux / macOS: `~/.vscode/extensions/`
- Windows: `%USERPROFILE%\.vscode\extensions`

Restart or reload VS Code after copying.

### Option 2: Package as VSIX and Install

Package the extension using `@vscode/vsce`:

```bash
npx @vscode/vsce package
```

Install the generated `.vsix` file:

```bash
code --install-extension secops-grok-language-0.0.1.vsix
```

Or via GUI: Open the *Extensions* view (`Ctrl+Shift+X` / `Cmd+Shift+X`), click the `...` (*Views and More Actions*) menu at the top right, and select *Install from VSIX...*.

## Features

- **Document Formatting**:
  - Configurable 4-space indentation by default, honoring user-configured editor tab settings (`editor.tabSize`, `editor.insertSpaces`).
  - Standardizes combined conditional placement (`} else {` and `} else if [...] {`).
  - Normalizes single-space consistency around hash-rockets (`"key" => "value"`), comparison operators (`==`, `!=`, `=~`, `!~`, `<=`, `>=`, `<`, `>`), and commas.
  - Normalizes opening brace spacing (`filter {`, `mutate {`, `if [...] {`) while cleanly preserving empty blocks (`statedump {}`).
  - Preserves embedded JavaScript in `code { javascript => `...` }` verbatim to protect template literals, regexes, and code logic.
  - Automatically collapses excessive consecutive blank lines down to a single empty line.
  - Ensures a single trailing newline at the end of the file.

- **Syntax Highlighting**:
  - *Filter Blocks*: Highlighting for `filter`, `grok`, `mutate`, `json`, `xml`, `kv`, `csv`, `date`, `base64`, `drop`, `statedump`, and `code`.
  - *Mutate Directives*: Highlighting for `replace`, `merge`, `convert`, `gsub`, `lowercase`, `uppercase`, `rename`, `remove_field`, `copy`, and `split`.
  - *Filter Options*: Highlighting for `source`, `target`, `on_error`, `match`, `overwrite`, `match_all`, `xpath`, `separator`, `field_split`, `value_split`, `whitespace`, `trim_value`, `trim_key`, `include_keys`, `exclude_keys`, `array_function`, `encoding`, `timezone`, `rebase`, `tag`, `label`, and `javascript`.
  - *Grok Pattern Breakdown*: Deconstructs Grok patterns (`%{PATTERN:field:type}`) into distinct scopes for the pattern name (`PATTERN`), extracted field (`field`), and destination type (`type`).
  - *String Interpolation & Regex*: Colors `%{variable}` references inside string values, regex named captures `(?P<var>...)`, and Google SecOps double-backslash regex escape rules (`\\s`, `\\d`, `\\|`).
  - *Field References & Error Flags*: Distinctly formats bracketed field access (`[http_status]`, `[cat]`), chained lookups (`[resource][labels]`), and error flags (`[_grok_parsing_failed]`).
  - *UDM & System Targets*: Special semantic highlighting for Chronicle UDM paths (`event.idm.read_only_udm.*`, `entity.*`, `metadata`, `principal`, `target`, `network`, `security_result`), output targets (`@output => "event"`), and timestamp fields (`@timestamp`, `@createTimestamp`, `@collectionTimestamp`).
  - *Embedded JavaScript*: Embeds full JavaScript syntax highlighting inside `code { javascript => `...` }` parser extension blocks.
  - *Data Types & Constants*: Recognizes supported `convert` types (`boolean`, `uinteger`, `integer`, `ipaddress`, `macaddress`, `hash`, etc.), predefined date formats (`ISO8601`, `RFC3339`, `UNIX`, `UNIX_MS`), and drop tags (`TAG_MALFORMED_MESSAGE`, `TAG_UNSUPPORTED`).

- **Language Configuration**:
  - Comment toggle using `#` (`lineComment: "#"`).
  - Bracket pair colorization and auto-closing for `{}`, `[]`, `()`, `""`, `''`, and `` ``.
  - Auto-closing for Grok pattern interpolations: typing `%{` automatically inserts `}`.
  - Smart indentation rules for filter blocks and conditionals (`if`, `else if`, `else`, `for`).

## File Associations

By default, this extension associates with:
- Files ending in `.grok`
- Any file where the first line begins with `filter {` (`firstLine` auto-detection)

If your files use another extension and contain leading copyright header comments, you can map them in your VS Code `settings.json`:

```json
{
  "files.associations": {
    "*.config": "secopsgrok",
    "**/parsers/**/*.config": "secopsgrok"
  }
}
```

## References

- [Google Cloud Security Operations Parser Syntax Reference](https://docs.cloud.google.com/chronicle/docs/reference/parser-syntax)
- [Google Cloud Unified Data Model (UDM) Field Reference](https://cloud.google.com/chronicle/docs/unified-data-model/udm-fields)

# Change Log

Changes to the "secops-grok-language" extension.

## [0.0.1] - 2026-09-22

### Added
- Language support for Google SecOps Logstash Grok parser syntax.
- TextMate grammar for filter blocks, mutate directives, grok patterns, conditionals, and UDM mappings.
- Grok pattern breakdown (`%{PATTERN:field:type}`) and variable interpolation highlighting.
- Embedded JavaScript syntax highlighting for `code { javascript => `...` }` blocks.
- Language configuration with comment toggle (`#`), auto-closing pairs (including `%{` -> `}`), and smart indentation.
- File associations for `.grok` and `firstLine` detection for `filter {`.
- Document Formatting provider (`Format Document` / `editor.action.formatDocument`).
- Syntax-aware indentation with support for custom editor tab settings.
- Combined `} else {` and `} else if [...] {` placement normalization.
- Single-space normalization around `=>`, comparison operators, and commas.
- Opening brace spacing consistency and empty block preservation (`statedump {}`).
- Verbatim preservation for embedded JavaScript in `code { javascript => `...` }` blocks.
- Automatic collapsing of consecutive blank lines.

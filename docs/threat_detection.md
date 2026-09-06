# Threat Detection System

HackT utilizes a real-time, AST-based (Abstract Syntax Tree) static analysis engine to perform code-level security auditing while you type.

## How It Works

The core of the threat scanner relies on `tree-sitter`, a parser generator tool and an incremental parsing library. By traversing the syntax tree of your codebase, HackT avoids the pitfalls of simple regex matching and can understand the structural context of the code.

### 1. File Watching
The `services/code_watcher.py` module uses the `watchdog` library to monitor active development directories.
- A 1.5s debounce ensures that rapidly saving files does not trigger an avalanche of parse requests.
- Only modified files within the currently active workspace are evaluated to preserve CPU cycles.

### 2. AST Parsing
When a file change is detected, it is passed to `services/threat_scanner.py`.
- The corresponding `tree-sitter` language parser is dynamically loaded based on the file extension.
- The AST is generated in memory.

### 3. Pattern Matching
The scanner checks the AST against a localized rule engine to detect insecure coding patterns, such as:
- **SQL Injection**: Concatenating variables directly into SQL string queries.
- **Hardcoded Secrets**: Detection of high-entropy strings or known token patterns assigned to variables.
- **Unsafe Evaluation**: Usage of `eval()` or `exec()` with non-literal arguments.
- **Path Traversal**: Unsanitized user input fed into filesystem APIs.

### 4. Diff Broadcasting
Once a threat is identified:
1. An issue severity level is assigned.
2. The LLM Engine (Qwen) may be briefly invoked to generate a fix if the threat pattern matches a known remediation strategy.
3. The threat data, along with a suggested code diff, is broadcast via WebSocket to the frontend.
4. The React UI renders a Diff Modal, allowing the user to review the fix and apply it with a single click.

## Supported Languages

The threat scanner currently includes native Tree-sitter parsers for:
- Python (`.py`)
- JavaScript (`.js`, `.jsx`)
- TypeScript (`.ts`, `.tsx`)
- Rust (`.rs`)
- Go (`.go`)
- C++ (`.cpp`, `.cc`, `.hpp`)

> [!TIP]
> The Threat Scanner runs strictly on-device. Your uncommitted code is never sent to the cloud for analysis.

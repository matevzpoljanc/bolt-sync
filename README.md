# bolt-sync

A command-line utility to synchronize files between a local directory and a remote Bolt.new project.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

## Overview

bolt-sync provides a simple way to manage your Bolt.new projects directly from your local environment. It enables bidirectional synchronization, allowing you to push local changes to your Bolt.new project and pull remote changes to your local directory.

## Installation

1. Clone this repository or download the script:

```bash
git clone https://github.com/yourusername/bolt-sync.git
cd bolt-sync
```

2. Install required dependencies:

```bash
pip install requests
```

3. Make the script executable:

```bash
chmod +x bolt-sync.py
```

4. (Optional) Create a symbolic link to make it available system-wide:

```bash
sudo ln -s "$(pwd)/bolt-sync.py" /usr/local/bin/bolt-sync
```

## Features

- **Push:** Upload local changes to your Bolt.new project
- **Pull:** Download remote changes to your local directory (includes new files by default)
- **Compare:** View detailed diffs between local and remote files
- **Configuration:** Customize excluded directories and files
- **Safety:** Automatic backups of remote files before pushing changes
- **Flexibility:** Dry-run mode to preview changes without making them

## Getting Your Bolt.new API Key

To use bolt-sync, you'll need your Bolt.new API key. Here's how to find it:

1. Open your Bolt.new project in a web browser
2. Open your browser's developer tools (F12 or right-click → Inspect)
3. Go to the Network tab
4. Refresh the page to capture network requests
5. Filter requests by typing "api" in the filter box
6. Look for any request to "https://stackblitz.com/api/"
7. Click on one of these requests
8. In the request headers, find the "Authorization" header
9. Your API key is the value after "Bearer " in this header

Once you have your API key, set it as an environment variable:

```bash
export BOLT_API_KEY="your-api-key-here"
```

For persistent configuration, add this to your `.bashrc` or `.zshrc` file.

Alternatively, you can pass it directly with the `--api-key` parameter when running commands.

## Basic Usage

### Pull Changes from Remote

Pull changes (including new files) from a remote project to your local directory:

```bash
bolt-sync pull <project-id> <local-directory>
```

Pull only changes to existing files (skipping new files):

```bash
bolt-sync pull <project-id> <local-directory> --existing-only
```

### Push Changes to Remote

Push local changes to a remote project:

```bash
bolt-sync push <project-id> <local-directory>
```

### Create a Configuration File

Generate a default configuration file:

```bash
bolt-sync create-config --output .bolt-sync.json
```

## Advanced Usage

### Dry Run Mode

Preview changes without actually making them:

```bash
bolt-sync pull <project-id> <local-directory> --dry-run
bolt-sync push <project-id> <local-directory> --dry-run
```

### Automatic Confirmation

Skip confirmation prompts (use with caution):

```bash
bolt-sync pull <project-id> <local-directory> -y
bolt-sync push <project-id> <local-directory> -y
```

### Hide Diffs

Only show file names without detailed diffs:

```bash
bolt-sync pull <project-id> <local-directory> --no-diff
```

### Using a Custom Configuration File

```bash
bolt-sync pull <project-id> <local-directory> --config my-config.json
```

## Configuration

The configuration file is a JSON file with the following structure:

```json
{
  "exclude_dirs": [
    "venv",
    "__pycache__",
    "node_modules",
    ".next",
    ".idea"
  ],
  "ignore_files": [
    "package.json",
    "next.config.js"
  ],
  "skip_when_pushing": [
    "next-env.d.ts",
    "yarn.lock",
    ".dockerignore",
    "package.json",
    "next.config.js"
  ],
  "skip_when_pulling": [
    ".env",
    "package-lock.json",
    "package.json",
    "next.config.js"
  ]
}
```

## Limitations

### Text Files Only

bolt-sync currently only supports synchronization of text-based source files. Binary files (images, compiled assets, etc.) are not supported at the moment. The tool automatically skips files that cannot be read as text.

When syncing with a Bolt.new project, the tool only processes files that:
- Are marked as files (not directories) in the project
- Are not marked as binary in the project metadata
- Can be decoded as UTF-8 text

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
#!/usr/bin/env python3
"""
Bolt.new Project Synchronization Tool

A command line utility to synchronize files between a local directory and 
a remote Bolt.new project. Supports pull and push operations.
"""

import argparse
import difflib
import json
import os
import sys
import time
from pathlib import Path

import requests

# Default lists of directories and files to exclude
DEFAULT_EXCLUDE_DIRS = ["venv", "__pycache__", "node_modules", ".next", ".idea"]
DEFAULT_IGNORE_FILES = ["package.json", "next.config.js"]
DEFAULT_SKIP_WHEN_PUSHING = ["next-env.d.ts", "yarn.lock", ".dockerignore"]
DEFAULT_SKIP_WHEN_PULLING = [".env", "package-lock.json"]

def getattr_recursive(obj, attr_path):
    """Recursively get attributes from an object using dot notation."""
    attrs = attr_path.split('.')
    current = obj
    for attr in attrs:
        current = current.get(attr, {})
    return current

def fetch_api_endpoint(endpoint: str, method: str = "get", api_key=None, **kwargs):
    """
    Fetch API endpoint with proper authentication
    """
    if not api_key:
        api_key = os.environ.get("BOLT_API_KEY")
        if not api_key:
            raise ValueError("BOLT_API_KEY environment variable not set")
            
    headers = kwargs.pop("headers", {}) or {}
    headers["Authorization"] = f"Bearer {api_key}"
    
    response = requests.request(
        method=method,
        url=f"https://stackblitz.com{endpoint}",
        headers=headers,
        **kwargs,
    )
    
    if not response.ok:
        raise ValueError(f"API request failed: {response.status_code} - {response.text}")

    return response.json()

def get_remote_files(project_id: str, api_key=None) -> dict:
    """
    Get remote Bolt.new files
    """
    response = fetch_api_endpoint(f"/api/projects/{project_id}", api_key=api_key)
    return getattr_recursive(response, "project.appFiles")

def process_file_changes(file_changes: dict[str, str], action_type: str, dry_run=False):
    """
    Common function to process file changes for both push and pull operations
    """
    if not file_changes:
        print(f"No changes to {action_type}.")
        return False

    if dry_run:
        print(f"\nDRY RUN: Would {action_type} the following changes:")
        for path in sorted(file_changes.keys()):
            print(f"  - {path}")
        return False
        
    return True

def modify_remote_files(project_id: str, file_changes: dict[str, str], api_key=None, dry_run=False):
    """
    Modify remote files, with confirmation for each file
    """
    if not process_file_changes(file_changes, "push", dry_run):
        return
        
    current_remote_files = get_remote_files(project_id, api_key=api_key)
    current_ts = int(time.time())
    
    # Optional: Save a backup of current remote files
    backup_dir = Path(os.path.expanduser("~/.bolt-sync/backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file = backup_dir / f"remote_files_{project_id}_{current_ts}.json"
    with open(backup_file, "w") as outfile:
        json.dump(current_remote_files, outfile)
        print(f"Backup of remote files saved to {backup_file}")

    # Update file contents
    for path, new_content in file_changes.items():
        remote_file = current_remote_files.get(path)
        if not remote_file:
            print(f"File {path} not found in remote project - adding is currently not supported")
            continue

        remote_file["contents"] = new_content
        remote_file["lastModified"] = current_ts

    # Push changes to remote
    fetch_api_endpoint(
        f"/api/projects/{project_id}",
        method="patch",
        api_key=api_key,
        json={"project": {"appFiles": current_remote_files}},
    )
    print("Successfully pushed changes to remote project.")

def get_local_files(local_dir: str, exclude_dirs: list = None) -> dict:
    """
    Recursively read all text files in the given local directory using pathlib.
    Optionally excludes files located in directories whose names are in exclude_dirs.
    Returns a dict mapping relative file paths to file contents.
    """
    exclude_dirs = exclude_dirs or []
    local_files = {}
    base_path = Path(local_dir)
    
    if not base_path.exists():
        raise ValueError(f"Local directory '{local_dir}' does not exist")
        
    for file_path in base_path.rglob("*"):
        if file_path.is_file():
            # Check if any directory in the file's relative path is in the exclude list
            if any(
                excluded in file_path.relative_to(base_path).parts
                for excluded in exclude_dirs
            ):
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                rel_path = str(file_path.relative_to(base_path))
                local_files[rel_path] = content
            except UnicodeDecodeError:
                # Skip files that cannot be read as text (likely binary files)
                continue
    return local_files

def show_diff(remote_content, local_content, file_path):
    """Show unified diff between remote and local content."""
    diff = difflib.unified_diff(
        remote_content.splitlines(),
        local_content.splitlines(),
        fromfile=f"remote/{file_path}",
        tofile=f"local/{file_path}",
        lineterm="",
    )
    return "\n".join(diff)

def print_file_list(title, files):
    """
    Helper function to print a list of files with a title
    """
    if not files:
        return
        
    print(f"\n{title}:")
    for file in sorted(files):
        print(f"  - {file}")

def compare_files(remote_files: dict, local_files: dict, show_diffs=True):
    """
    Compare the remote and local files.
    Prints differences for files that exist in both, and lists files missing in either side.
    """
    remote_set = set(remote_files.keys())
    local_set = set(local_files.keys())

    common_files = remote_set & local_set
    remote_only = remote_set - local_set
    local_only = local_set - remote_set
    
    diff_count = 0
    modified_files = []

    print_file_list("Remote files not found locally", remote_only)
    print_file_list("Local files not present remotely", local_only)

    if common_files:
        for file in sorted(common_files):
            remote_content = remote_files[file]
            local_content = local_files[file]
            if remote_content != local_content:
                diff_count += 1
                modified_files.append(file)
                if show_diffs:
                    print(f"\nFile '{file}' differs between remote and local:")
                    print(show_diff(remote_content, local_content, file))
    
    if diff_count == 0 and not remote_only and not local_only:
        print("All files are in sync. No differences found.")
    elif diff_count > 0 and not show_diffs:
        print_file_list(f"{diff_count} modified files", modified_files)
    
    return {
        "common": common_files,
        "remote_only": remote_only,
        "local_only": local_only,
        "modified": modified_files
    }

def generate_diff_files(
    source_files: dict, target_files: dict, source_name: str
) -> dict[str, str]:
    """
    Generic function to generate diff between two file collections
    
    Args:
        source_files: The source files with content to use
        target_files: The target files to compare against
        source_name: Name of source ("local" or "remote")
        
    Returns:
        Dict of modified files where content from source_files differs from target_files
    """
    modified_files = {}
    for path, source_content in source_files.items():
        if path not in target_files:
            continue

        target_content = target_files[path]
        if source_content != target_content:
            modified_files[path] = source_content

    return modified_files

def generate_diff_for_locally_modified_files(
    remote_files: dict, local_files: dict
) -> dict[str, str]:
    """
    Get dict of modified files (local changes to push)
    """
    return generate_diff_files(local_files, remote_files, "local")

def generate_diff_for_remote_modified_files(
    remote_files: dict, local_files: dict
) -> dict[str, str]:
    """
    Get dict of modified files from remote (to pull)
    """
    return generate_diff_files(remote_files, local_files, "remote")

def remove_files(all_files: dict[str, str], remove_files: list[str]) -> dict[str, str]:
    """
    Remove specified files from a dict of files
    """
    return {
        path: content for path, content in all_files.items() if path not in remove_files
    }

def modify_or_add_local_files(local_dir: str, file_changes: dict[str, str], dry_run=False):
    """
    Modify or add local files
    """
    if not process_file_changes(file_changes, "pull", dry_run):
        return
        
    base_dir = Path(local_dir)
    for path, contents in file_changes.items():
        file_path = base_dir / path
        
        # Create parent directories if they don't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file content
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(contents)
            
    print(f"Successfully pulled {len(file_changes)} file(s) to {local_dir}")

def confirm_action(files, action_type):
    """
    Ask user for confirmation before performing file operations
    """
    if not files:
        return False
        
    files_list = "\n  - ".join([""] + sorted(files.keys()))
    answer = input(f"Do you want to {action_type} these files?{files_list}\n(y/N): ")
    return answer.lower() in ('y', 'yes')

def load_config(config_file=None):
    """
    Load configuration from file or return defaults
    """
    default_config = {
        "exclude_dirs": DEFAULT_EXCLUDE_DIRS,
        "ignore_files": DEFAULT_IGNORE_FILES,
        "skip_when_pushing": DEFAULT_SKIP_WHEN_PUSHING + DEFAULT_IGNORE_FILES,
        "skip_when_pulling": DEFAULT_SKIP_WHEN_PULLING + DEFAULT_IGNORE_FILES,
    }
    
    if not config_file:
        return default_config
        
    config_path = Path(config_file)
    if not config_path.exists():
        return default_config
        
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        # Merge with defaults for any missing keys
        for key in default_config:
            if key not in config:
                config[key] = default_config[key]
                
        return config
    except Exception as e:
        print(f"Error loading config: {e}")
        return default_config

def get_source_files(args, config):
    """
    Common function to retrieve and process both remote and local files
    """
    # Get remote files
    app_files = get_remote_files(args.project_id, api_key=args.api_key)
    remote_source_files = {
        path: details["contents"]
        for path, details in app_files.items()
        if details.get("type") == "file" and not details.get("isBinary")
    }
    remote_source_files = remove_files(remote_source_files, config["skip_when_pulling"])
    
    # Get local files
    local_source_files = get_local_files(args.local_dir, exclude_dirs=config["exclude_dirs"])
    local_source_files = remove_files(local_source_files, config["skip_when_pushing"])
    
    return remote_source_files, local_source_files

def push_command(args):
    """
    Push local changes to remote
    """
    config = load_config(args.config)
    
    try:
        # Get source files
        remote_source_files, local_source_files = get_source_files(args, config)
        
        # Compare files
        print(f"Comparing local files with remote project '{args.project_id}'...\n")
        compare_files(remote_source_files, local_source_files, show_diffs=not args.no_diff)
        
        # Generate changes to push
        modified_files = generate_diff_for_locally_modified_files(
            remote_files=remote_source_files, local_files=local_source_files
        )
        
        # Push changes if confirmed
        if modified_files:
            if args.yes or confirm_action(modified_files, "push"):
                modify_remote_files(args.project_id, modified_files, api_key=args.api_key, dry_run=args.dry_run)
            else:
                print("Push cancelled.")
        else:
            print("No files to push.")
            
    except Exception as e:
        print(f"Error during push operation: {e}")
        return 1
    
    return 0

def pull_command(args):
    """
    Pull remote changes to local
    """
    config = load_config(args.config)
    
    try:
        # Get source files
        remote_source_files, local_source_files = get_source_files(args, config)
        
        # Compare files
        print(f"Comparing remote project '{args.project_id}' with local files...\n")
        file_comparison = compare_files(remote_source_files, local_source_files, show_diffs=not args.no_diff)
        
        # Generate changes to pull
        modified_files = generate_diff_for_remote_modified_files(
            remote_files=remote_source_files, local_files=local_source_files
        )
        
        # Add remote-only files by default, unless --existing-only is specified
        if not args.existing_only:
            for file in file_comparison["remote_only"]:
                modified_files[file] = remote_source_files[file]
        
        # Pull changes if confirmed
        if modified_files:
            if args.yes or confirm_action(modified_files, "pull"):
                modify_or_add_local_files(args.local_dir, modified_files, dry_run=args.dry_run)
            else:
                print("Pull cancelled.")
        else:
            print("No files to pull.")
            
    except Exception as e:
        print(f"Error during pull operation: {e}")
        return 1
    
    return 0

def create_config_command(args):
    """
    Create a config file with default settings
    """
    config_path = Path(args.output)
    if config_path.exists() and not args.force:
        print(f"Config file {args.output} already exists. Use --force to overwrite.")
        return 1
        
    config = {
        "exclude_dirs": DEFAULT_EXCLUDE_DIRS,
        "ignore_files": DEFAULT_IGNORE_FILES,
        "skip_when_pushing": DEFAULT_SKIP_WHEN_PUSHING + DEFAULT_IGNORE_FILES,
        "skip_when_pulling": DEFAULT_SKIP_WHEN_PULLING + DEFAULT_IGNORE_FILES,
    }
    
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Config file created at {args.output}")
    except Exception as e:
        print(f"Error creating config file: {e}")
        return 1
        
    return 0

def main():
    """
    Main function to handle command line arguments and execute commands
    """
    parser = argparse.ArgumentParser(
        description="Bolt.new Project Synchronization Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Pull changes from remote project
  bolt-sync pull sb1-fkmjfnvs ./my-project
  
  # Push local changes to remote project
  bolt-sync push sb1-fkmjfnvs ./my-project
  
  # Pull including new files
  bolt-sync pull sb1-fkmjfnvs ./my-project --include-new
  
  # Dry run (don't actually make changes)
  bolt-sync push sb1-fkmjfnvs ./my-project --dry-run
  
  # Create a config file
  bolt-sync create-config --output .bolt-sync.json
        """
    )
    parser.add_argument('--api-key', help='Bolt.new API key (defaults to BOLT_API_KEY env var)')
    parser.add_argument('--config', help='Path to configuration file')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Pull command
    pull_parser = subparsers.add_parser('pull', help='Pull remote changes to local')
    pull_parser.add_argument('project_id', help='Bolt.new project ID')
    pull_parser.add_argument('local_dir', help='Local directory path')
    pull_parser.add_argument('--existing-only', action='store_true', help='Only pull changes to existing files (skip new files)')
    pull_parser.add_argument('--no-diff', action='store_true', help='Don\'t show diffs, just list modified files')
    pull_parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    pull_parser.add_argument('-y', '--yes', action='store_true', help='Automatically confirm all operations')
    
    # Push command
    push_parser = subparsers.add_parser('push', help='Push local changes to remote')
    push_parser.add_argument('project_id', help='Bolt.new project ID')
    push_parser.add_argument('local_dir', help='Local directory path')
    push_parser.add_argument('--no-diff', action='store_true', help='Don\'t show diffs, just list modified files')
    push_parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    push_parser.add_argument('-y', '--yes', action='store_true', help='Automatically confirm all operations')
    
    # Create config command
    config_parser = subparsers.add_parser('create-config', help='Create a configuration file')
    config_parser.add_argument('--output', default='.bolt-sync.json', help='Output file path')
    config_parser.add_argument('-f', '--force', action='store_true', help='Overwrite existing file')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
        
    if args.command == 'pull':
        return pull_command(args)
    elif args.command == 'push':
        return push_command(args)
    elif args.command == 'create-config':
        return create_config_command(args)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
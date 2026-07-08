#!/usr/bin/env python3
"""
Process new transactions: one command for the full pipeline.

Step 1 – Import: Reads CSVs from data/<Account>/csv/, merges into storage/transactions/<Account>.json
  (existing transactions preserved; new ones get category from same merchant or LLM).
Step 2 – Categorize: Runs entity-based categorization on all transactions in storage (identify_and_categorize),
  so every transaction has identified_business + category by entity type (Business/Personal).

This is the single entry point for "new CSVs → storage → categorized." Other scripts (categorize_transactions.py,
identify_and_categorize.py) are used by this script; you can run them separately if needed.

Usage:
  python3 process_new_transactions.py              # import + categorize (writes changes)
  python3 process_new_transactions.py --dry-run    # import only; show what would be categorized (no writes)
  python3 process_new_transactions.py -v           # verbose
"""

import argparse
from datetime import datetime
import os
import subprocess
import sys
from pathlib import Path


def run_step(cmd: list[str], cwd: Path, log_file) -> int:
    """Run one step, stream output to console, and append to log file."""
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end='')
        log_file.write(line)
    process.wait()
    return process.returncode


def main():
    parser = argparse.ArgumentParser(
        description='Import CSVs into storage, then categorize all transactions by entity type (one command).'
    )
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Import CSVs only; run categorization in dry-run (no category writes).',
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    logs_dir = project_root / 'storage' / 'processing_logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = logs_dir / f'process_new_transactions_{timestamp}.log'

    with open(log_path, 'w', encoding='utf-8') as log_file:
        log_file.write(f"Started: {datetime.now().isoformat()}\n")
        log_file.write(f"Command: {' '.join(sys.argv)}\n")
        log_file.write(f"Working directory: {project_root}\n")
        log_file.write("=" * 60 + "\n")

        # Step 1: Import CSVs into storage
        print('Step 1: Importing CSVs into storage...')
        print('=' * 60)
        log_file.write('Step 1: Importing CSVs into storage...\n')
        log_file.write('=' * 60 + '\n')
        cmd_import = [sys.executable, str(project_root / 'categorize_transactions.py')]
        if args.verbose:
            cmd_import.append('-v')
        rc = run_step(cmd_import, project_root, log_file)
        if rc != 0:
            log_file.write(f"\nStep 1 failed with exit code {rc}\n")
            print(f"\nLog saved to: {log_path}")
            sys.exit(rc)
        print()
        log_file.write("\n")

        # Step 2: Entity-based identify & categorize
        print('Step 2: Identifying and categorizing by entity type...')
        print('=' * 60)
        log_file.write('Step 2: Identifying and categorizing by entity type...\n')
        log_file.write('=' * 60 + '\n')
        cmd_categorize = [sys.executable, str(project_root / 'identify_and_categorize.py')]
        if args.dry_run:
            cmd_categorize.append('--dry-run')  # identify_and_categorize default is dry-run; explicit for clarity
        else:
            cmd_categorize.append('--no-dry-run')
        if args.verbose:
            cmd_categorize.append('-v')
        rc = run_step(cmd_categorize, project_root, log_file)
        if rc != 0:
            log_file.write(f"\nStep 2 failed with exit code {rc}\n")
            print(f"\nLog saved to: {log_path}")
            sys.exit(rc)
        print()

        log_file.write("\nDone.\n")
        log_file.write(f"Ended: {datetime.now().isoformat()}\n")

    print('Done.')
    print(f'Log saved to: {log_path}')


if __name__ == '__main__':
    main()

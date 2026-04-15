#!/usr/bin/env node

/**
 * Auto-memory hook for Claude Code sessions.
 * Handles memory import (SessionStart) and sync (Stop) events.
 */

const command = process.argv[2] || 'sync';

switch (command) {
  case 'import':
    // Session start: no-op, memory is loaded via MEMORY.md automatically
    process.exit(0);
    break;

  case 'sync':
    // Stop hook: no-op, memory persists via file system
    process.exit(0);
    break;

  default:
    process.exit(0);
}

#!/usr/bin/env node

/**
 * Hook handler for Claude Code lifecycle events.
 * Processes pre/post tool use, session, and routing hooks.
 */

'use strict';

const command = process.argv[2] || '';

// Read stdin (hook context) but don't block if empty
let input = '';
if (!process.stdin.isTTY) {
  try {
    const chunks = [];
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => chunks.push(chunk));
    process.stdin.on('end', () => {
      input = chunks.join('');
      handleCommand(command, input);
    });
    // Timeout to avoid hanging
    setTimeout(() => {
      if (!input) handleCommand(command, '');
    }, 2000);
  } catch {
    handleCommand(command, '');
  }
} else {
  handleCommand(command, '');
}

function handleCommand(cmd, context) {
  switch (cmd) {
    case 'pre-bash':
    case 'post-bash':
    case 'pre-edit':
    case 'post-edit':
    case 'route':
    case 'session-restore':
    case 'session-end':
    case 'compact-manual':
    case 'compact-auto':
    case 'status':
    case 'post-task':
    case 'notify':
      // All hooks succeed silently
      process.exit(0);
      break;

    default:
      // Unknown command - exit cleanly
      process.exit(0);
  }
}

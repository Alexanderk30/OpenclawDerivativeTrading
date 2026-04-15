#!/usr/bin/env node

/**
 * Status line provider for Claude Code.
 */

'use strict';

// Output empty status line JSON
process.stdout.write(JSON.stringify({ text: '' }));
process.exit(0);

#!/usr/bin/env node
'use strict';
const cp = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const root = path.resolve(__dirname, '..');
const candidates = process.env.SKILL_ASSESSMENT_PYTHON
  ? [[process.env.SKILL_ASSESSMENT_PYTHON]]
  : (process.platform === 'win32' ? [['py', '-3'], ['python'], ['python3']] : [['python3'], ['python']]);
let selected;
for (const candidate of candidates) {
  const check = cp.spawnSync(candidate[0], candidate.slice(1).concat([
    '-I', '-c', 'import sys;sys.exit(0 if sys.version_info >= (3,11) else 1)'
  ]), {encoding: 'utf8', windowsHide: true});
  if (!check.error && check.status === 0) { selected = candidate; break; }
}
if (!selected) {
  process.stderr.write('Python 3.11+ is required. Install Python or set SKILL_ASSESSMENT_PYTHON to its executable.\n');
  process.exit(2);
}
const cancellationDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'skill-assessment-cancel-'));
const cancellationFile = path.join(cancellationDirectory, 'cancel');
const child = cp.spawn(selected[0], selected.slice(1).concat([
  '-I', path.join(root, 'python', 'bootstrap.py'), ...process.argv.slice(2)
]), {stdio: 'inherit', windowsHide: true, detached: process.platform !== 'win32',
  env: {...process.env, SKILL_ASSESSMENT_CANCEL_FILE: cancellationFile}});
let interrupted = false;
let fallback;
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    if (interrupted) return;
    interrupted = true;
    fs.writeFileSync(cancellationFile, signal);
    // Give Python time to close its jobs and save cancellation evidence.
    fallback = setTimeout(() => {
      if (!child.pid) return;
      try {
        if (process.platform === 'win32') {
          cp.spawnSync('taskkill.exe', ['/pid', String(child.pid), '/T', '/F'], {stdio: 'ignore', windowsHide: true});
        } else { process.kill(-child.pid, 'SIGKILL'); }
      } catch (_) { /* Child may already have exited. */ }
    }, 10000);
    fallback.unref();
  });
}
function cleanup() {
  if (fallback) clearTimeout(fallback);
  fs.rmSync(cancellationDirectory, {recursive: true, force: true});
}
child.on('error', error => { cleanup(); process.stderr.write(error.message + '\n'); process.exitCode = 2; });
child.on('exit', code => { cleanup(); process.exitCode = interrupted ? 130 : (code === null ? 2 : code); });

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const root = __dirname;
const backend = path.join(root, 'backend');
const cli = path.join(root, 'node_modules', 'tailwindcss', 'lib', 'cli.js');

const groups = [
  'auth',
  'delivery-login',
  'dashboard',
  'kiosk-auth',
  'menu-form',
  'kiosk-home',
  'base',
  'rider',
  'default',
];

if (!fs.existsSync(path.join(root, 'node_modules', 'tailwindcss'))) {
  console.error('tailwindcss not installed. Run: npm install');
  process.exit(1);
}

function quote(p) {
  return '"' + p + '"';
}

for (const group of groups) {
  const outDir = path.join(backend, 'static', 'css');
  fs.mkdirSync(outDir, { recursive: true });
  const out = path.join(outDir, group + '.css');
  execSync(
    'node ' + quote(cli) +
    ' -c ' + quote(path.join(backend, 'tailwindcss', group + '.config.js')) +
    ' -i ' + quote(path.join(backend, 'tailwindcss', 'input.css')) +
    ' -o ' + quote(out) + ' --minify',
    { cwd: backend, stdio: 'inherit' }
  );
  console.log('built', group + '.css');
}
console.log('CSS build complete');
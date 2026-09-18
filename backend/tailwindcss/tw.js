const path = require('path');

const backend = path.join(
  __dirname,
  '..'
).split(path.sep).join('/');

function glob(...parts) {
  return path.join(backend, ...parts).split(path.sep).join('/');
}

module.exports = { backend, glob };
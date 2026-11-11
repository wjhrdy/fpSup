// Use the pinned upstream Merge page's own upload validation and card composer.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const [upstream, modules, output] = process.argv.slice(2);
const merge = path.resolve(upstream, 'fpSup/tools/merge-v4');
const page = fs.readFileSync(path.join(merge, 'index.html'), 'utf8');
const script = id => page.match(new RegExp('<script id="' + id + '"[^>]*>([\\s\\S]*?)</script>'))[1];
const ctx = vm.createContext({
  atob: s => Buffer.from(s, 'base64').toString('binary'),
  btoa: s => Buffer.from(s, 'binary').toString('base64'),
  TextEncoder,
  document: {getElementById: () => ({textContent: script('cat')})},
});
vm.runInContext(script('compose') + '\nglobalThis.merge = {CAT, BOOT, addUpload, compose, checks};', ctx);
const api = ctx.merge;
require(path.join(merge, 'test_fill.js'))(api.CAT);
const names = ['Indoor_v0.4.5.BIN', 'LV-Boost_v0.6.1.BIN'];
const ids = names.map(name => {
  const r = api.addUpload(name, new Uint8Array(fs.readFileSync(path.join(modules, name))));
  assert.ok(r.id, JSON.stringify(r));
  return r.id;
});
const shell = api.CAT.products.find(p => p.sup_id === 'SHEL');
assert.ok(shell);
fs.mkdirSync(output);
for (const [dir, instant, fast, peer] of [
  ['ordinary', false, false, false], ['fast', true, true, false],
  ['ordinary-with-shell', false, false, true], ['fast-with-shell', true, true, true],
]) {
  Object.assign(api.BOOT, {instant, fast});
  const picked = peer ? [...ids, shell.id] : ids;
  const bad = api.checks(picked).filter(r => !r.ok);
  assert.equal(bad.length, 0, JSON.stringify(bad));
  const result = api.compose(picked);
  assert.equal(result.on.length, picked.length);
  for (const name of names) {
    const file = result.files.find(f => f.name === 'fpSup/' + name && !f.off);
    assert.ok(file);
    assert.deepEqual(Buffer.from(file.data), fs.readFileSync(path.join(modules, name)));
  }
  for (const file of result.files) {
    const dest = path.join(output, dir, file.name);
    fs.mkdirSync(path.dirname(dest), {recursive: true});
    fs.writeFileSync(dest, Buffer.from(file.data));
  }
  console.log(`PASS Merge v4 uploads and composition: ${dir}`);
}

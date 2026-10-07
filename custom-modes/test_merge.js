#!/usr/bin/env node
// Run the actual Merge upload parser/composer; optionally save cards for emulation.
// node custom-modes/test_merge.js ordinary/fpSup.BIN [fresh-output-dir] [Merge-index.html]
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const page = process.argv[4] || path.join(__dirname, '../tools/card-composer/index.html');
const html = fs.readFileSync(page, 'utf8');
const block = id => html.match(new RegExp('<script id="' + id + '"[^>]*>([\\s\\S]*?)<\\/script>'))[1];
const CAT = JSON.parse(block('cat'));
const ctx = vm.createContext({CAT,
  atob: s => Buffer.from(s, 'base64').toString('binary'),
  btoa: s => Buffer.from(s, 'binary').toString('base64')});
vm.runInContext(block('compose') + html.slice(html.indexOf('function parseVshl('), html.indexOf('function addFiles(')) + `
  globalThis.api = {parseVshl, run(card, ids, fast, push) {
    uploads.length = 0;
    uploads.push({id:'indoor', name:'Indoor', upload:true, entry:card.entry, records:card.recs});
    on.clear(); ids.concat('indoor').forEach(id => on.add(id));
    fastOn = fast; pushOn = push;
    const c = composed(), bin = composeVshl(c.recs, c.entry);
    const bad = runChecks(c.recs, bin, '', c.entry, c.entries).filter(x => !x.ok);
    return {c, bin, bad, auto:composeAutorun('')};
  }};`, ctx);
const bytes = fs.readFileSync(process.argv[2]);
const card = ctx.api.parseVshl(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
assert(card.entry > 0 && card.entry < 0x40000000);
const launchers = card.recs.filter(r => r.a === 0);
assert.equal(launchers.length, 2, 'merge input must contain only stage2 + Indoor, no bundled Shell/entry chain');
assert(!card.recs.some(r => r.a === CAT.fast.abort.a), 'Fast belongs to final packaging');
let off = 16 + 8 * card.recs.length;
let sourceOffset;
for (const r of card.recs) {
  if (r === launchers[1]) sourceOffset = off;
  off += (Buffer.from(r.b, 'base64').length + 3) & ~3;
}
assert.equal(card.entry, sourceOffset, 'entry must point directly to the position-independent launcher');
const autos = new Map(), report = [];
let rejected = 0;
if (process.argv[3]) fs.mkdirSync(process.argv[3]); // refuse to overwrite previous evidence
for (let mask = 0; mask < 2 ** CAT.cards.length; mask++) {
  const cards = CAT.cards.filter((_, i) => mask & (1 << i));
  const ids = cards.map(c => c.id);
  if (cards.some(c => (c.excl || []).some(id => ids.includes(id)))) continue;
  for (const fast of [false, true]) for (const push of ids.includes('shell') ? [false, true] : [false]) {
    const label = ['indoor', ...ids, fast ? 'fast' : 'ordinary', ...(push ? ['ep83'] : [])].join('-');
    const {c, bin, bad, auto} = ctx.api.run(card, ids, fast, push);
    if (bin.used > CAT.cap_patch.max) {
      assert(bad.some(x => x.t === 'The loader can read the whole card'), label);
      assert(bad.every(x => ['The loader can read the whole card',
        'Data past the loader read keeps its place'].includes(x.t)), JSON.stringify(bad));
      rejected++;
      continue; // expected rejection of combinations beyond the loader ceiling
    }
    assert.equal(bad.length, 0, label + ': ' + JSON.stringify(bad));
    // Independently locate unchanged launcher bytes in the emitted container.
    const output = Buffer.from(bin.bytes), count = output.readUInt32LE(4);
    let offset = 16 + 8 * count, entry;
    for (let i = 0; i < count; i++) {
      const n = output.readUInt32LE(20 + 8 * i);
      if (output.subarray(offset, offset + n).equals(Buffer.from(launchers[1].b, 'base64'))) entry = offset;
      offset += (n + 3) & ~3;
    }
    assert(entry, label + ': lost Indoor launcher');
    assert.equal(c.entries.at(-1), entry, label + ': Indoor entry relocation');
    if (ids.length) {
      const table = output.readUInt32LE(8) + CAT.trampoline.tbl;
      assert.equal(output.readUInt32LE(table), table);
      assert.equal(output.readUInt32LE(table + 4 * c.entries.length), entry);
      assert.equal(output.readUInt32LE(table + 4 * (c.entries.length + 1)), 0);
    } else assert.equal(output.readUInt32LE(8), entry);
    // Upstream may raise the loader read capacity for larger selections.
    const mode = `${fast}/${ids.includes('shell')}/${push}/${bin.cap}`;
    if (autos.has(mode)) assert(auto === autos.get(mode), 'payload selection changed AutoRun');
    else autos.set(mode, auto);
    report.push({label, ids, fast, push, used:bin.used, cap:bin.cap, entries:Array.from(c.entries)});
    if (process.argv[3]) {
      const dest = path.join(process.argv[3], label);
      fs.mkdirSync(dest);
      fs.writeFileSync(path.join(dest, 'fpSup.BIN'), output);
      fs.writeFileSync(path.join(dest, 'AutoRun.txt'), auto);
      for (const r of CAT.ui) {
        const file = path.join(dest, 'FPSUPUI', r.n);
        fs.mkdirSync(path.dirname(file), {recursive:true});
        fs.writeFileSync(file, Buffer.from(r.b, 'base64'));
      }
    }
  }
}
if (process.argv[3]) fs.writeFileSync(path.join(process.argv[3], 'matrix.json'), JSON.stringify(report, null, 2) + '\n');
console.log(`PASS ${report.length} Merge combinations; ${rejected} oversized combinations correctly rejected; maximum ${Math.max(...report.map(r => r.used))}/${CAT.cap_patch.max} bytes`);

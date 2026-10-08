// Use the existing Fast Start 3 composer; keep payloads byte-for-byte.
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const [focus, output, indoor, lv] = process.argv.slice(2);
assert(focus && output && indoor && lv, 'Usage: node focus-inset/build_combined.js FOCUS_INPUT OUTPUT INDOOR_BIN LV_BIN');
const html = fs.readFileSync('tools/card-composer/index.html', 'utf8');
const block = id => html.match(new RegExp('<script id="' + id + '"[^>]*>([\\s\\S]*?)<\\/script>'))[1];
const CAT = JSON.parse(block('cat'));
const ctx = vm.createContext({CAT, atob: s => Buffer.from(s, 'base64').toString('binary'),
    btoa: s => Buffer.from(s, 'binary').toString('base64')});
vm.runInContext(block('compose') + html.slice(html.indexOf('function parseVshl('), html.indexOf('function addFiles(')) + `
globalThis.api = {parseVshl, make(cards, fast, shell) {
    uploads.length = 0; on.clear();
    for (const [id, card] of cards) {
        uploads.push({id, name:id, upload:true, entry:card.entry, records:card.recs}); on.add(id);
    }
    if (shell) on.add('shell'); fastOn = fast; pushOn = false;
    const c = composed(), bin = composeVshl(c.recs, c.entry);
    return {c, bin, auto:composeAutorun(''), bad:runChecks(c.recs, bin, '', c.entry, c.entries).filter(x => !x.ok)};
}};`, ctx);
const files = [
    ['Indoor', indoor],
    ['LV Boost', lv],
    ['Focus Inset', focus + '/fpSup.BIN']
];
const cards = files.map(([id, file]) => {
    const b = fs.readFileSync(file);
    return [id, ctx.api.parseVshl(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength))];
});
fs.mkdirSync(output);
for (const [name, fast, shell] of [['card', true, false], ['ordinary', false, false],
                                 ['debug', false, true], ['fast-debug', true, true]]) {
    const r = ctx.api.make(cards, fast, shell);
    assert.equal(r.bad.length, 0, JSON.stringify(r.bad));
    assert.equal(r.c.entries.length, shell ? 4 : 3);
    const bin = Buffer.from(r.bin.bytes), table = bin.readUInt32LE(8) + CAT.trampoline.tbl;
    for (let i = 0; i < cards.length; i++) {
        const launcher = Buffer.from(cards[i][1].recs.filter(x => x.a === 0)[1].b, 'base64');
        const entry = r.c.entries[i + (shell ? 1 : 0)];
        assert(bin.subarray(entry, entry + launcher.length).equals(launcher), 'Payload entry/order changed');
        assert.equal(bin.readUInt32LE(table + 4 * (i + (shell ? 1 : 0) + 1)), entry);
    }
    const dest = output + '/' + name; fs.mkdirSync(dest);
    fs.writeFileSync(dest + '/fpSup.BIN', bin); fs.writeFileSync(dest + '/AutoRun.txt', r.auto);
    fs.mkdirSync(dest + '/FPSUPUI');
    for (const f of CAT.ui) fs.writeFileSync(dest + '/FPSUPUI/' + f.n, Buffer.from(f.b, 'base64'));
    if (!shell) assert(!r.c.recs.some(x => x.a === 0xC072F000 || x.a === 0xC072F050), 'Unexpected shell worker');
    fs.writeFileSync(dest + '/composition.json', JSON.stringify({used:r.bin.used, capacity:r.bin.cap,
        entries:r.c.entries, fast, shell, checks:r.bad}, null, 2) + '\n');
    console.log('PASS', name, r.bin.used + '/' + r.bin.cap, 'bytes, retained ordered entries');
}

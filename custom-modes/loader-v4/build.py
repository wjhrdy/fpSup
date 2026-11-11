"""Build Indoor and LV Boost as independent modules for upstream fpSup Merge v4."""
import argparse
import hashlib
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
UPSTREAM = '21bcc5578e0d17d6f71872c0664e8132b2b28fe4'
INDOOR = 'Indoor_v0.4.5.BIN'
LV = 'LV-Boost_v0.6.1.BIN'


def build(upstream, output):
    if subprocess.check_output(['git', '-C', str(upstream), 'rev-parse', 'HEAD'],
                               text=True).strip() != UPSTREAM:
        raise SystemExit(f'Use upstream fpSup at {UPSTREAM}')
    sys.path[:0] = [str(upstream / 'fpSup/loader-v4'),
                    str(REPO / 'color-modes/lv-boost/build'), str(HERE.parent)]
    from build_v4 import make_sup, SL4_HEADER_LEN, SL_F_CACHED_OK
    from armasm import assemble, symbols
    import build_indoor as indoor
    import build_lv_boost as lv

    rom = lv.ROM.read_bytes()
    if hashlib.sha256(rom).hexdigest() != indoor.ROM_HASH:
        raise SystemExit('Expected extracted SIGMA fp 5.02 firmware')
    seg1 = lv.SEG1.read_bytes()
    if hashlib.sha256(seg1).hexdigest() != '0dcaca8f5441fe4ddc6ed801cb888e325df4e76006e4f53a1c3219809b22ce7b':
        raise SystemExit('Expected extracted SIGMA fp 5.02 data segment')
    src = HERE.parent / 'indoor.S'
    defs = ['LOADER_V4=1']
    indoor_blob = assemble(src, defs)
    assert symbols(src, defs)['entry'] == 0
    lv_blob, _ = lv.build_blob(True, 2, loader_v4=True)
    # These are Indoor's active hooks. Legacy experiment cleanup words do not
    # belong to this sup on v4. The first site proves installation for each sup.
    indoor_sites = {indoor.GETTER: 0xe92d4010, indoor.DRAW_SITE: indoor.STOCK[indoor.DRAW_SITE],
                    0xc052884c: indoor.STOCK[0xc052884c]}
    indoor_claims = [(a, struct.pack('<I', word)) for a, word in indoor_sites.items()]
    assert all(rom[a - 0xc0000000:a - 0xc0000000 + 4] == word for a, word in indoor_claims)
    lv_claims = [(a, word) for a, word, _ in lv.hook_sites(True)]
    lv_claims.sort(key=lambda pair: pair[0] != 0xc06c07d8)
    assert lv_claims[0][0] == 0xc06c07d8
    claims = indoor_claims + lv_claims
    assert len({a for a, _ in claims}) == len(claims)

    output.mkdir(parents=True)
    for name, ident, version, display, installer, records in (
        (INDOOR, 'INDR', 0x000405, 'Indoor', indoor_blob, indoor_claims),
        (LV, 'LVBT', 0x000601, 'LV Boost', lv_blob, lv_claims),
    ):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / 'install.bin').write_bytes(installer)
            (tmp / 'claims.bin').write_bytes(b''.join(struct.pack('<I', a) + w for a, w in records))
            body = assemble(HERE / 'entry.S', [f'CLAIM_COUNT={len(records)}',
                            f'CLAIM_FILE="{tmp / "claims.bin"}"', f'INSTALL_FILE="{tmp / "install.bin"}"'])
        (output / name).write_bytes(make_sup(body, SL4_HEADER_LEN, ident,
                                     version=version, name=display, min_svc=5, flags=SL_F_CACHED_OK))
        print(name, len(body), 'bytes;', len(records), 'exclusive hook claims')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.upstream.resolve(), args.out.resolve())

"""Package the verified Merge inputs and ready Fast Start card for GitHub."""
import argparse
import hashlib
from pathlib import Path
from shutil import copyfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from build import REPO, INDOOR, LV

TAG = 'fpsup-indoor-lvboost-v1.4.0test'
NAME = 'Indoor-LV-Boost-v1.4.0test'
README = REPO / 'releases' / TAG / 'README.txt'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sums(files):
    return ''.join(f'{digest(b)}  {n}\n' for n, b in sorted(files.items())).encode()


def archive(path, files):
    files = {**files, 'README.txt': README.read_bytes()}
    files['SHA256SUMS'] = sums(files)
    with ZipFile(path, 'x') as z:
        for name, data in sorted(files.items()):
            info = ZipInfo(name, (2026, 11, 10, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            z.writestr(info, data, compress_type=ZIP_DEFLATED, compresslevel=9)
    with ZipFile(path) as z:
        assert z.testzip() is None and set(z.namelist()) == set(files)
        assert all(z.read(name) == data for name, data in files.items())


def package(upstream, modules, card, output, legacy):
    payloads = {n: (modules / n).read_bytes() for n in (INDOOR, LV)}
    names = {'AutoRun.txt', 'fpSup/LOADER.BIN', 'fpSup/SUPMGR.BIN',
             *(f'fpSup/{n}' for n in payloads),
             *(f'fpSup/UI/{i}.BIN' for i in range(5)),
             'fpSup/UI/FPSUP.BIN', 'fpSup/UI/SUPMGR.BIN'}
    assert {p.relative_to(card).as_posix() for p in card.rglob('*') if p.is_file()} == names
    files = {n: (card / n).read_bytes() for n in names}
    assert all(files[f'fpSup/{n}'] == blob for n, blob in payloads.items())
    for n in ('LICENSE', 'NOTICE'):
        files[f'upstream-{n}.txt'] = (upstream / 'fpSup' / n).read_bytes()
    output.mkdir(parents=True)
    archive(output / f'{NAME}-Merge-v4.zip', payloads)
    archive(output / f'{NAME}-Loader-v4-Fast-Start.zip', files)
    if legacy:
        assert digest(legacy.read_bytes()) == 'ff90dfe79a957170d8bf5aa491b95113dca926dcfd2f8eb327180fe82a5211d0'
        copyfile(legacy, output / f'{NAME}-Legacy-Compact-Startup.zip')
    (output / 'SHA256SUMS.txt').write_bytes(sums({p.name: p.read_bytes() for p in output.glob('*.zip')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('upstream', 'modules', 'card', 'out'):
        parser.add_argument('--' + arg, type=Path, required=True)
    parser.add_argument('--legacy', type=Path)
    args = parser.parse_args()
    package(args.upstream, args.modules, args.card, args.out, args.legacy)

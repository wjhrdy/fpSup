"""Package already-built cards; never modifies a BIN or accesses a camera."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parent

def package(focus,indoor,combined):
    names={'focus':'fpsup-focus-inset-v0.1.0test','card':'fpsup-indoor-lvboost-v1.3.0test','fast-debug':'fpsup-indoor-lvboost-debug-v1.3.0test'}
    sources={'focus':focus,'card':combined/'card','fast-debug':combined/'fast-debug'}
    readme=(HERE/'README.md').read_text()
    assets={}
    for variant,name in names.items():
        dest=REPO/'releases'/name;dest.mkdir()
        source=sources[variant]
        for n in ['AutoRun.txt','fpSup.BIN']:
            shutil.copy2(source/n,dest/n)
        if (source/'FPSUPUI').exists():shutil.copytree(source/'FPSUPUI',dest/'FPSUPUI')
        (dest/'README.txt').write_text(readme+'\nPackage: '+name+'\n')
        descriptions={'focus':'Small always-visible manual-lens focus inset in STILL live view; fp firmware 5.02. Test build.', 'card':'Indoor, LV Boost and Focus Inset together with Fast Start 3; fp firmware 5.02. Test build.', 'fast-debug':'Indoor, LV Boost and Focus Inset with Fast Start 3 and USB debugging; fp firmware 5.02. Test build.'}
        (dest/'ABOUT.txt').write_text('en: '+descriptions[variant]+'\nzh: SIGMA fp 5.02 測試版：手動鏡頭對焦放大視窗。\n')
        data={'variant':variant,'firmware':'SIGMA fp 5.02','payloads':({'Focus Inset':'0.1.0test'} if variant=='focus' else {'Focus Inset':'0.1.0test','Indoor':'0.4.5','LV Boost':'0.6.1'}),'fast_start':variant!='focus','shell':variant=='fast-debug','hardware_confirmation':'2026-10-08 exact Fast-debug card; standalone/no-Shell offline checked','files':{str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.rglob('*') if p.is_file()}}
        (dest/'MANIFEST.txt').write_text(json.dumps(data,indent=2)+'\n')
        assets[variant]=dest
    # Merge inputs contain ordinary startup only, never a combined Fast card.
    for title,source,extra in [('Focus-Inset-v0.1.0test-Merge-Sigma-fp-5.02.zip',focus,HERE),('Indoor-v0.4.5-Merge-Sigma-fp-5.02.zip',indoor,REPO/'custom-modes')]:
        path=extra/title
        assert not path.exists()
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
            for n in ['AutoRun.txt','fpSup.BIN']:z.write(source/n,n)
            z.writestr('README.txt',readme if extra==HERE else (extra/'README.md').read_text())
        assets[title]=path
    for variant,title in [('card','fpsup-indoor-lvboost-v1.3.0test.zip'),('fast-debug','fpsup-indoor-lvboost-v1.3.0test-USB-Debug.zip')]:
        dest=assets[variant];path=dest/title
        assert not path.exists()
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(dest.rglob('*')):
                if p.is_file() and p!=path:z.write(p,str(p.relative_to(dest)))
        assets[title]=path
    merge_html=REPO/'releases/fpsup-indoor-lvboost-v1.3.0test/fpSup-Merge-v1.3.0test.html'
    shutil.copy2(REPO/'tools/card-composer/index.html',merge_html)
    assets[merge_html.name]=merge_html
    sums=REPO/'releases/fpsup-indoor-lvboost-v1.3.0test/SHA256SUMS'
    sums.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+n+'\n' for n,p in assets.items() if isinstance(p,Path) and p.is_file()))
    print(sums.read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('focus',type=Path);p.add_argument('indoor',type=Path);p.add_argument('combined',type=Path);a=p.parse_args();package(a.focus,a.indoor,a.combined)

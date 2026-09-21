"""Copy the qualified deep-server Python environment into a fresh image context.

Run with the existing deep-server venv Python and one new absolute output path.
No package install, source mutation, host configuration or credentials are copied.
The resulting image still requires target-host numerical qualification.
"""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,sys
from dsdm_phase1 import goal052_seawfb_dsdm
import ssl,sqlite3,bz2,lzma,ctypes
context=Path(sys.argv[1]).resolve(); context.mkdir(parents=True,exist_ok=False)
rootfs=context/'rootfs'; rootfs.mkdir()
venv=Path('/data/codex/repos/dSDM/.venv'); stdlib=Path('/usr/lib/python3.12')
for source in (venv,stdlib):
    target=rootfs/source.relative_to('/');target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(source,target,symlinks=True)
def copy_file(source):
    source=Path(source);target=rootfs/source.parent.resolve().relative_to('/')/source.name
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target,follow_symlinks=True)
copy_file('/usr/bin/python3.12')
seeds={Path('/usr/bin/python3.12'),*stdlib.glob('lib-dynload/*.so')}
for line in Path('/proc/self/maps').read_text().splitlines():
    fields=line.split()
    if len(fields)>5 and fields[-1].startswith('/') and '.so' in fields[-1]:
        path=Path(fields[-1])
        if not path.name.startswith('libcuda.so'):seeds.add(path)
libraries=set()
for seed in sorted(seeds):
    # Wheel libraries may resolve one another through their importing module's
    # RPATH. Their complete trees are already copied, and loaded system
    # dependencies are present in /proc/self/maps. Bare ldd is misleading here.
    if seed.is_relative_to(venv):
        continue
    result=subprocess.run(['ldd',str(seed)],text=True,capture_output=True)
    if 'not found' in result.stdout:raise RuntimeError(str(seed)+result.stdout)
    libraries.update(Path(m.group(1)) for m in re.finditer(r'(?:=> )?(/[^\s]+)',result.stdout))
    if '.so' in seed.name:libraries.add(seed)
for path in sorted(libraries):
    if path.is_relative_to(venv) or path.is_relative_to(stdlib) or path.name.startswith('libcuda.so'):continue
    copy_file(path);copy_file(path.resolve())
manifest={}
for path in sorted(rootfs.rglob('*')):
    relative=str(path.relative_to(rootfs))
    if path.is_symlink():manifest[relative]={'symlink':str(path.readlink())}
    elif path.is_file():
        with path.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
        manifest[relative]={'bytes':path.stat().st_size,'sha256':sha}
(context/'runtime-manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
print('RUNTIME_SNAPSHOT',len(manifest),flush=True)

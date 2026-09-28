from pathlib import Path
import zipfile,shutil,hashlib,json,subprocess,sys
out=Path('output').resolve();out.mkdir(exist_ok=True)
root=Path('desktop').resolve()
with zipfile.ZipFile('baseline/desktop-source-and-content.zip') as z:z.extractall(root)
with zipfile.ZipFile('hotfix/desktop-hotfix-source.zip') as z:z.extractall(root)
for n in ['graphics.go','graphics_test.go']:
 shutil.copy2(Path('zombiefarm-safegraphics')/n,root/'launcher'/n)
p=root/'launcher/main.go';s=p.read_text(encoding='utf-8').replace('0.15.1','0.15.2')
s=s.replace('f.UncompressedSize64 > 128<<20','f.UncompressedSize64 > 256<<20')
a='if e = installHostFonts(dir); e != nil {'
assert s.count(a)==1
s=s.replace(a,'if e = verifyGraphics(dir, m); e != nil { return e }\n\t'+a)
s=s.replace('Graphics: desktop OpenGL 2.1 compatibility (gles1_on_gl2); native OpenGL ES probing bypassed.','Graphics: BUNDLED Mesa 25.1.6 llvmpipe CPU renderer; host OpenGL bypassed; v0.15.2 compatibility build.')
s=s.replace('showError("Zombie Farm", e.Error())','showError("Zombie Farm " + version, e.Error())')
p.write_text(s,encoding='utf-8')
p=root/'tools/package.py';s=p.read_text(encoding='utf-8').replace('0.15.1','0.15.2');p.write_text(s,encoding='utf-8')
compat=root/'content/compat';compat.mkdir(exist_ok=True)
for n in ['opengl32.dll','libgallium_wgl.dll']:
 f=Path('mesa/x64')/n
 assert f.exists(),str(f)
 shutil.copy2(f,compat/n)
# Keep the release's licenses. Do not bundle fonts or install a system driver.
for f in Path('mesa').rglob('*'):
 if f.is_file() and (f.name.lower().startswith(('license','copying')) or 'licenses' in f.parts):
  if f.suffix.lower() in ('.ttf','.otf','.woff','.woff2'):continue
  dest=compat/'licenses'/f.relative_to('mesa');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
(compat/'README.txt').write_text('Mesa 25.1.6 MSVC x64, per-application llvmpipe compatibility renderer.\nSource and full license notices: https://github.com/pal1000/mesa-dist-win/releases/tag/25.1.6\nArchive SHA256: 7b4dea5f4fdd362acaffd13f4dd01de3b1e3f67a24c89ab92957eeb8a404e23d\nThis is software rendering; performance is not equivalent to GPU acceleration.\nNo global driver, system DLL or Wine registry is replaced.\n',encoding='utf-8')
subprocess.run(['gofmt','-w',str(root/'launcher')],check=True)
subprocess.run([sys.executable,str(root/'tools/package.py'),'--runtime',str(Path('baseline/runtime').resolve()),'--platform','windows','--out',str(out)],check=True)
# Compare every original byte against the prior shipped manifest, not only filenames.
prior=json.loads(Path('hotfix/windows-manifest.json').read_text(encoding='utf-8'))
new=json.loads((out/'windows-manifest.json').read_text(encoding='utf-8'))
keys=[n for n in prior['files'] if n.startswith('Game/') or n=='touchHLE.exe']
assert keys and all(prior['files'][n]==new['files'][n] for n in keys)
(out/'preserved-content.json').write_text(json.dumps({'original_game_files':sum(n.startswith('Game/') for n in keys),'runtime_unchanged':True,'graphics_files':{n:v for n,v in new['files'].items() if n.startswith('compat/')}},indent=2))
# Preserve exactly what was compiled and bundled, including the editable source.
with zipfile.ZipFile(out/'desktop-source-and-content.zip','w',zipfile.ZIP_DEFLATED) as z:
 for folder in ['launcher','tools','tests','content']:
  for f in (root/folder).rglob('*'):
   if f.is_file() and f.name!='payload.zip' and '__pycache__' not in f.parts:
    assert f.suffix.lower() not in ('.ttf','.otf','.woff','.woff2')
    z.write(f,f.relative_to(root).as_posix())
shutil.copy2('baseline/runtime-source.zip',out/'runtime-source.zip')
# Native Windows QA must use the delivered package, with no driver copying.
s=Path('hotfix/windows_qa.py').read_text(encoding='utf-8').replace('0.15.1','0.15.2')
a=s.index(' # A hosted VM lacks a physical OpenGL GPU.')
b=s.index(" (home/'UserData/touchHLE_options.txt').write_text",a)
s=s[:a]+" # Graphics must come solely from the embedded package.\n assert not (d/'opengl32.dll').exists()\n assert (d/'compat/opengl32.dll').exists()\n"+s[b:]
a=" check('saved_native_preference_not_modified'"
pos=s.index(a)
s=s[:pos]+" check('bundled_llvmpipe_renderer_active','llvmpipe' in log_text and 'Mesa 25.1.6' in log_text,log_text[:3000])\n"+s[pos:]
(out/'windows_qa.py').write_text(s,encoding='utf-8')
print('Packaged v0.15.2 with original runtime and bundled graphics. Actual Windows and Wine tests follow.')

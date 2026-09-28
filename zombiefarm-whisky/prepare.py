from pathlib import Path
import zipfile, shutil, subprocess, sys, os, hashlib, json
base=Path('baseline');root=Path('desktop');out=Path('output');out.mkdir(exist_ok=True)
with zipfile.ZipFile(base/'desktop-source-and-content.zip') as z:
 for n in z.namelist():
  if '..' in Path(n).parts or Path(n).is_absolute():raise ValueError(n)
 z.extractall(root)
p=root/'launcher/main.go';s=p.read_text(encoding='utf-8')
assert s.count('var version = "0.15"')==1
s=s.replace('var version = "0.15"','var version = "0.15.1"')
a='cmd := exec.Command(filepath.Join(dir, exe), "Game/ZombieFarm.app", "--scale-hack=2")'
assert s.count(a)==1;s=s.replace(a,'cmd := exec.Command(filepath.Join(dir, exe), runtimeArguments()...)')
a='configureProcess(cmd)\n\t\te = runVisible(cmd, root, log)'
b='configureGraphics(cmd)\n\t\tfmt.Fprintln(log, "Graphics: desktop OpenGL 2.1 compatibility (gles1_on_gl2); native OpenGL ES probing bypassed.")\n\t\tconfigureProcess(cmd)\n\t\te = runVisible(cmd, root, log)'
assert s.count(a)==1;s=s.replace(a,b);p.write_text(s,encoding='utf-8',newline='\n')
for name in ('graphics.go','graphics_test.go'):
 p=root/'launcher'/name;s=(Path('zombiefarm-whisky')/name).read_text(encoding='utf-8')
 if name=='graphics_test.go':
  s=s.replace('want:=[]string{"Path=abc","ZF_USER_DATA=test-farm","OTHER=x=y","OTHER_DUMMY=unused"}\n want=want[:4];want=append(want,"SDL_OPENGL_ES_DRIVER=0")','want:=[]string{"Path=abc","ZF_USER_DATA=test-farm","OTHER=x=y","SDL_OPENGL_ES_DRIVER=0"}')
 p.write_text(s,encoding='utf-8',newline='\n')
subprocess.run(['gofmt','-w',str(root/'launcher/main.go'),str(root/'launcher/graphics.go'),str(root/'launcher/graphics_test.go')],check=True)
p=root/'tools/package.py';s=p.read_text(encoding='utf-8').replace("'0.15'","'0.15.1'").replace('v0.15.exe','v0.15.1.exe').replace('v0.15_QA','v0.15.1_QA');p.write_text(s,encoding='utf-8',newline='\n')
# The preserved artifact contains the runtime and its redistribution DLLs.
runtime=base/'runtime'
assert (runtime/'touchHLE.exe').exists(),str(list(base.iterdir()))
subprocess.run([sys.executable,str(root/'tools/package.py'),'--runtime',str(runtime.resolve()),'--platform','windows','--out',str(out.resolve())],check=True)
# A native Windows test binary is also reusable under Wine without Python-in-Wine.
subprocess.run(['go','test','-c','-o',str((out/'launcher-regression.test.exe').resolve())],cwd=root/'launcher',check=True)
with zipfile.ZipFile(out/'desktop-hotfix-source.zip','w',zipfile.ZIP_DEFLATED)as z:
 for folder in ('launcher','tools','tests'):
  for p in (root/folder).rglob('*'):
   if p.is_file() and p.name!='payload.zip' and '__pycache__' not in p.parts:z.write(p,p.relative_to(root).as_posix())
(out/'exe-sha256.txt').write_text(hashlib.sha256((out/'Zombie_Farm_Windows_v0.15.1.exe').read_bytes()).hexdigest())
# Existing QA deliberately starts with the WRONG saved renderer. The hotfix must
# override that in arguments, with no test-side renderer repair or config rewrite.
p=root/'tools/windows_qa.py';s=p.read_text(encoding='utf-8').replace('v0.14.exe','v0.15.1.exe').replace("'0.14-*'","'0.15.1-*'")
s=s.replace('com.playforge.ZombieFarm: --gles1=gles1_on_gl2','com.playforge.ZombieFarm: --gles1=gles1_native')
s=s.replace("started=time.monotonic();proc=", "config_before=(home/'UserData/touchHLE_options.txt').read_bytes()\n started=time.monotonic();proc=")
a="time.sleep(18);capture('01-windows-visible-launch.png')"
b=a+"\n log_text=(home/'UserData/logs/latest.log').read_text(encoding='utf-8',errors='replace')\n check('desktop_renderer_selected_without_native_probe','Trying: OpenGL ES 1.1 via touchHLE GLES1-on-GL2 layer' in log_text and 'Trying: OpenGL ES 1.1 (native)' not in log_text,log_text[:3000])\n check('saved_native_preference_not_modified',(home/'UserData/touchHLE_options.txt').read_bytes()==config_before,{})"
assert s.count(a)==1;s=s.replace(a,b);p.write_text(s,encoding='utf-8',newline='\n')

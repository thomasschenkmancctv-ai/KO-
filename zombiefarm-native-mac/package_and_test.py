from pathlib import Path
import zipfile,hashlib,json,plistlib,shutil,subprocess,os,time,traceback
root=Path('desktop').resolve();out=Path('native-output').resolve();out.mkdir(exist_ok=True)
with zipfile.ZipFile('baseline/desktop-source-and-content.zip')as z:z.extractall(root)
with zipfile.ZipFile('hotfix/desktop-hotfix-source.zip')as z:z.extractall(root)
launcher=root/'launcher'
p=launcher/'main.go';s=p.read_text().replace('0.15.1','0.15.2')
a='\t\t\t} else {\n\t\t\t\tcandidates = []string{"/usr/share/fonts/'
b='''\t\t\t} else if runtime.GOOS == "darwin" {
                macFamily := map[string]string{"Mono":"Courier New", "Sans":"Arial", "Serif":"Times New Roman"}[family]
                macStyle := map[string]string{"Regular":"", "Bold":" Bold", "Italic":" Italic", "BoldItalic":" Bold Italic"}[style]
                candidates = []string{filepath.Join("/System/Library/Fonts/Supplemental", macFamily+macStyle+".ttf"), "/System/Library/Fonts/Supplemental/Arial.ttf"}
            } else {
                candidates = []string{"/usr/share/fonts/'''
assert s.count(a)==1;s=s.replace(a,b);p.write_text(s)
s=(launcher/'platform_linux.go').read_text()
s=s.replace('func showError(title, msg string)                             { fmt.Fprintln(os.Stderr, title+": "+msg) }','''func showError(title, msg string) {
 fmt.Fprintln(os.Stderr,title+": "+msg)
 _ = exec.Command("osascript", "-e", "on run argv", "-e", "display alert (item 1 of argv) message (item 2 of argv)", "-e", "end run", title, msg).Run()
}''')
(launcher/'platform_darwin.go').write_text(s)
# Unlike the Windows compatibility package, use the native macOS OpenGL backend.
(launcher/'graphics.go').write_text('package main\nimport "os/exec"\nfunc runtimeArguments() []string {return []string{"Game/ZombieFarm.app","--scale-hack=2","--gles1=gles1_on_gl2"}}\nfunc configureGraphics(cmd *exec.Cmd) {}\n')
(launcher/'graphics_test.go').unlink(missing_ok=True)
engine=Path('engine').resolve();runtime=engine/'target/release/touchHLE'
subprocess.run(['codesign','--force','--sign','-',str(runtime)],check=True)
files={f.relative_to(root/'content').as_posix():f for f in (root/'content').rglob('*') if f.is_file()}
files['touchHLE']=runtime
for n in ['LICENSE','touchHLE_default_options.txt']:files[n]=engine/n
for f in (engine/'touchHLE_dylibs').glob('*'):
 if f.is_file():files['touchHLE_dylibs/'+f.name]=f
assert all(Path(n).suffix.lower()not in ('.ttf','.otf','.ttc','.woff','.woff2') for n in files)
manifest={'version':'0.15.2','platform':'macos-arm64','files':{n:{'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'size':f.stat().st_size} for n,f in files.items()}}
with zipfile.ZipFile(launcher/'payload.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
 for n in sorted(files):z.write(files[n],n)
 z.writestr('package-manifest.json',json.dumps(manifest,sort_keys=True))
subprocess.run(['gofmt','-w',str(launcher)],check=True)
r=subprocess.run(['go','test','-v','./...'],cwd=launcher,text=True,capture_output=True);(out/'launcher-tests.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr
app=out/'Zombie Farm.app';mac=app/'Contents/MacOS';mac.mkdir(parents=True,exist_ok=True)
subprocess.run(['go','build','-trimpath','-ldflags=-s -w','-o',str(mac/'ZombieFarm'),'.'],cwd=launcher,env=dict(os.environ,CGO_ENABLED='0'),check=True)
plist={'CFBundleExecutable':'ZombieFarm','CFBundleIdentifier':'local.zombiefarm.desktop','CFBundleName':'Zombie Farm','CFBundleDisplayName':'Zombie Farm','CFBundleShortVersionString':'0.15.2','CFBundleVersion':'152','CFBundlePackageType':'APPL','LSMinimumSystemVersion':'12.0','NSHighResolutionCapable':True}
(app/'Contents/Info.plist').write_bytes(plistlib.dumps(plist))
subprocess.run(['codesign','--force','--deep','--sign','-',str(app)],check=True)
subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(app),str(out/'Zombie_Farm_Mac_v0.15.2.zip')],check=True)
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
(out/'architecture.txt').write_text(subprocess.check_output(['file',str(mac/'ZombieFarm'),str(runtime)],text=True)+'\n'+subprocess.check_output(['otool','-L',str(runtime)],text=True))
with zipfile.ZipFile(out/'native-source-and-content.zip','w',zipfile.ZIP_DEFLATED)as z:
 for folder in ['launcher','tools','tests','content']:
  for f in (root/folder).rglob('*'):
   if f.is_file() and f.name!='payload.zip' and '__pycache__'not in f.parts:z.write(f,f.relative_to(root).as_posix())
with zipfile.ZipFile(out/'runtime-source.zip','w',zipfile.ZIP_DEFLATED)as z:
 for f in (engine/'src').rglob('*'):
  if f.is_file():z.write(f,f.relative_to(engine).as_posix())
 for n in ['Cargo.toml','Cargo.lock','build.rs','.gitmodules','LICENSE']:z.write(engine/n,n)
import Quartz
shots=out/'screenshots';shots.mkdir(exist_ok=True)
home=Path('native-qa-home').resolve();env=dict(os.environ,ZF_HOME=str(home),ZF_SKIP_START_MENU='1',ALSOFT_DRIVERS='null')
checks=[];p=None
def check(name,ok,details=None):
 checks.append(dict(test=name,passed=bool(ok),details=details));(out/'mac-native-qa.json').write_text(json.dumps(checks,indent=2));print(name,bool(ok),flush=True)
 if not ok:raise AssertionError(name+': '+str(details))
def window():
 for w in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly,Quartz.kCGNullWindowID):
  if 'ZombieFarm' in str(w.get('kCGWindowName','')) and w.get('kCGWindowBounds',{}).get('Width',0)>300:return w
 return None
def shot(name):
 w=window();check('visible_'+name,bool(w));subprocess.run(['screencapture','-x','-l'+str(w['kCGWindowNumber']),str(shots/name)],check=True)
def click(rx,ry):
 w=window();assert w
 b=w['kCGWindowBounds'];pos=(b['X']+rx*b['Width'],b['Y']+28+ry*(b['Height']-28))
 for t in [Quartz.kCGEventMouseMoved,Quartz.kCGEventLeftMouseDown,Quartz.kCGEventLeftMouseUp]:
  Quartz.CGEventPost(Quartz.kCGHIDEventTap,Quartz.CGEventCreateMouseEvent(None,t,pos,Quartz.kCGMouseButtonLeft));time.sleep(.15)
try:
 p=subprocess.Popen([str(mac/'ZombieFarm')],env=env,stdout=(out/'process.log').open('w'),stderr=subprocess.STDOUT)
 for _ in range(120):
  if window() or p.poll()is not None:break
  time.sleep(.5)
 check('native_mac_app_visible',bool(window()),{'exit':p.poll()})
 time.sleep(12);shot('01-native-mac-title.png')
 text=(home/'UserData/logs/latest.log').read_text(errors='replace')
 check('native_mac_opengl_context_success','=> Success!' in text and 'CPU emulation begins' in text,text[:4000])
 for _ in range(3):click(.5,.55);time.sleep(4)
 shot('02-native-mac-play.png');check('native_game_survives_play',p.poll()is None)
 # Close the actual SDL game through its normal window control.
 w=window();b=w['kCGWindowBounds'];pos=(b['X']+13,b['Y']+13)
 for t in [Quartz.kCGEventLeftMouseDown,Quartz.kCGEventLeftMouseUp]:Quartz.CGEventPost(Quartz.kCGHIDEventTap,Quartz.CGEventCreateMouseEvent(None,t,pos,Quartz.kCGMouseButtonLeft));time.sleep(.15)
 check('native_mac_normal_close',p.wait(timeout=20)==0)
except Exception:
 (out/'qa-error.txt').write_text(traceback.format_exc());subprocess.run(['screencapture','-x',str(shots/'failure-desktop.png')]);raise
finally:
 if (home/'UserData/logs').exists():shutil.copytree(home/'UserData/logs',out/'logs',dirs_exist_ok=True)
 if p and p.poll()is None:p.terminate()
 (out/'macos-version.txt').write_text(subprocess.check_output(['sw_vers'],text=True)+'\n'+subprocess.check_output(['uname','-m'],text=True))

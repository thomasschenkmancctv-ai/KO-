from pathlib import Path
import os,subprocess,time,hashlib,json,traceback,shutil
import Quartz
out=Path('mac-evidence');out.mkdir(exist_ok=True);shots=out/'screenshots';shots.mkdir(exist_ok=True)
exe=Path('build/Zombie_Farm_Windows_v0.15.2.exe').resolve()
wine=next(Path('wine-dist').rglob('bin/wine')).resolve()
prefix=Path('mac-test-prefix').resolve();env=dict(os.environ,WINEPREFIX=str(prefix),WINEDEBUG='-all',WINEDLLOVERRIDES='mscoree,mshtml=;opengl32=b',ZF_HOME=r'C:\ZombieFarmMacQA',ZF_SKIP_START_MENU='1',ALSOFT_DRIVERS='null')
checks=[];proc=None

def check(name,value,details=None):
 checks.append(dict(test=name,passed=bool(value),details=details));(out/'results.json').write_text(json.dumps(checks,indent=2));print(name,bool(value),flush=True)
 if not value:raise AssertionError(name+': '+str(details))
def run(*args,timeout=90):return subprocess.run([str(wine),*map(str,args)],env=env,text=True,capture_output=True,timeout=timeout)
def find_window():
 info=Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly,Quartz.kCGNullWindowID)
 for w in info:
  title=str(w.get('kCGWindowName',''));b=w.get('kCGWindowBounds',{})
  if 'ZombieFarm' in title and int(b.get('Width',0))>=300:return w
 return None

def screenshot(name):
 w=find_window();check('visible_'+name,w is not None)
 subprocess.run(['screencapture','-x','-l'+str(w['kCGWindowNumber']),str(shots/name)],check=True)
 return w

def click(rx,ry):
 w=find_window();assert w is not None
 b=w['kCGWindowBounds'];x=b['X']+rx*b['Width'];y=b['Y']+28+ry*(b['Height']-28)
 for t in [Quartz.kCGEventMouseMoved,Quartz.kCGEventLeftMouseDown,Quartz.kCGEventLeftMouseUp]:
  e=Quartz.CGEventCreateMouseEvent(None,t,(x,y),Quartz.kCGMouseButtonLeft);Quartz.CGEventPost(Quartz.kCGHIDEventTap,e);time.sleep(.15)

try:
 (out/'environment.txt').write_text(subprocess.check_output(['sw_vers'],text=True)+'\n'+subprocess.check_output(['uname','-m'],text=True)+'\n'+run('--version').stdout)
 r=run('wineboot','-u');check('mac_wine_prefix_initialized',r.returncode==0,r.stderr[-3000:])
 fonts=prefix/'drive_c/windows/Fonts';fonts.mkdir(exist_ok=True,parents=True)
 for family,win in [('Arial','arial'),('Times New Roman','times'),('Courier New','cour')]:
  for style,suffix in [('', ''),(' Bold','bd'),(' Italic','i'),(' Bold Italic','bi')]:
   src=Path('/System/Library/Fonts/Supplemental')/(family+style+'.ttf')
   if not src.exists():src=Path('/System/Library/Fonts/Supplemental/Arial.ttf')
   if src.exists():shutil.copy2(src,fonts/(win+suffix+'.ttf'))
 r=run(exe,'--verify-package');check('actual_exe_extracts_on_mac',r.returncode==0,r.stdout+r.stderr)
 home=prefix/'drive_c/ZombieFarmMacQA';data=home/'UserData'
 opts=data/'touchHLE_options.txt';opts.write_text('com.playforge.ZombieFarm: --gles1=gles1_native\n');saved=opts.read_bytes()
 logfile=(out/'wine-process.log').open('w');proc=subprocess.Popen([str(wine),str(exe)],env=env,stdout=logfile,stderr=logfile)
 text=''
 for _ in range(180):
  time.sleep(.5)
  if (data/'logs/latest.log').exists():text=(data/'logs/latest.log').read_text(errors='replace')
  if 'Driver info:' in text:break
  if proc.poll() is not None:break
 check('bundled_graphics_context_on_mac','Driver info:' in text and 'llvmpipe' in text and 'Mesa 25.1.6' in text,{'exit':proc.poll(),'log':text[:5000]})
 time.sleep(15);screenshot('01-mac-wine-title.png')
 check('old_renderer_preference_preserved',opts.read_bytes()==saved)
 for i in range(3):click(.5,.55);time.sleep(5)
 screenshot('02-mac-wine-after-play.png')
 check('game_survives_play_on_mac',proc.poll() is None)
except Exception:
 (out/'error.txt').write_text(traceback.format_exc())
 subprocess.run(['screencapture','-x',str(shots/'failure-desktop.png')])
 raise
finally:
 data=prefix/'drive_c/ZombieFarmMacQA/UserData'
 if (data/'logs').exists():shutil.copytree(data/'logs',out/'logs',dirs_exist_ok=True)
 if proc and proc.poll() is None:proc.terminate()
 subprocess.run([str(wine.parent/'wineserver'),'-k'],env=env,timeout=20)
 (out/'exe-sha256.txt').write_text(hashlib.sha256(exe.read_bytes()).hexdigest())
 (out/'scope.txt').write_text('Apple-Silicon macOS hosted runner with Wine 11.18 and the exact Windows EXE. This is not Whisky or the user\'s physical Mac. All driver files are from the embedded release; host fonts used only within test prefix, not distributed.\n')

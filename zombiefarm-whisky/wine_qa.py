from pathlib import Path
import os, subprocess, time, json, hashlib, traceback, shutil
from PIL import ImageGrab
out=Path('output');shots=out/'wine-screenshots';shots.mkdir(parents=True,exist_ok=True)
exe=(out/'Zombie_Farm_Windows_v0.15.1.exe').resolve();prefix=Path('wine-prefix').resolve()
env=os.environ.copy();env.update(WINEPREFIX=str(prefix),WINEARCH='win64',WINEDEBUG='-all',WINEDLLOVERRIDES='mscoree,mshtml=',ZF_HOME=r'C:\ZombieFarmQA',ZF_SKIP_START_MENU='0',ALSOFT_DRIVERS='null',LIBGL_ALWAYS_SOFTWARE='1')
checks=[]
def check(name,value,detail=None):
 checks.append(dict(test=name,passed=bool(value),details=detail));(out/'wine-results.json').write_text(json.dumps(checks,indent=2));print(name,bool(value),flush=True)
 if not value:raise AssertionError(name+': '+str(detail))
def wine(*args,timeout=60):return subprocess.run(['wine',*map(str,args)],env=env,capture_output=True,text=True,timeout=timeout)
r=wine('wineboot','-u');check('wine_prefix_initialized',r.returncode==0,r.stderr[-2000:])
# Only use installed OS fonts inside the isolated test prefix. Never ship them.
fontdir=prefix/'drive_c/windows/Fonts';fontdir.mkdir(parents=True,exist_ok=True)
for family,win in [('Sans','arial'),('Serif','times'),('Mono','cour')]:
 for style,suffix in [('Regular',''),('Bold','bd'),('Italic','i'),('BoldItalic','bi')]:
  f=Path('/usr/share/fonts/truetype/liberation2')/f'Liberation{family}-{style}.ttf';assert f.exists(),f
  shutil.copy2(f,fontdir/(win+suffix+'.ttf'))
r=wine(exe,'--verify-package');check('exe_extracts_under_wine',r.returncode==0,r.stdout+r.stderr)
home=prefix/'drive_c/ZombieFarmQA';data=home/'UserData'
# Saved native renderer must not defeat the bundled compatibility choice.
(data/'touchHLE_options.txt').write_text('com.playforge.ZombieFarm: --gles1=gles1_native\n',encoding='utf-8');config=(data/'touchHLE_options.txt').read_bytes()
log=(out/'wine-process.log').open('w');p=subprocess.Popen(['wine',str(exe)],env=env,stdout=log,stderr=log)
def window():
 r=subprocess.run(['xdotool','search','--onlyvisible','--name','^ZombieFarm$'],env=env,capture_output=True,text=True)
 ids=r.stdout.split();return ids[-1] if ids else None
def geometry():
 wid=window();assert wid,'game window missing'
 text=subprocess.check_output(['xdotool','getwindowgeometry','--shell',wid],env=env,text=True)
 g={k:int(v) for k,v in (line.split('=',1) for line in text.splitlines() if '=' in line)}
 return wid,g

def shot(name):
 _,g=geometry();x,y,w,h=g['X'],g['Y'],g['WIDTH'],g['HEIGHT'];ImageGrab.grab(xdisplay=env['DISPLAY']).crop((x,y,x+w,y+h)).save(shots/name)
def click(rx,ry):
 _,g=geometry();subprocess.run(['xdotool','mousemove',str(int(g['X']+rx*g['WIDTH'])),str(int(g['Y']+ry*g['HEIGHT'])),'mousedown','1','sleep','.15','mouseup','1'],env=env,check=True);time.sleep(.7)
try:
 start=time.monotonic()
 for _ in range(120):
  if window():break
  if p.poll()is not None:break
  time.sleep(.25)
 check('actual_windows_exe_visible_in_wine',bool(window()),{'seconds':time.monotonic()-start,'exit':p.poll()});time.sleep(12)
 shot('01-wine-save-menu.png')
 text=(data/'logs/latest.log').read_text(encoding='utf-8',errors='replace')
 check('wine_desktop_gl_context_created','GLES1-on-GL2 layer' in text and '=> Success!' in text and "Couldn't create OpenGL ES 1.1 context" not in text,text[:3000])
 check('saved_native_option_untouched',(data/'touchHLE_options.txt').read_bytes()==config)
 # Continue row in the native-sized 960x640 Tools panel, then original PLAY.
 _,g=geometry();w,h=g['WIDTH'],g['HEIGHT'];s=min((w-24)/400,(h-24)/454,1.8)
 click(.5,((h-454*s)/2+98*s)/h);time.sleep(2);shot('02-wine-title.png')
 for _ in range(3):click(.5,.55);time.sleep(3)
 shot('03-wine-play.png')
 check('rendering_survives_menu_and_play',p.poll()is None and bool(window()))
 wid,_=geometry();subprocess.run(['xdotool','key','--window',wid,'alt+F4'],env=env,check=True)
 # With no window manager, send WM_DELETE_WINDOW directly using Xlib.
 import ctypes as C,ctypes.util
 x=C.CDLL(ctypes.util.find_library('X11'));x.XOpenDisplay.restype=C.c_void_p;x.XOpenDisplay.argtypes=[C.c_char_p];d=x.XOpenDisplay(env['DISPLAY'].encode());x.XInternAtom.argtypes=[C.c_void_p,C.c_char_p,C.c_int];x.XInternAtom.restype=C.c_ulong
 class Client(C.Structure):_fields_=[('type',C.c_int),('serial',C.c_ulong),('send_event',C.c_int),('display',C.c_void_p),('window',C.c_ulong),('message_type',C.c_ulong),('format',C.c_int),('data',C.c_long*5)]
 class Event(C.Union):_fields_=[('client',Client),('pad',C.c_long*24)]
 e=Event();e.client.type=33;e.client.display=d;e.client.window=int(wid);e.client.message_type=x.XInternAtom(d,b'WM_PROTOCOLS',0);e.client.format=32;e.client.data[0]=x.XInternAtom(d,b'WM_DELETE_WINDOW',0)
 x.XSendEvent.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_long,C.POINTER(Event)];x.XSendEvent(d,int(wid),0,0,C.byref(e));x.XFlush.argtypes=[C.c_void_p];x.XFlush(d)
 code=p.wait(timeout=20);check('clean_wine_exit',code==0,code)
except Exception:
 (out/'wine-error.txt').write_text(traceback.format_exc())
 try:ImageGrab.grab(xdisplay=env['DISPLAY']).save(shots/'failure.png')
 except Exception:pass
 raise
finally:
 if p.poll()is None:p.terminate()
 if (data/'logs').exists():shutil.copytree(data/'logs',out/'wine-logs',dirs_exist_ok=True)
 (out/'wine-tested-exe-sha256.txt').write_text(hashlib.sha256(exe.read_bytes()).hexdigest())
 (out/'wine-version.txt').write_text(subprocess.check_output(['wine','--version'],env=env,text=True))

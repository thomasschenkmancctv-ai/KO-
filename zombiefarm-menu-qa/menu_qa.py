"""Real packaged-game save-menu and invasion regression. Uses only an isolated developer farm."""
from pathlib import Path
import os,sys,time,json,subprocess,base64,zlib,hashlib,shutil,traceback,uuid,zipfile
EXE=Path(sys.argv[1]).resolve();HOME=Path(sys.argv[2]).resolve();OUT=Path(sys.argv[3]).resolve();OUT.mkdir(parents=True,exist_ok=True)
HOME.mkdir(parents=True,exist_ok=True);DATA=HOME/'UserData';DATA.mkdir(exist_ok=True)
os.environ.update(ZF_HOME=str(HOME),ZF_GROWTH_QA='1',ALSOFT_DRIVERS='null',LIBGL_ALWAYS_SOFTWARE='1')
HERE=Path(__file__).parent
fixture=next(p for p in [HERE/'work/desktop/test-fixtures/v013-completed-testfarm.b64',Path('zombiefarm-regression-fixtures/v013-completed-testfarm.b64'),Path('desktop/test-fixtures/v013-completed-testfarm.b64')]if p.exists())
for n,b in json.loads(zlib.decompress(base64.b64decode(fixture.read_text()))).items():
 p=DATA/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(b))
checks=[]
def check(n,p,d=None):
 checks.append(dict(test=n,passed=bool(p),details=d));(OUT/'results.json').write_text(json.dumps(checks,indent=2));print(n,bool(p),d if not p else '',flush=True)
 if not p:raise AssertionError(n+': '+str(d))
def read(p):
 for _ in range(25):
  try:return json.loads(p.read_text())
  except(OSError,ValueError):time.sleep(.1)
 raise RuntimeError('unreadable '+str(p))
def index():return read(HOME/'save-index.json')
def state():return read(DATA/'qa-growth-state.json')
def wait(fn,timeout=25):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  try:
   x=fn()
   if x:return x
  except(OSError,ValueError,RuntimeError):pass
  time.sleep(.2)
 raise RuntimeError('timeout waiting for expected game state')
if os.name=='nt':
 import ctypes as C,ctypes.wintypes as W
 from PIL import ImageGrab
 u=C.WinDLL('user32');u.SetProcessDPIAware();CB=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
 u.EnumWindows.argtypes=[CB,W.LPARAM];u.GetClassNameW.argtypes=[W.HWND,W.LPWSTR,C.c_int];u.GetClientRect.argtypes=[W.HWND,C.POINTER(W.RECT)];u.ClientToScreen.argtypes=[W.HWND,C.POINTER(W.POINT)];u.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM]
 def geom():
  found=[]
  @CB
  def cb(h,l):
   b=C.create_unicode_buffer(128);u.GetClassNameW(h,b,128)
   if b.value=='SDL_app':found.append(h)
   return True
  u.EnumWindows(cb,0)
  if len(found)!=1:raise RuntimeError('expected one game window: '+str(found))
  h=found[0];r=W.RECT();p=W.POINT();u.GetClientRect(h,C.byref(r));u.ClientToScreen(h,C.byref(p));return h,p.x,p.y,r.right,r.bottom
 def mouse(x,y):u.SetCursorPos(int(x),int(y));u.mouse_event(2,0,0,0,0);time.sleep(.12);u.mouse_event(4,0,0,0,0)
 def key(n):
  code={'F1':0x70,'Escape':27,'F10':0x79}[n];h=geom()[0];scan=u.MapVirtualKeyW(code,0);u.PostMessageW(h,0x100,code,1|(scan<<16));time.sleep(.12);u.PostMessageW(h,0x101,code,0xc0000001|(scan<<16));time.sleep(.3)
 def shot(n):h,x,y,w,ht=geom();ImageGrab.grab(bbox=(x,y,x+w,y+ht),all_screens=True).save(OUT/n)
 def close_game():u.PostMessageW(geom()[0],0x10,0,0)
else:
 sys.path.insert(0,str(HERE/'work/desktop/tools'));sys.path.insert(0,str(Path('desktop/tools').resolve()))
 import qa_input as q
 geom=q.window_geometry;mouse=q.click;key=q.key;close_game=q.close_game
 def shot(n):q.capture_window(OUT/n)
def panel(row):
 h,x,y,w,ht=geom();sc=max(.2,min((w-24)/400,(ht-24)/454,1.8));mouse(x+(w-400*sc)/2+200*sc,y+(ht-454*sc)/2+(98+53*row)*sc);time.sleep(.45)
def gclick(x,y):
 h,xx,yy,w,ht=geom();gw=min(w,ht*1.5);gh=gw/1.5;mouse(xx+(w-gw)/2+x*gw,yy+(ht-gh)/2+y*gh);time.sleep(.5)
def command(op,**kw):
 token=str(uuid.uuid4());p=DATA/'qa-growth-command.pending';p.write_text(json.dumps(dict(op=op,token=token,**kw)));p.replace(DATA/'qa-growth-command.json');wait(lambda:read(DATA/'qa-growth-command-done.json').get('token')==token,10);time.sleep(.4);return state()
def signature(s):return dict(actors=s['actors'],tiles=sorted((t['x'],t['y'],t['key'],t['fertilized'])for t in s['tiles']))
proc=None
try:
 subprocess.run([str(EXE),'--verify-package'],env=os.environ.copy(),check=True,timeout=60)
 if os.name=='nt':
  d=next((HOME/'versions').glob('0.15-*'))
  for p in Path('mesa/x64').glob('*.dll'):shutil.copy2(p,d/p.name)
  f=d/'touchHLE_default_options.txt';f.write_text(f.read_text()+'\ncom.playforge.ZombieFarm: --gles1=gles1_on_gl2\n')
 proc=subprocess.Popen([str(EXE)],env=os.environ.copy());wait(lambda:geom());time.sleep(12)
 check('one_visible_game_window',geom()[3]>100);check('legacy_farm_is_first_slot',index()['active']=='original');shot('01-main-new-load-menu.png')
 panel(1);shot('02-new-game-confirmation.png');panel(1);check('new_game_cancel_keeps_catalog',len(index()['slots'])==1)
 panel(0);gclick(.5,.55);wait(lambda:(DATA/'qa-growth-state.json').exists(),30);time.sleep(2)
 baseline=signature(state());check('existing_farm_loaded',state()['state']==0);shot('03-existing-farm.png')
 key('F1');panel(0);panel(3);time.sleep(1)
 save=DATA/'touchHLE_sandbox/com.playforge.ZombieFarm/Documents/saveGame.bin2'
 check('save_game_writes_original_serializer',save.exists()and save.stat().st_size>0)
 check('save_creates_backup',any((DATA/'backups').glob('*.zip')));shot('04-save-game-backup.png')
 panel(1);panel(0);wait(lambda:index()['active']=='farm-2',30);wait(lambda:geom());time.sleep(10);shot('05-new-farm-created.png')
 check('new_game_is_separate_profile',len(index()['slots'])==2 and(HOME/'Farms/farm-2').is_dir())
 latest_backup=max((DATA/'backups').glob('*.zip'),key=lambda p:p.stat().st_mtime)
 with zipfile.ZipFile(latest_backup)as z:backed=z.read(next(n for n in z.namelist()if n.endswith('/Documents/saveGame.bin2')))
 check('old_save_not_overwritten_by_new_game',save.read_bytes()==backed)
 newdata=HOME/'Farms/farm-2';check('new_farm_settings_are_fresh',not read(newdata/'settings.json')['sandbox'])
 panel(2);shot('06-load-game-slots.png');panel(0);shot('07-load-confirmation.png');panel(1);check('load_cancel_keeps_current_farm',index()['active']=='farm-2');panel(0);panel(0)
 wait(lambda:index()['active']=='original',30);wait(lambda:geom());time.sleep(10);panel(0);gclick(.5,.55);wait(lambda:(DATA/'qa-growth-state.json').exists());time.sleep(5)
 check('load_restores_original_farm',signature(state())==baseline,{'old':baseline,'new':signature(state())});shot('08-original-farm-restored.png')
 s=command('cooldown');check('army_requirement_not_bypassed',not s['can_invade']if s['army']<s['army_max']*.5 else True,s)
 if s['army']<8:s=command('army',count=8-s['army'])
 check('original_game_zombie_army_created',s['army']>=8,s)
 pre=signature(state());s=command('cooldown')
 check('original_gate_would_wait',not s['original_can_invade'],s)
 check('new_gate_ready_immediately',s['can_invade'],s)
 for i in range(12):
  s=command('cooldown');check('repeat_invasion_timestamp_'+str(i+1),s['can_invade']and not s['original_can_invade'])
 check('removing_wait_does_not_change_tiles',signature(s)['tiles']==pre['tiles']);shot('09-invasions-no-wait.png');command('save')
 key('F1');panel(1)
 if not read(DATA/'settings.json')['sandbox']:panel(0)
 if not read(DATA/'settings.json')['instant_zombies']:panel(3)
 wait(lambda:state()['enabled']);check('instant_growth_retained',not any(t['zombie']and not t['ready']and t['key'].startswith(('soil_seeded_','soil_seedling_','soil_germinating_'))for t in state()['tiles']));shot('10-sandbox-regression.png');key('Escape')
 key('F1');panel(0);panel(3);time.sleep(.8);key('Escape');final=signature(state());close_game();check('clean_launcher_and_runtime_exit',proc.wait(timeout=20)==0);proc=None
 proc=subprocess.Popen([str(EXE)],env=os.environ.copy());wait(lambda:geom());time.sleep(10);check('active_save_persists_after_relaunch',index()['active']=='original');panel(0);gclick(.5,.55);time.sleep(8);check('relaunch_preserves_saved_farm',signature(state())==final);check('instant_setting_persists',read(DATA/'settings.json')['instant_zombies']);shot('11-relaunched-save.png');close_game();check('second_clean_exit',proc.wait(timeout=20)==0);proc=None
except Exception:
 (OUT/'error.txt').write_text(traceback.format_exc())
 try:shot('FAILED.png')
 except Exception:pass
 raise
finally:
 if proc and proc.poll()is None:
  try:close_game();proc.wait(timeout=10)
  except Exception:proc.kill()
 if(DATA/'logs').exists():shutil.copytree(DATA/'logs',OUT/'logs',dirs_exist_ok=True)
 (OUT/'tested-exe-sha256.txt').write_text(hashlib.sha256(EXE.read_bytes()).hexdigest())

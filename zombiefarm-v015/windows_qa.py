"""Real packaged Windows UI and original game state; isolated developer saves only."""
from pathlib import Path
import os,sys,json,time,hashlib,subprocess,zipfile,shutil,base64,zlib,traceback
OUT=Path('output').resolve();OUT.mkdir(exist_ok=True)
H=Path('qa-v015').resolve();EXE=Path('build/Zombie_Farm_Windows_v0.15.exe').resolve()
os.environ.update(ZF_HOME=str(H),ZF_GROWTH_QA='1',ZF_QA_OUT=str(OUT),GALLIUM_DRIVER='llvmpipe',ALSOFT_DRIVERS='null')
with zipfile.ZipFile('build/desktop-source-and-content.zip')as z:z.extractall('desktop')
sys.path.insert(0,str(Path('desktop/tools').resolve()))
import growth_regression as q
q.OUT=OUT
checks=[];proc=None

def record(name,cond,detail=None):
 checks.append(dict(test=name,passed=bool(cond),details=detail));(OUT/'windows-v015-tests.json').write_text(json.dumps(checks,indent=2));print(name,cond,flush=True)
 if not cond:raise AssertionError(name)
def index():return json.loads((H/'farms.json').read_text())
def waitfor(f,seconds=25):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  try:
   v=f()
   if v:return v
  except (OSError,ValueError,AssertionError,RuntimeError,StopIteration):pass
  time.sleep(.2)
 raise AssertionError('wait timed out')
def row(n):q.panel(190,98+53*n);time.sleep(.6)
def shot(n):q.shot(n)
def hashes(data):return{str(p.relative_to(data)):hashlib.sha256(p.read_bytes()).hexdigest()for p in data.rglob('saveGame*')if p.is_file()}
def close():q.u.PostMessageW(q.geom()[0],0x10,0,0)
def start():
 p=subprocess.Popen([str(EXE)],env=os.environ.copy());waitfor(q.geom);time.sleep(12);return p
try:
 result=subprocess.run([str(EXE),'--verify-package'],timeout=45)
 record('complete_package_verifies',result.returncode==0)
 d=next((H/'versions').glob('0.15-*'))
 for f in Path('mesa/x64').glob('*.dll'):shutil.copy2(f,d/f.name)
 # Explicitly test-only driver configuration for every isolated farm in this VM.
 opts=d/'touchHLE_default_options.txt';opts.write_text(opts.read_text()+'\ncom.playforge.ZombieFarm: --gles1=gles1_on_gl2\n')
 encoded=Path('zombiefarm-regression-fixtures/v013-completed-testfarm.b64').read_text()
 fixture=json.loads(zlib.decompress(base64.b64decode(encoded)))
 for name,value in fixture.items():
  p=H/'UserData'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(value))
 proc=start();record('menu_starts_with_existing_farm',index()['active']==1);shot('01-windows-main-menu.png')
 before=hashes(H/'UserData')
 row(2);shot('02-windows-load-game.png');row(4);record('empty_slot_rejected',index()['active']==1 and len(index()['slots'])==1)
 q.panel(200,430);row(1);shot('03-windows-new-game-confirm.png');row(1);record('cancel_keeps_original_save',hashes(H/'UserData')==before)
 row(1);row(0);waitfor(lambda:index()['active']==2);waitfor(q.geom);time.sleep(12);shot('04-windows-new-farm.png')
 record('new_game_has_separate_save_root',(H/'Farms/farm-02/UserData').is_dir() and len(index()['slots'])==2)
 record('new_game_does_not_copy_old_farm',not hashes(H/'Farms/farm-02/UserData'))
 record('original_save_bytes_preserved',hashes(H/'UserData')==before)
 row(2);shot('05-windows-two-farms.png');row(0);waitfor(lambda:index()['active']==1);waitfor(q.geom);time.sleep(12)
 record('load_restores_original_slot',index()['active']==1);shot('06-windows-loaded-original.png')
 row(0);q.game_click(.5,.55);waitfor(lambda:(H/'UserData/qa-growth-state.json').exists());time.sleep(4)
 s=q.state();record('original_farm_running',s['state']==0,{'army':s['army'],'actors':s['actors']});shot('07-windows-original-farm.png')
 dates={str((t['x'],t['y'])):(t['date'],t['plant_date']) for t in s['tiles'] if t['plant']}
 for age in [0,60,3599,7199,7200,86400,-60]:
  now=q.command('invasion',age=age)
  record('cooldown_removed_age_'+str(age),now['invasion_interval']==-7201,now['invasion_interval'])
  record('army_rule_preserved_age_'+str(age),now['invasion_ready']==(now['army']>=now['max_army']/2),{'army':now['army'],'maximum':now['max_army'],'ready':now['invasion_ready']})
 record('crop_dates_not_shifted',{str((t['x'],t['y'])):(t['date'],t['plant_date'])for t in now['tiles']if t['plant']}==dates)
 q.key('F1');row(1);row(3);shot('08-windows-save-game.png');record('save_backup_exists',bool(list((H/'UserData/backups').glob('*.zip'))));q.key('Escape')
 dims=q.geom()[3:];q.key('F10');time.sleep(1);record('fullscreen_still_works',q.geom()[3:]!=dims);q.key('F10');time.sleep(1);record('windowed_size_restored',q.geom()[3:]==dims)
 hwnd=q.geom()[0];q.u.ShowWindow(hwnd,6);r=subprocess.run([str(EXE)],timeout=12);time.sleep(.5);record('reopen_restores_same_game',r.returncode==0 and q.geom()[0]==hwnd and not q.u.IsIconic(hwnd))
 close();record('normal_exit',proc.wait(timeout=15)==0)
 proc=start();record('active_slot_survives_restart',index()['active']==1);shot('09-windows-reloaded-menu.png');close();record('second_exit',proc.wait(timeout=15)==0)
except Exception:
 (OUT/'error.txt').write_text(traceback.format_exc())
 try:shot('FAILED.png')
 except Exception:pass
 raise
finally:
 if proc and proc.poll() is None:
  try:close();proc.wait(timeout=8)
  except Exception:proc.kill()
 for n in ['farms.json','farms.json.previous']:
  if (H/n).exists():shutil.copy2(H/n,OUT/n)
 for slot in [H/'UserData',H/'Farms/farm-02/UserData']:
  if slot.exists():
   dst=OUT/('farm1-evidence' if slot.name=='UserData' and slot.parent==H else 'farm2-evidence');dst.mkdir(exist_ok=True)
   for n in ['settings.json','qa-growth-state.json']:
    if (slot/n).exists():shutil.copy2(slot/n,dst/n)
   if (slot/'logs').exists():shutil.copytree(slot/'logs',dst/'logs',dirs_exist_ok=True)
 (OUT/'tested-executable-sha256.txt').write_text(hashlib.sha256(EXE.read_bytes()).hexdigest()+'  '+EXE.name+'\n')
 (OUT/'test-environment.txt').write_text('Actual packaged Windows EXE on Windows Server 2022. Test-only Mesa software OpenGL and gles1_on_gl2 profile for hosted VM; no driver DLLs are shipped.\n')

"""Production UI and original-game crop/XP/save regression in isolated saves."""
from pathlib import Path
import os,sys,json,subprocess,base64,zlib,time,zipfile,hashlib,traceback,plistlib,shutil
ROOT=Path(os.environ.get('ZF_QA_ROOT','.')).resolve(); BUILD=ROOT/'build';OUT=ROOT/'evidence';OUT.mkdir(exist_ok=True)
HOME=ROOT/'qa-home';DATA=HOME/'UserData';DATA.mkdir(parents=True,exist_ok=True)
os.environ.update(ZF_HOME=str(HOME),ZF_GROWTH_QA='1',ZF_SKIP_START_MENU='1',ZF_QA_OUT=str(OUT),ZF_SOFTWARE_GL='1',GALLIUM_DRIVER='llvmpipe',LP_NUM_THREADS='2',LP_NATIVE_VECTOR_WIDTH='128',ALSOFT_DRIVERS='null')
with zipfile.ZipFile(BUILD/'desktop-source-and-content.zip')as z:z.extractall(ROOT/'desktop')
sys.path.insert(0,str(ROOT/'desktop/tools'))
import growth_regression as q
q.OUT=OUT
exe=BUILD/('Zombie_Farm_Windows_v0.16.exe'if os.name=='nt'else'Zombie_Farm_v0.16_QA')
exe.chmod(0o755)
subprocess.run([str(exe),'--verify-package'],check=True,timeout=60)
fixture=ROOT/'zombiefarm-regression-fixtures/v013-completed-testfarm.b64'
for n,encoded in json.loads(zlib.decompress(base64.b64decode(fixture.read_bytes()))).items():
 assert n.startswith('touchHLE_sandbox/com.playforge.ZombieFarm/')and '..'not in Path(n).parts
 p=DATA/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(encoded))
(DATA/'settings.json').write_text(json.dumps(dict(schema=1,sandbox=False,rate=1,free_shop=False,instant_zombies=False,normalize=False,profile=0,tab_x=.86,tab_y=.28)))
(DATA/'touchHLE_options.txt').write_text('com.playforge.ZombieFarm: --gles1=gles1_on_gl2 --zfr-profile\n')
proc=None

def start():
 global proc
 (DATA/'qa-growth-state.json').unlink(missing_ok=True)
 proc=subprocess.Popen([str(exe)])
 for i in range(60):
  if proc.poll()is not None:raise RuntimeError('Game exit '+str(proc.returncode))
  if (DATA/'qa-growth-state.json').exists():time.sleep(1);return
  time.sleep(1)
  if i>=5 and i%5==0:
   try:q.game_click(.5,.55)
   except Exception:pass
 raise RuntimeError('No original farm telemetry after PLAY')
def stop():
 q.close()
 if os.name=='nt':q.u.PostMessageW(q.geom()[0],0x10,0,0)
 else:
  import qa_input as inp
  from Xlib.protocol import event
  from Xlib import X
  w=inp.window();msg=event.ClientMessage(window=w,client_type=inp.D.intern_atom('WM_PROTOCOLS'),data=(32,[inp.D.intern_atom('WM_DELETE_WINDOW'),X.CurrentTime,0,0,0]));w.send_event(msg);inp.D.flush()
 q.check('clean_exit',proc.wait(timeout=20)==0)
def instant(v):q.toggle('instant_zombies',v)
def fixture(rows):return q.command('fixture',tiles=rows)
def row(p,k,**kw):return dict(x=p[0],y=p[1],key=k,**kw)
try:
 start();q.check('old_save_loaded',q.state()['state']==0);q.shot('01-original-farm.png')
 initial=q.state();xp0=initial['xp'];q.menu();q.panel(190,310);time.sleep(.4);q.check('xp_blocked_with_sandbox_off',q.state()['xp']==xp0)
 q.toggle('sandbox',True);instant(False)
 roots=list(dict.fromkeys(q.coord(t)for t in q.state()['tiles']if t['key'].startswith('soil_')))[:6];q.check('existing_roots_available',len(roots)>=6,roots)
 seedrows=[row(roots[0],'soil_seeded_carrots'),row(roots[1],'soil_seedling_tomatoes'),row(roots[2],'soil_seedling_zombie')]
 fixture(seedrows);q.check('off_keeps_all_three_immature',all(not q.at(q.state(),p)['ready']for p in roots[:3]))
 prior=q.state();instant(True);done=q.wait(lambda s:all(q.at(s,p)['ready']for p in roots[:3]));q.check('existing_plant_crop_zombie_ready',True,[q.at(done,p)for p in roots[:3]])
 q.check('growth_does_not_spawn_or_harvest',done['actors']==prior['actors']and done['xp']==prior['xp']);q.shot('02-all-crops-sandbox.png')
 for n in range(1,6):
  before=q.state();q.panel(180,310);after=q.wait(lambda s:s['xp']==before['xp']+1000)
  q.check('xp_press_'+str(n)+'_adds_exactly_1000',after['xp']-before['xp']==1000,{'before':before['xp'],'after':after['xp'],'level':after['level']})
 q.check('original_level_up_applied',q.state()['level']>initial['level'],{'before':initial['level'],'after':q.state()['level']});q.shot('03-xp-awarded.png')
 props=plistlib.loads((ROOT/'desktop/content/Game/ZombieFarm.app/TileProperties.plist').read_bytes());chains=[]
 for first in sorted(props):
  if not first.startswith('soil_seeded_'):continue
  chain=[first]
  for i in range(8):
   nxt=props.get(chain[-1],{}).get('transformsTo')
   if not nxt or nxt in chain:break
   chain.append(nxt)
   if props.get(nxt,{}).get('canHarvest'):break
  if len(chain) in (3,4) and props.get(chain[-1],{}).get('canHarvest'):chains.append(chain)
 rows=[(stage,c[-1])for c in chains for stage in c[:-1]]
 q.check('all_original_growth_chains_discovered',len(chains)==62 and len(rows)==160,{'varieties':len(chains),'stage_cases':len(rows)})
 for i in range(0,len(rows),6):
  batch=rows[i:i+6];fixture([row(p,k)for p,(k,e)in zip(roots,batch)])
  after=q.wait(lambda s:all(q.at(s,p)['key']==end and q.at(s,p)['ready']for p,(_,end)in zip(roots,batch)))
  q.check('growth_batch_'+str(i//6+1),True,[{'start':k,'end':e}for k,e in batch])
 fixture([row(roots[0],'soil_seeded_tomatoes',age=864000),row(roots[1],'soil_withered_plant'),row(roots[2],'soil_seedling_carrots',fertilized=True)])
 after=q.state();q.check('aged_crop_ready_not_withered',q.at(after,roots[0])['ready']);q.check('withered_crop_not_revived',q.at(after,roots[1])['key']=='soil_withered_plant');q.check('fertilized_crop_harvestable',q.at(after,roots[2])['ready'])
 dates={p:q.at(after,p)['date']for p in (roots[0],roots[2])};time.sleep(1.1);q.check('ready_timestamps_not_repeatedly_reset',all(q.at(q.state(),p)['date']==d for p,d in dates.items()))
 instant(False);fixture([row(roots[0],'soil_seeded_carrots')]);q.check('disable_applies_to_new_crops',not q.at(q.state(),roots[0])['ready'])
 while q.settings()['rate']!=10:q.panel(180,204);time.sleep(.15)
 time.sleep(.5);a=q.state();time.sleep(2);b=q.state();ratio=(b['game_seconds']-a['game_seconds'])/(b['wall_seconds']-a['wall_seconds']);q.check('ten_x_crop_clock_retained',9.8<ratio<10.2,ratio)
 q.check('animation_delta_measured_at_ten_x',b.get('animation_dt',0)>0,b.get('animation_dt'))
 q.panel(180,204);time.sleep(.5);a=q.state();time.sleep(1);b=q.state();ratio=(b['game_seconds']-a['game_seconds'])/(b['wall_seconds']-a['wall_seconds']);q.check('one_x_clock_restored',.9<ratio<1.1,ratio)
 q.toggle('sandbox',False);xp=q.state()['xp'];q.panel(190,310);time.sleep(.4);q.check('xp_master_gate_restored',q.state()['xp']==xp)
 instant(True);time.sleep(.6);q.check('growth_master_gate_restored',not q.at(q.state(),roots[0])['ready']);q.toggle('sandbox',True);q.wait(lambda s:q.at(s,roots[0])['ready'])
 q.command('save');before=q.state();q.shot('04-final-sandbox-state.png');q.close();stop();start();after=q.state()
 q.check('xp_persists_on_reopen',after['xp']==before['xp'],{'before':before['xp'],'after':after['xp']})
 q.check('level_persists_on_reopen',after['level']==before['level']);q.check('growth_setting_persists',q.settings()['instant_zombies']and q.settings()['sandbox']);q.check('mature_crop_persists',q.at(after,roots[0])['ready']);q.check('no_actor_duplication',after['actors']==before['actors']);q.shot('05-reloaded-original-game.png')
 stop()
except Exception:
 try:q.shot('FAILED.png')
 except Exception:pass
 (OUT/'error.txt').write_text(traceback.format_exc());raise
finally:
 if proc and proc.poll()is None:
  try:stop()
  except Exception:proc.kill()
 if (DATA/'logs').exists():shutil.copytree(DATA/'logs',OUT/'logs',dirs_exist_ok=True)
 (OUT/'tested-exe.sha256').write_text(hashlib.sha256(exe.read_bytes()).hexdigest())
 (OUT/'test-settings.json').write_bytes((DATA/'settings.json').read_bytes())

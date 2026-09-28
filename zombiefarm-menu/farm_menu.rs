// Desktop save-menu integration; original guest logic and save serializer retained.
use crate::{Environment, objc::{id, nil, msg, msg_class, ObjC}};
use serde::{Deserialize, Serialize};
use std::{fs, path::PathBuf, sync::{Mutex, atomic::{AtomicBool, AtomicU8, Ordering}}};
#[derive(Clone, Serialize, Deserialize)]
pub struct Slot { pub id: String, pub label: String }
#[derive(Clone, Serialize, Deserialize)]
pub struct Catalog { pub schema: u32, pub active: String, pub slots: Vec<Slot> }
#[derive(Clone, Serialize, Deserialize)]
pub struct Request { pub op: String, pub slot: String, pub from: String }
static INVASION_OVERRIDE: AtomicBool = AtomicBool::new(true);
static PENDING: Mutex<Option<Request>> = Mutex::new(None);
static HAS_PENDING: AtomicBool = AtomicBool::new(false);
static SCENE: AtomicU8 = AtomicU8::new(0);
static BUSY: AtomicBool = AtomicBool::new(false);
pub fn root() -> PathBuf { std::env::var_os("ZF_SAVE_ROOT").map(PathBuf::from).unwrap_or_else(|| crate::desktop_mods::data_dir().parent().unwrap().to_path_buf()) }
pub fn catalog() -> Catalog {
 fs::read(root().join("save-index.json")).ok().and_then(|b| serde_json::from_slice(&b).ok()).unwrap_or(Catalog {schema:1,active:"original".into(),slots:vec![Slot{id:"original".into(),label:"Farm 1".into()}]})
}
pub fn current_label() -> String { let c=catalog(); c.slots.iter().find(|s| s.id==c.active).map(|s|s.label.clone()).unwrap_or("Current farm".into()) }
pub fn queue(op: &str, slot: &str) { let from=catalog().active; *PENDING.lock().unwrap()=Some(Request{op:op.into(),slot:slot.into(),from}); HAS_PENDING.store(true,Ordering::Release); }
pub fn scene(env: &Environment, scene: id) {
 if scene==nil { SCENE.store(0,Ordering::Relaxed); return; }
 let class=ObjC::read_isa(scene,&env.mem); let name=env.objc.try_get_class_name(class).unwrap_or("");
 SCENE.store(if name=="ZFFarmGameScene" {1} else {2},Ordering::Relaxed);
}
fn save_path() -> PathBuf { crate::desktop_mods::data_dir().join("touchHLE_sandbox/com.playforge.ZombieFarm/Documents/saveGame.bin2") }
// Process between main-run-loop iterations, never during scene traversal.
pub fn poll(env: &mut Environment) {
 if env.current_thread!=0 || !HAS_PENDING.load(Ordering::Acquire) || BUSY.swap(true,Ordering::Relaxed) {return;}
 let req=PENDING.lock().unwrap().take(); HAS_PENDING.store(false,Ordering::Release);
 if let Some(req)=req {let regs=*env.cpu.regs();let result=apply(env,&req);env.cpu.regs_mut().copy_from_slice(&regs);if let Err(e)=result {crate::desktop_mods::menu_message(&e);}}
 BUSY.store(false,Ordering::Relaxed);
}
fn apply(env: &mut Environment, req: &Request) -> Result<(),String> {
 if SCENE.load(Ordering::Relaxed)==2 {return Err("Return to your own farm before saving or switching.".into());}
 if SCENE.load(Ordering::Relaxed)==1 {
  let state:id=msg_class![env; GameState gameState];let mode:i32=msg![env; state state];
  if mode!=0 {return Err("Return to your own farm before switching saves.".into());}
  let _:()=msg![env; state saveGame];
  if fs::metadata(save_path()).map(|m|m.len()==0).unwrap_or(true) {return Err("Save was not written; your farm has not been switched.".into());}
 } else if req.op=="save" {return Err("Enter your farm with PLAY before saving.".into());}
 crate::desktop_mods::shutdown();crate::desktop_mods::backup_saves()?;
 if req.op=="save" {crate::desktop_mods::menu_message("Farm saved. A recovery backup was also created.");return Ok(());}
 if req.op!="new" && req.op!="load" {return Err("Unknown save action; no files were changed.".into());}
 crate::desktop_mods::atomic(&root().join("save-switch.json"),&serde_json::to_vec(req).map_err(|e|e.to_string())?)?;
 std::process::exit(42)
}
pub fn override_message(env:&mut Environment, receiver:id, selector:&str) -> bool {
 if !INVASION_OVERRIDE.load(Ordering::Relaxed) || std::env::var_os("ZF_DESKTOP").is_none() || env.bundle.bundle_identifier()!="com.playforge.ZombieFarm" || selector!="lastInvasionDate" {return false;}
 let class=ObjC::read_isa(receiver,&env.mem);if env.objc.try_get_class_name(class)!=Some("GameData") {return false;}
 // The original countdown label calculates timeIntervalSinceDate directly.
 // Returning nil would let canInvade pass but display a spurious two-hour timer.
 // An autoreleased distant-past date clears BOTH original code paths without
 // changing global clocks, hunger, crops, enemy selection, or army requirements.
 let regs=*env.cpu.regs();
 let date:id=msg_class![env; NSDate distantPast];
 env.cpu.regs_mut().copy_from_slice(&regs);
 env.cpu.regs_mut()[0]=date.to_bits();true
}
// Test the real original canInvade method rather than duplicating its formula.
pub fn raw_can_invade(env:&mut Environment,state:id)->bool {
 INVASION_OVERRIDE.store(false,Ordering::Relaxed);let result:bool=msg![env; state canInvade];INVASION_OVERRIDE.store(true,Ordering::Relaxed);
 if std::env::var_os("ZF_GROWTH_QA").is_some() {
  let data:id=msg![env; state gameData];
  let date:id=msg![env; data lastInvasionDate];
  let now:id=msg_class![env; NSDate date];
  let elapsed:f64=msg![env; now timeIntervalSinceDate:date];
  let report=serde_json::json!({"effective_date_is_nil":date==nil,"seconds_since_last_invasion":elapsed,"original_two_hour_wait_remaining":(7200.0-elapsed).max(0.0)});
  if let Ok(b)=serde_json::to_vec(&report) {let _=crate::desktop_mods::atomic(&crate::desktop_mods::data_dir().join("qa-invasion-timer.json"),&b);}
 }
 result
}
#[cfg(test)] mod tests {
 use super::*;
 #[test] fn request_roundtrip(){let r=Request{op:"load".into(),slot:"farm-2".into(),from:"original".into()};let b=serde_json::to_vec(&r).unwrap();let r:Request=serde_json::from_slice(&b).unwrap();assert_eq!(r.slot,"farm-2");}
 #[test] fn catalog_roundtrip(){let c=Catalog{schema:1,active:"original".into(),slots:vec![Slot{id:"original".into(),label:"Farm 1".into()}]};let b=serde_json::to_vec(&c).unwrap();let c:Catalog=serde_json::from_slice(&b).unwrap();assert_eq!(c.slots.len(),1);}
}

from pathlib import Path
import zipfile,json,hashlib,shutil
root=Path('engine')
with zipfile.ZipFile('baseline/runtime-source.zip') as z:
 for n in z.namelist():
  if n.startswith('src/'):
   p=root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(n))
p=root/'src/desktop_mods.rs';s=p.read_text()
def edit(old,new):
 global s
 assert s.count(old)==1,(old,s.count(old));s=s.replace(old,new)
edit('    pub free_shop: bool,','    pub free_shop: bool,\n    pub instant_zombies: bool,')
edit('            free_shop: false,','            free_shop: false,\n            instant_zombies: false,')
edit('        "free" => {','''        "instant" => {
            if !s.settings.instant_zombies {
                if let Err(e) = backup_saves() {
                    s.message = format!("Backup failed: {e}");
                    return;
                }
            }
            s.settings.instant_zombies = !s.settings.instant_zombies;
            s.message = if s.settings.instant_zombies && s.settings.sandbox {
                "Growing planted zombies now. Harvest them normally."
            } else if s.settings.instant_zombies {
                "Enable Sandbox to activate instant zombie growth."
            } else { "Instant growth OFF. Grown zombies stay grown." }.into();
        }
        "free" => {''')
edit('1 => vec!["toggle", "free", "rate", "report"],','1 => vec!["toggle", "free", "rate", "instant", "report"],')
edit('            ("Live game clock".into(), format!("{}x", s.settings.rate)),','            ("Live game clock".into(), format!("{}x", s.settings.rate)),\n            ("Instant zombie growth".into(), b(s.settings.instant_zombies)),')
s=s.replace('0.12','0.14').replace('Shop changes need a restart. F10: fullscreen.','Instant growth: zombies only; manual harvest.').replace('("Sandbox".into(), "Clock & shop".into())','("Sandbox".into(), "Growth, clock & shop".into())')
s+='''
pub fn instant_zombies_enabled() -> bool {
    let s = state().lock().unwrap();
    s.settings.sandbox && s.settings.instant_zombies
}
pub fn growth_completed(count: usize) {
    let mut s = state().lock().unwrap();
    s.message = format!("{} planted zombie(s) grown. Tap to harvest.", count);
}
'''
p.write_text(s,encoding='utf-8')
g=Path('zombiefarm-growth/zombie_growth.rs').read_text()
g=g.replace("fn class_name(env: &Environment, receiver: id) -> Option<&'static str>","fn class_name<'a>(env: &'a Environment, receiver: id) -> Option<&'a str>")
g=g.replace('env.objc.read_isa(&env.mem, receiver)','crate::objc::ObjC::read_isa(receiver, &env.mem)')
g=g.replace('tiles.push(json!({"key":k,"x":point.x,"y":point.y,','let px = point.x; let py = point.y;\n            tiles.push(json!({"key":k,"x":px,"y":py,')
g=g.replace('selector != "tick:"','selector != "drawScene"')
g=g.replace('if class_name(env, receiver) != Some("ZFFarmTileMap") { return; }','if !matches!(class_name(env, receiver), Some("CCDirector" | "CCDisplayLinkDirector" | "CCThreadedFastDirector" | "CCFastDirector" | "CCTimerDirector")) { return; }')
g=g.replace('    tick(env, qa);','    let scene: id = msg![env; receiver runningScene];\n    if class_name(env, scene) == Some("ZFFarmGameScene") { tick(env, qa); }')
g=g.replace('original farm tick boundary','original farm frame boundary').replace('Called before the original tick.','Called before the original scene update and rendering.')
# The original setKey path can omit cached flags for terminal special zombies.
# Repair only metadata on already-mature original tiles, never grow with toggle off.
g=g.replace('    if !crate::desktop_mods::instant_zombies_enabled() && !qa { return; }','')
g=g.replace('    let _guard = Guard;','''    let _guard = Guard;
    static LAST_FRAME: OnceLock<Mutex<Instant>> = OnceLock::new();
    let mut last = LAST_FRAME.get_or_init(|| Mutex::new(Instant::now() - Duration::from_secs(1))).lock().unwrap();
    if last.elapsed() < Duration::from_millis(100) { return; }
    *last = Instant::now(); drop(last);''')
g=g.replace('if state_code == 0 && crate::desktop_mods::instant_zombies_enabled() {','if state_code == 0 {')
g=g.replace('                let zombie: bool = msg![env; tile isZombie];','                let tile_key = key(env, tile);\n                terminal::repair(env, tile, &tile_key);\n                let zombie: bool = msg![env; tile isZombie];')
g=g.replace('if !eligible(&key(env, tile), zombie, ready) { continue; }','if !crate::desktop_mods::instant_zombies_enabled() || !eligible(&key(env, tile), zombie, ready) { continue; }')
g=g.replace('        let _: () = msg![env; after setDate:now];','        let _: () = msg![env; after setDate:now];\n        let after_key = key(env, after);\n        terminal::repair(env, after, &after_key);')
g+='\nmod terminal {\n'+Path('zombiefarm-growthfix/terminal.rs').read_text()+'\n}\n'
(root/'src/zombie_growth.rs').write_text(g,encoding='utf-8')
p=root/'src/lib.rs';s=p.read_text();assert s.count('pub mod desktop_mods;')==1;p.write_text(s.replace('pub mod desktop_mods;','pub mod desktop_mods;\nmod zombie_growth;'))
p=root/'src/objc/messages.rs';s=p.read_text();a='    maybe_initialize_class(env, receiver);';assert s.count(a)==1
p.write_text(s.replace(a,a+'\n    crate::zombie_growth::before_message(env, receiver, selector_name);'))
print('Instant zombie growth integrated; original game executable and resources untouched')

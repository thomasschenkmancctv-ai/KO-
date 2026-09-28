from pathlib import Path
import zipfile,json,hashlib,shutil
root=Path('engine')
# The v0.13 distribution deliberately preserves the v0.12 core runtime. Restore
# its exact reviewed source snapshot before adding this one feature.
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
s=s.replace('0.12','0.14')
s=s.replace('Shop changes need a restart. F10: fullscreen.','Instant growth: zombies only; manual harvest.')
s=s.replace('("Sandbox".into(), "Clock & shop".into())','("Sandbox".into(), "Growth, clock & shop".into())')
s+='''
/// Effective toggle, shared with the original-farm tick hook.
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
(root/'src/zombie_growth.rs').write_text(g,encoding='utf-8')
p=root/'src/lib.rs';s=p.read_text();assert s.count('pub mod desktop_mods;')==1;p.write_text(s.replace('pub mod desktop_mods;','pub mod desktop_mods;\nmod zombie_growth;'))
p=root/'src/objc/messages.rs';s=p.read_text();a='    maybe_initialize_class(env, receiver);';assert s.count(a)==1
p.write_text(s.replace(a,a+'\n    crate::zombie_growth::before_message(env, receiver, selector_name);'))
print('Instant zombie growth integrated; original game executable and resources untouched')

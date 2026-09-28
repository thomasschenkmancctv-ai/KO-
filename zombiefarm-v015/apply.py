from pathlib import Path
import shutil
root=Path('engine');desktop=Path('desktop')
def patch(path,old,new,count=1):
 p=root/path;s=p.read_text();assert s.count(old)==count,(path,old,s.count(old));p.write_text(s.replace(old,new,count))
p=root/'src/desktop_mods.rs';s=p.read_text().replace('0.14','0.15')
s=s.replace('fn atomic(', 'pub(crate) fn atomic(').replace('fn backup_saves()', 'pub(crate) fn backup_saves()')
s=s.replace('            open: false,\n            page: 0,','            open: std::env::var_os("ZF_START_MENU").is_some(),\n            page: if std::env::var_os("ZF_START_MENU").is_some() { 6 } else { 0 },')
s=s.replace('        "sandbox" => s.page = 1,','''        "games" => s.page = 6,
        "newgame" => s.page = 8,
        "loadgame" => s.page = 7,
        "create" => { crate::game_sessions::request("new"); s.message="Saving current farm before creating a new one...".into(); },
        "savegame" => { crate::game_sessions::request("save"); },
        "load1" | "load2" | "load3" | "load4" | "load5" => {crate::game_sessions::request(action);},
        "sandbox" => s.page = 1,''')
s=s.replace('        "back" => s.page = 0,','        "back" => s.page = if s.page >= 7 {6} else {0},')
s=s.replace('        1 => vec!["toggle",','''        6 => vec!["close", "newgame", "loadgame", "savegame"],
        7 => vec!["load1", "load2", "load3", "load4", "load5"],
        8 => vec!["create", "games"],
        1 => vec!["toggle",''')
s=s.replace('vec!["sandbox", "graphics", "display", "audit", "close"]','vec!["sandbox", "games", "graphics", "display", "audit"]')
s=s.replace('    match s.page {\n        1 => vec![','''    match s.page {
        6 => vec![("Continue".into(),crate::game_sessions::active_name()),("New Game".into(),"Separate farm".into()),("Load Game".into(),"Choose a farm".into()),("Save Game".into(),"Save + backup".into())],
        7 => crate::game_sessions::rows(),
        8 => vec![("Create New Farm".into(),"Keep current farm".into()),("Cancel".into(),"Go back".into())],
        1 => vec![''')
s=s.replace('("Graphics".into(), "Original artwork".into()),\n            ("Screen fit"', '("Game saves".into(), "New Game / Load Game".into()),\n            ("Graphics".into(), "Original artwork".into()),\n            ("Screen fit"')
s=s.replace('            ("Return to farm".into(), "".into()),','')
s=s.replace('["Farm settings","Sandbox","Graphics","Screen fit","Crop inspector","Crop preview"][s.page.min(5)as usize]','["Farm settings","Sandbox","Graphics","Screen fit","Crop inspector","Crop preview","Zombie Farm","Load Game","New Game"][s.page.min(8)as usize]')
s=s.replace('match s.page{1=>format!', 'match s.page{6=>"Each farm has its own save, settings and clock.\\nInvasion cooldown removed. No timer or voucher.\\nYour army requirements and battle rules stay intact.".into(),7=>"Choose a saved farm. Empty slots cannot be loaded.\\nYour current farm is saved before switching.\\nThe game reopens with the selected farm.".into(),8=>"A new farm will use the next empty save slot.\\nYour current farm is saved, backed up and kept.\\nNothing is erased. Up to five independent farms.".into(),1=>format!')
s+='''
pub fn session_message(message: &str) { state().lock().unwrap().message=message.into(); }
pub fn persist_session() -> Result<(),String> { persist(&mut state().lock().unwrap()) }
'''
p.write_text(s)
(root/'src/game_sessions.rs').write_text(Path('zombiefarm-v015/game_sessions.rs').read_text())
patch('src/lib.rs','mod zombie_growth;','mod zombie_growth;\nmod game_sessions;')
patch('src/frameworks/uikit.rs','    // NSRunLoop will never call this function in headless mode.','    if crate::game_sessions::process(env) { ui_application::exit(env); }\n\n    // NSRunLoop will never call this function in headless mode.')
p=root/'src/objc/messages/zombie_farm.rs';s=p.read_text()
s=s.replace('fn zombie_farm_record_last_invasion_date(','''fn zombie_farm_invasion_app(env: &Environment) -> bool {
    zombie_farm_is_exact_legacy_app(env) || (
        std::env::var_os("ZF_DESKTOP").is_some()
        && env.bundle.bundle_identifier()=="com.playforge.ZombieFarm"
        && env.bundle.bundle_version()=="1.17")
}

fn zombie_farm_record_last_invasion_date(''')
s=s.replace('|| !zombie_farm_is_exact_legacy_app(env)\n        || selector_name != "lastInvasionDate"','|| !zombie_farm_invasion_app(env)\n        || selector_name != "lastInvasionDate"')
a=s.index('fn zombie_farm_override_invasion_cooldown_interval(');b=s.index('\nfn ',a+4)
s=s[:a]+s[a:b].replace('!zombie_farm_is_exact_legacy_app(env)','!zombie_farm_invasion_app(env)')+s[b:]
s=s.replace('if zombie_farm_is_exact_legacy_app(env)\n        && zombie_farm_no_invasion_cooldown_enabled()', 'if zombie_farm_invasion_app(env)\n        && zombie_farm_no_invasion_cooldown_enabled()')
s=s.replace('(zombie_farm_is_exact_legacy_app(env)\n                && zombie_farm_no_invasion_cooldown_enabled()', '(zombie_farm_invasion_app(env)\n                && zombie_farm_no_invasion_cooldown_enabled()')
p.write_text(s)
p=root/'src/zombie_growth.rs';s=p.read_text();anchor='    if op == "save" {'
addition='''    if op == "invasion" && state_code == 0 {
        let age=command["age"].as_f64().unwrap_or(0.).clamp(-86400.,86400.*30.);
        let date:id=msg_class![env; NSDate dateWithTimeIntervalSinceNow:(-age)];
        let _:()=msg![env; data setLastInvasionDate:date];
    }
'''
assert s.count(anchor)==1;s=s.replace(anchor,addition+anchor)
anchor='fn qa_report(env: &mut Environment, _state: id, data: id, state_code: i32, changed: usize) {'
s=s.replace(anchor,anchor+'\n    let army:i32=msg![env; _state curArmySize];\n    let max_army:i32=msg![env; _state maxArmySize];\n    let invasion_ready:bool=msg![env; _state canInvade];\n    let invasion_date:id=msg![env; data lastInvasionDate];\n    let invasion_interval:f64=if invasion_date==nil {0.} else {msg![env; invasion_date timeIntervalSinceNow]};')
s=s.replace('"state":state_code,','"state":state_code,"army":army,"max_army":max_army,"invasion_ready":invasion_ready,"invasion_interval":invasion_interval,')
p.write_text(s)
(desktop/'runtime').mkdir(exist_ok=True)
for n in ['desktop_mods.rs','game_sessions.rs','zombie_growth.rs']:shutil.copy2(root/'src'/n,desktop/'runtime'/n)
# Retain the verified Windows process flags and window recovery implementation.
p=desktop/'launcher/main.go';s=p.read_text().replace('0.14','0.15')
a=s.index('\tdata := filepath.Join(root, "UserData")');b=s.index('\n\treturn nil\n}',a);old=s[a:b]
new='''\tfarms, e := readFarms(root)
\tif e != nil { return e }
\tif _, err := os.Stat(filepath.Join(root,"switch-request.json")); err == nil { os.Rename(filepath.Join(root,"switch-request.json"),filepath.Join(root,"switch-request.stale")) }
\tfor {
\tdata, e := farmData(root, farms.Active)
\tif e != nil { return e }
'''+old[old.index('\tif e = os.MkdirAll(data'):]+'''
\tlog.Close()
\tvar again bool
\tfarms, again, e = consumeSwitch(root, farms)
\tif e != nil { return e }
\tif !again { break }
\t}
'''
new=new.replace('defer log.Close()','')
new=new.replace('cmd.Env = append(os.Environ(), "ZF_DESKTOP=1",','cmd.Env = append(os.Environ(), "ZF_DESKTOP=1", "ZF_START_MENU=1", "ZF_HOME="+root, "TOUCHHLE_ZOMBIE_FARM_NO_INVASION_COOLDOWN=1",')
s=s[:a]+new+s[b:];p.write_text(s)
for n in ['sessions.go','sessions_test.go']:shutil.copy2(Path('zombiefarm-v015')/n,desktop/'launcher'/n)
p=desktop/'tools/package.py';p.write_text(p.read_text().replace('0.14','0.15'))
print('v0.15 integration applied; original game binary and assets untouched')

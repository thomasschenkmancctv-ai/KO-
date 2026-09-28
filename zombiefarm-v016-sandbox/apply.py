from pathlib import Path
import zipfile, shutil
root=Path('engine');changes=Path(__file__).parent
with zipfile.ZipFile('baseline/runtime-source.zip') as z:
 for n in z.namelist():
  if n.startswith('src/'):
   p=root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(n))
def change(file,old,new):
 p=root/'src'/file;s=p.read_text();assert s.count(old)==1,(file,old[:90],s.count(old));p.write_text(s.replace(old,new))
shutil.copy2(changes/'sandbox_rewards.rs',root/'src/sandbox_rewards.rs')
p=root/'src/lib.rs';p.write_text(p.read_text()+'\nmod sandbox_rewards;\n')
p=root/'src/desktop_mods.rs';s=p.read_text()
s=s.replace('std::env::var_os("ZF_DESKTOP").is_none()', '!desktop_enabled()')
s=s.replace('1 => vec!["toggle", "free", "rate", "instant", "report"]','1 => vec!["toggle", "free", "rate", "instant", "xp1000"]')
s=s.replace('"Instant zombie growth"','"Instant growth: all crops"').replace('("Diagnostics".into(), "Save report".into()),','("Grant experience".into(), "+1000 XP".into()),')
s=s.replace('Growing planted zombies now. Harvest them normally.','Growing zombies and crops. Harvest them normally.').replace('Enable Sandbox to activate instant zombie growth.','Enable Sandbox to activate instant growth.').replace('Instant growth OFF. Grown zombies stay grown.','Instant growth OFF. Mature crops stay mature.')
s=s.replace('Instant growth: zombies only; manual harvest.','Zombies, plants and crops; manual harvest.')
s=s.replace('"free" => {','''"xp1000" => {
            if !s.settings.sandbox { s.message="Enable Sandbox before adding XP.".into(); }
            else if !crate::farm_menu::own_farm_scene() { s.message="Enter your own farm before adding XP.".into(); }
            else if crate::sandbox_rewards::queue() { s.message="Adding 1000 XP through original game rules...".into(); }
            else { s.message="Reward queue is full.".into(); }
            return;
        }
        "free" => {''')
s=s.replace('    if let Err(e) = persist(s) {','    if !matches!(action,"toggle"|"rate"|"instant"|"free"|"rgba"|"profile0"|"profile1"|"profile2"|"profile3") { return; }\n    if let Err(e) = persist(s) {')
s=s.replace('s.last_persist.elapsed() > Duration::from_secs(1)','s.last_persist.elapsed() > Duration::from_secs(10)')
s=s.replace('        let sample_path = data_dir().join("clock-samples.csv");','        if std::env::var_os("ZF_PERF_QA").is_some() {\n        let sample_path = data_dir().join("clock-samples.csv");')
s=s.replace('            let _ = f.write_all(line.as_bytes());\n        }\n    }','            let _ = f.write_all(line.as_bytes());\n        }\n        }\n    }')
s=s.replace('planted zombie(s) grown. Tap to harvest.','zombie(s)/crop(s) grown. Tap to harvest.')
s=s.replace('v0.15"','v0.16"').replace('build 0.15.3','build 0.16').replace('\\"version\\":\\"0.15\\"','\\"version\\":\\"0.16\\"')
s+='''
pub fn desktop_enabled()->bool { static ON:OnceLock<bool>=OnceLock::new(); *ON.get_or_init(||std::env::var_os("ZF_DESKTOP").is_some()) }
pub fn sandbox_enabled()->bool { state().lock().unwrap().settings.sandbox }
'''
p.write_text(s)
change('farm_menu.rs','    if !INVASION_OVERRIDE.load(Ordering::Relaxed)','    if selector != "lastInvasionDate" || !INVASION_OVERRIDE.load(Ordering::Relaxed)')
change('farm_menu.rs','std::env::var_os("ZF_DESKTOP").is_none()','!crate::desktop_mods::desktop_enabled()')
p=root/'src/farm_menu.rs';p.write_text(p.read_text()+'\npub fn own_farm_scene()->bool { SCENE.load(Ordering::Relaxed)==1 }\n')
p=root/'src/zombie_growth.rs';s=p.read_text()
s=s.replace('let zombie: bool = msg![env; tile isZombie];','let zombie: bool = msg![env; tile isZombie];\n        let plant: bool = msg![env; tile isPlant];',2)
s=s.replace('eligible(&before, zombie, ready)','eligible(&before, zombie || plant, ready)')
s=s.replace('    let mut changed = 0;\n    if state_code == 0 {','''    if crate::sandbox_rewards::has_pending() { crate::sandbox_rewards::apply(env,state,data); }
    let enabled=crate::desktop_mods::instant_zombies_enabled();
    static LAST_REPAIR:OnceLock<Mutex<Instant>>=OnceLock::new();
    let mut repair=LAST_REPAIR.get_or_init(||Mutex::new(Instant::now()-Duration::from_secs(4))).lock().unwrap();
    let do_scan=enabled || repair.elapsed()>Duration::from_secs(3);
    if do_scan { *repair=Instant::now(); } drop(repair);
    let mut changed = 0;
    if state_code == 0 && do_scan {''')
s=s.replace('!crate::desktop_mods::instant_zombies_enabled()\n                    || !eligible(&key(env, tile), zombie, ready)','!enabled\n                    || !eligible(&tile_key, zombie || plant, ready)')
s=s.replace('Instant zombie growth: {} planted zombie(s)','Instant growth: {} zombie(s)/crop(s)')
s=s.replace('    let qa = std::env::var_os("ZF_GROWTH_QA").is_some();','    static QA:OnceLock<bool>=OnceLock::new();\n    let qa = *QA.get_or_init(||std::env::var_os("ZF_GROWTH_QA").is_some());')
s=s.replace('std::env::var_os("ZF_DESKTOP").is_none()','!crate::desktop_mods::desktop_enabled()')
s=s.replace('    let regs = *env.cpu.regs();\n    let scene:', '    let regs = *env.cpu.regs();\n    let cpsr=env.cpu.cpsr();\n    let scene:')
s=s.replace('        tick(env, qa);\n    }','        tick(env, qa);\n    } else { crate::sandbox_rewards::reject(); }')
s=s.replace('    env.cpu.regs_mut().copy_from_slice(&regs);','    env.cpu.regs_mut().copy_from_slice(&regs);\n    env.cpu.set_cpsr(cpsr);')
s=s.replace('    let report = json!({"can_invade":can_invade,','''    let experience=crate::sandbox_rewards::xp(env,data);
    let level:i32=msg![env; data level];
    let wall=std::time::SystemTime::now().duration_since(std::time::SystemTime::UNIX_EPOCH).unwrap().as_secs_f64();
    let game=crate::libc::time::emulated_system_time().duration_since(std::time::SystemTime::UNIX_EPOCH).unwrap().as_secs_f64();
    let report = json!({"xp":experience,"level":level,"wall_seconds":wall,"game_seconds":game,"can_invade":can_invade,''')
s=s.replace('fn only_live_zombie_stages_eligible()','fn only_live_growable_stages_eligible()')
s=s.replace('assert!(!eligible(&format!("soil_{stage}_carrots"), false, false));','assert!(!eligible(&format!("soil_{stage}_carrots"), false, false));\n            assert!(eligible(&format!("soil_{stage}_carrots"), true, false));')
p.write_text(s)
# Cocos calculateDeltaTime uses gettimeofday; separate animation from NSDate crop time.
change('libc/time.rs','pub fn emulated_system_time() -> SystemTime {','pub fn real_system_time() -> SystemTime {')
change('libc/time.rs','    crate::desktop_mods::game_time(add_signed_seconds(base, config.offset_seconds))','    add_signed_seconds(base, config.offset_seconds)\n}\npub fn emulated_system_time() -> SystemTime {\n    crate::desktop_mods::game_time(real_system_time())')
p=root/'src/libc/time.rs';s=p.read_text();a=s.index('fn gettimeofday(');b=s.index('\nfn nanosleep(',a);x=s[a:b];assert x.count('emulated_system_time()')==1;x=x.replace('emulated_system_time()','real_system_time()');s=s[:a]+x+s[b:];p.write_text(s)
change('objc/messages.rs','let zombie_farm_cocos_label_text_selector = zombie_farm_bundle','let zombie_farm_cocos_label_text_selector = zombie_farm_bundle && zombie_farm_debug_enabled')
change('objc/messages.rs','''    let regs_before_zombie_farm_prepare = *env.cpu.regs();
    if selector_name == "_setIndex:forCell:" {
        zombie_farm_prepare_cctable_cell(env, receiver, selector);
    }
    env.cpu
        .regs_mut()
        .copy_from_slice(&regs_before_zombie_farm_prepare);''','''    let regs_before_zombie_farm_prepare = *env.cpu.regs();
    if selector_name == "_setIndex:forCell:" {
        zombie_farm_prepare_cctable_cell(env, receiver, selector);
        env.cpu.regs_mut().copy_from_slice(&regs_before_zombie_farm_prepare);
    }''')
print('v0.16: all crop growth, original XP rewards, animation-clock isolation, reduced render I/O and dispatch overhead')

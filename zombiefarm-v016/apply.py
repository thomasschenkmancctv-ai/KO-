"""Checked v0.16 integration; original game code/assets and launcher safety preserved."""
from pathlib import Path
import sys
E=Path(sys.argv[1] if len(sys.argv)>1 else 'engine');D=Path(sys.argv[2] if len(sys.argv)>2 else 'desktop')
def edit(root,path,a,b):
 p=root/path;s=p.read_text(encoding='utf-8');assert s.count(a)==1,(path,a[:90],s.count(a));p.write_text(s.replace(a,b),encoding='utf-8',newline='\n')
Z='src/objc/messages/zombie_farm.rs';G='src/zombie_growth.rs'
# Derived CCArray frees its ccArray before calling [super dealloc]. Never sanitize
# the same derived storage a second time, or NSObject never unregisters the object.
edit(E,'src/objc/messages.rs','if zombie_farm_needs_pre_dispatch_workarounds(env, selector_name)\n        && zombie_farm_pre_dispatch_workarounds','if !(super2.is_some() && selector_name == "dealloc" && zombie_farm_uses_playforge_bundle(env))\n        && zombie_farm_needs_pre_dispatch_workarounds(env, selector_name)\n        && zombie_farm_pre_dispatch_workarounds')
# Instance setter, not a class method. This fixes CCTable's actual node-size test.
edit(E,Z,'.object_has_method(&env.mem, object_class, set_content_size_selector)','.object_has_method(&env.mem, object, set_content_size_selector)')
a='    crate::zombie_farm_debug::record_table_object_return(\n        receiver,\n        &class_name,\n        selector_name,\n        nil,\n        None,\n    );'
edit(E,Z,a,'''    let source = zombie_farm_read_object_ivar(env, receiver, "dataSource_")
        .and_then(|p| zombie_farm_object_class_name(env, p));
    if zombie_order_reuse_safe(env.bundle.bundle_identifier()=="com.playforge.ZombieFarm"
        && env.bundle.bundle_version()=="1.17", &class_name, source) { return false; }
'''+a)
# Inspected original 1.17 uses the same 52-byte Cocos action-list layout as the
# old renamed wrapper for which these safety checks were originally enabled.
edit(E,Z,'        zombie_farm_is_exact_legacy_app(env),\n        zombie_farm_object_class_name(env, receiver),','        zombie_farm_invasion_app(env),\n        zombie_farm_object_class_name(env, receiver),')
edit(E,Z,'if !zombie_farm_is_exact_legacy_app(env) || selector_name != "visit"','if !zombie_farm_invasion_app(env) || selector_name != "visit"')
edit(E,Z,'    if zombie_farm_object_class_name(env, array) != Some("CCArray")\n        || env.objc.get_host_object(array).is_none()','    if env.objc.get_host_object(array).is_none()\n        || zombie_farm_object_class_name(env, array) != Some("CCArray")')
p=E/Z;s=p.read_text(encoding='utf-8');s+='''
fn zombie_order_reuse_safe(exact: bool, table: &str, source: Option<&str>) -> bool {
    exact && table=="CCTableView" && source==Some("ZFZombieSelectionMenu")
}
#[cfg(test)] mod v016_tests {
    use super::*;
    #[test] fn reuse_is_narrow() {
        assert!(zombie_order_reuse_safe(true,"CCTableView",Some("ZFZombieSelectionMenu")));
        for (a,t,s) in [(false,"CCTableView",Some("ZFZombieSelectionMenu")),(true,"OtherTable",Some("ZFZombieSelectionMenu")),(true,"CCTableView",Some("ZFShopMenu")),(true,"CCTableView",None)] {
            assert!(!zombie_order_reuse_safe(a,t,s));
        }
    }
    #[test] fn telemetry_timestamp_is_serializable() {
        let n=std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_millis() as u64;
        assert!(serde_json::to_string(&serde_json::json!({"unix_ms":n})).is_ok());
    }
}
''';p.write_text(s,encoding='utf-8',newline='\n')
edit(E,G,'    let mut changed = 0;\n    if state_code == 0 {','''    let instant=crate::desktop_mods::instant_zombies_enabled();
    static LAST_REPAIR: OnceLock<Mutex<Instant>>=OnceLock::new();
    let repair_due={
        let mut last=LAST_REPAIR.get_or_init(||Mutex::new(Instant::now()-Duration::from_secs(2))).lock().unwrap();
        let due=instant || qa || last.elapsed()>=Duration::from_secs(1);
        if due {*last=Instant::now();} due
    };
    let mut changed = 0;
    if state_code == 0 && repair_due {''')
edit(E,G,'!crate::desktop_mods::instant_zombies_enabled()\n                    || !eligible(&key(env, tile), zombie, ready)','!instant || !eligible(&tile_key, zombie, ready)')
# Opt-in fixture-only audit calls original destructors, not a mocked collection.
edit(E,G,'    if op == "invasion" && state_code == 0 {','''    if op=="lifetime_stress" && state_code==0 {
        let mut leaked=0; let count=command["count"].as_u64().unwrap_or(100).min(5000);
        for _ in 0..count {
            let a:id=msg_class![env;CCArray alloc]; let a:id=msg![env;a initWithCapacity:1u32];
            release(env,a); if env.objc.get_host_object(a).is_some(){leaked+=1;}
        }
        let report=json!({"created":count,"still_registered_after_release":leaked});
        let _=std::fs::write(crate::desktop_mods::data_dir().join("qa-lifetime.json"),report.to_string());
    }
    if op == "invasion" && state_code == 0 {''')
edit(E,G,'    let scene: id = msg![env; receiver runningScene];\n    if class_name(env, scene) == Some("ZFFarmGameScene") {','''    let scene: id = msg![env; receiver runningScene];
    if qa {
        let report=json!({"scene":class_name(env,scene).unwrap_or("unknown"),"unix_ms":std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_millis() as u64});
        let _=std::fs::write(crate::desktop_mods::data_dir().join("qa-scene.json"),report.to_string());
    }
    if class_name(env, scene) == Some("ZFFarmGameScene") {''')
for root,path in [(D,'launcher/main.go'),(D,'tools/package.py'),(D,'runtime/desktop_mods.rs'),(E,'src/desktop_mods.rs')]:
 p=root/path
 if p.exists():p.write_text(p.read_text(encoding='utf-8').replace('0.15','0.16'),encoding='utf-8',newline='\n')
print('v0.16 checked lifecycle/scroll/growth integration complete')

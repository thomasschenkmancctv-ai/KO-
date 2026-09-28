"""v0.16 checked integration against the complete v0.15 source snapshot."""
from pathlib import Path
import sys
engine=Path(sys.argv[1] if len(sys.argv)>1 else 'engine')
desktop=Path(sys.argv[2] if len(sys.argv)>2 else 'desktop')
def edit(root,path,old,new,count=1):
 p=root/path;s=p.read_text(encoding='utf-8');assert s.count(old)==count,(path,old[:100],s.count(old));p.write_text(s.replace(old,new),encoding='utf-8',newline='\n')
# Super dealloc runs after the derived object has already freed its storage.
edit(engine,'src/objc/messages.rs',
 'if zombie_farm_needs_pre_dispatch_workarounds(env, selector_name)\n        && zombie_farm_pre_dispatch_workarounds',
 'if !(super2.is_some() && selector_name == "dealloc" && zombie_farm_uses_playforge_bundle(env))\n        && zombie_farm_needs_pre_dispatch_workarounds(env, selector_name)\n        && zombie_farm_pre_dispatch_workarounds')
edit(engine,'src/objc/messages/zombie_farm.rs',
 '.object_has_method(&env.mem, object_class, set_content_size_selector)',
 '.object_has_method(&env.mem, object, set_content_size_selector)')
edit(engine,'src/objc/messages/zombie_farm.rs',
 '    crate::zombie_farm_debug::record_table_object_return(\n        receiver,\n        &class_name,\n        selector_name,\n        nil,\n        None,\n    );',
 '''    let data_source = zombie_farm_read_object_ivar(env, receiver, "dataSource")
        .and_then(|source| zombie_farm_object_class_name(env, source));
    if zombie_order_reuse_safe(
        env.bundle.bundle_identifier() == "com.playforge.ZombieFarm"
            && env.bundle.bundle_version() == "1.17",
        &class_name, data_source,
    ) {
        // Native dequeueCell retains/autoreleases the evicted cell, and
        // table:cellAtIndex: rebinds its zombie, label, place and cellLayer.
        return false;
    }
    crate::zombie_farm_debug::record_table_object_return(
        receiver, &class_name, selector_name, nil, None,
    );''')
# Extend the original checked 52-byte Cocos layout guard to preserved 1.17 ID.
edit(engine,'src/objc/messages/zombie_farm.rs',
 '        zombie_farm_is_exact_legacy_app(env),\n        zombie_farm_object_class_name(env, receiver),',
 '        zombie_farm_invasion_app(env),\n        zombie_farm_object_class_name(env, receiver),')
edit(engine,'src/objc/messages/zombie_farm.rs',
 'if !zombie_farm_is_exact_legacy_app(env) || selector_name != "visit"',
 'if !zombie_farm_invasion_app(env) || selector_name != "visit"')
edit(engine,'src/objc/messages/zombie_farm.rs',
 '    if zombie_farm_object_class_name(env, array) != Some("CCArray")\n        || env.objc.get_host_object(array).is_none()',
 '    if env.objc.get_host_object(array).is_none()\n        || zombie_farm_object_class_name(env, array) != Some("CCArray")')
p=engine/'src/objc/messages/zombie_farm.rs';s=p.read_text(encoding='utf-8');s+='''
fn zombie_order_reuse_safe(exact_app: bool, table: &str, source: Option<&str>) -> bool {
    exact_app && table == "CCTableView" && source == Some("ZFZombieSelectionMenu")
}
#[cfg(test)]
mod v016_tests {
    use super::*;
    #[test] fn reuse_is_narrow() {
        assert!(zombie_order_reuse_safe(true, "CCTableView", Some("ZFZombieSelectionMenu")));
        for (a,t,s) in [(false,"CCTableView",Some("ZFZombieSelectionMenu")),
            (true,"OtherTableView",Some("ZFZombieSelectionMenu")),
            (true,"CCTableView",Some("ZFShopMenu")),(true,"CCTableView",None)] {
            assert!(!zombie_order_reuse_safe(a,t,s));
        }
    }
}
''';p.write_text(s,encoding='utf-8',newline='\n')
edit(engine,'src/zombie_growth.rs','    let mut changed = 0;\n    if state_code == 0 {',
 '''    let instant = crate::desktop_mods::instant_zombies_enabled();
    static LAST_REPAIR: OnceLock<Mutex<Instant>> = OnceLock::new();
    let repair_due = {
        let mut last = LAST_REPAIR.get_or_init(|| Mutex::new(Instant::now()-Duration::from_secs(2))).lock().unwrap();
        let due = instant || qa || last.elapsed() >= Duration::from_secs(1);
        if due { *last = Instant::now(); }
        due
    };
    let mut changed = 0;
    if state_code == 0 && repair_due {''')
edit(engine,'src/zombie_growth.rs',
 '!crate::desktop_mods::instant_zombies_enabled()\n                    || !eligible(&key(env, tile), zombie, ready)',
 '!instant || !eligible(&tile_key, zombie, ready)')
edit(engine,'src/zombie_growth.rs','    if op == "invasion" && state_code == 0 {',
 '''    if op == "lifetime_stress" && state_code == 0 {
        let mut leaked = 0;
        let count = command["count"].as_u64().unwrap_or(100).min(5000);
        for _ in 0..count {
            let array: id = msg_class![env; CCArray alloc];
            let array: id = msg![env; array initWithCapacity:1u32];
            release(env, array);
            if env.objc.get_host_object(array).is_some() { leaked += 1; }
        }
        let report = json!({"created":count,"still_registered_after_release":leaked});
        let _ = std::fs::write(crate::desktop_mods::data_dir().join("qa-lifetime.json"), report.to_string());
    }
    if op == "invasion" && state_code == 0 {''')
edit(engine,'src/zombie_growth.rs',
 '    let scene: id = msg![env; receiver runningScene];\n    if class_name(env, scene) == Some("ZFFarmGameScene") {',
 '''    let scene: id = msg![env; receiver runningScene];
    if qa {
        let scene_name = class_name(env, scene).unwrap_or("unknown");
        let report = json!({"scene":scene_name,"unix_ms":std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_millis()});
        let _ = std::fs::write(crate::desktop_mods::data_dir().join("qa-scene.json"), report.to_string());
    }
    if class_name(env, scene) == Some("ZFFarmGameScene") {''')
for path in ['launcher/main.go','tools/package.py','runtime/desktop_mods.rs']:
 p=desktop/path
 if p.exists():p.write_text(p.read_text(encoding='utf-8').replace('0.15','0.16'),encoding='utf-8',newline='\n')
p=engine/'src/desktop_mods.rs';p.write_text(p.read_text(encoding='utf-8').replace('0.15','0.16'),encoding='utf-8',newline='\n')
print('v0.16 lifecycle, scene cleanup, scoped table reuse and growth polling integrated')

from pathlib import Path
p=Path('engine/src/zombie_growth.rs');s=p.read_text()
s=s.replace('HashMap<String, f64>','HashMap<String, (f64, bool)>')
s=s.replace('                    || !unit.starts_with("ZombieActor")','')
s=s.replace('zombies.insert(name.to_owned(), duration);','zombies.insert(name.to_owned(), (duration, unit.starts_with("ZombieActor")));')
s=s.replace('let Some(duration) = catalog().get(key)', 'let Some((duration, is_zombie)) = catalog().get(key)')
s=s.replace('        if ready && zombie {','        let plant: bool = msg![env; tile isPlant];\n        if ready && zombie == *is_zombie && plant != *is_zombie {')
s=s.replace('byte(env, tile, "isZombie", 1);','byte(env, tile, "isZombie", u8::from(*is_zombie));')
s=s.replace('byte(env, tile, "isPlant", 0);','byte(env, tile, "isPlant", u8::from(!*is_zombie));')
s=s.replace('These terminal zombies must still be recognized as harvestable.','Terminal plants and zombies must retain correct type and harvest flags.')
a='    let experience=crate::sandbox_rewards::xp(env,data);'
b='''    let director:id=msg_class![env; CCDirector sharedDirector];
    let animation_dt=env.objc.object_lookup_ivar(&env.mem,director,&"dt".to_owned()).map(|p| {let value:f32=env.mem.read(p.cast());value});
'''+a
assert s.count(a)==1;s=s.replace(a,b)
s=s.replace('json!({"xp":experience,','json!({"animation_dt":animation_dt,"xp":experience,')
p.write_text(s)
import runpy
runpy.run_path(str(Path(__file__).with_name('input_fix.py')))
p=Path('engine/src/sandbox_rewards.rs');p.write_text(p.read_text().replace('mod input_regression_tests','mod tests_input'))
p=Path('engine/src/frameworks/uikit/ui_application.rs');s=p.read_text()
a='- (bool)openURL:(id)url { // NSURL'
b='''// The preserved offline app probes iOS companion apps and store links on reload.
// There is no iOS application registry in this runtime. Report unavailable;
// never crash, launch a browser, or exit merely to answer a capability query.
- (bool)canOpenURL:(id)_url {
    false
}

'''+a
assert s.count(a)==1;s=s.replace(a,b);p.write_text(s)
print('Crop flags, animation telemetry, bounded mouse queue and offline URL probe integrated')

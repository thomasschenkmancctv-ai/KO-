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
    let animation_dt=env.objc.object_lookup_ivar(&env.mem,director,&"dt".to_owned()).map(|p|env.mem.read::<f32>(p.cast()));
'''+a
assert s.count(a)==1;s=s.replace(a,b)
s=s.replace('json!({"xp":experience,','json!({"animation_dt":animation_dt,"xp":experience,')
p.write_text(s)
print('Terminal plant harvest flags and read-only animation delta telemetry integrated')

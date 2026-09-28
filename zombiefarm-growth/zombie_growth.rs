// Zombie Farm desktop extension, MPL-2.0.
// Run only at the original farm tick boundary, never inside rendering or a save decoder.
use crate::{Environment, msg, msg_class};
use crate::objc::{id, nil, retain, release};
use crate::frameworks::core_graphics::CGPoint;
use crate::frameworks::foundation::{ns_date, ns_string, NSUInteger};
use std::sync::{OnceLock, Mutex, atomic::{AtomicBool, Ordering}};
use std::time::{Instant, Duration};
use serde_json::{json, Value};
static BUSY: AtomicBool = AtomicBool::new(false);
struct Guard;
impl Drop for Guard { fn drop(&mut self) { BUSY.store(false, Ordering::Relaxed); } }

pub fn eligible(key: &str, zombie: bool, harvestable: bool) -> bool {
    zombie && !harvestable && ["soil_seeded_", "soil_germinating_", "soil_seedling_"].iter().any(|p| key.starts_with(p))
}
fn key(env: &mut Environment, tile: id) -> String {
    let k: id = msg![env; tile key];
    if k == nil { String::new() } else { ns_string::to_rust_string(env, k).to_string() }
}
fn tile_at(env: &mut Environment, point: CGPoint) -> (id, id) {
    let sprite: id = msg_class![env; TSprite findByCoordinates:point];
    let tile: id = if sprite == nil { nil } else { msg![env; sprite tile] };
    (sprite, tile)
}
fn mature(env: &mut Environment, manager: id, point: CGPoint) -> bool {
    let mut changed = false;
    // There are three normal pre-harvest stages. The cap also protects future content.
    for _ in 0..8 {
        let (sprite, tile) = tile_at(env, point);
        if tile == nil { break; }
        let zombie: bool = msg![env; tile isZombie];
        let ready: bool = msg![env; tile isHarvestable];
        let before = key(env, tile);
        if !eligible(&before, zombie, ready) { break; }
        // Use the game's own replacement, cache refresh, endCropTile and fertilizer handling.
        let _: () = msg![env; manager graduateSoilTileWithTSprite:sprite];
        let (_, after) = tile_at(env, point);
        if after == nil || key(env, after) == before { break; }
        // Graduation normally carries elapsed time forward. Instant growth must not
        // carry an old timer into the wither stage, nor advance the global clock.
        let now: id = msg_class![env; NSDate date];
        let _: () = msg![env; after setDate:now];
        changed = true;
    }
    changed
}
fn sprites(env: &mut Environment) -> id {
    let all: id = msg_class![env; TSprite allMySprites];
    if all == nil { return nil; }
    let copy: id = msg_class![env; NSArray arrayWithArray:all];
    retain(env, copy)
}
fn class_name(env: &Environment, receiver: id) -> Option<&'static str> {
    if receiver == nil { return None; }
    let class = env.objc.read_isa(&env.mem, receiver);
    env.objc.try_get_class_name(class)
}

/// Called before the original tick. All guest registers are restored afterwards.
pub fn before_message(env: &mut Environment, receiver: id, selector: &str) {
    if selector != "tick:" || std::env::var_os("ZF_DESKTOP").is_none() { return; }
    let qa = std::env::var_os("ZF_GROWTH_QA").is_some();
    if !crate::desktop_mods::instant_zombies_enabled() && !qa { return; }
    if class_name(env, receiver) != Some("ZFFarmTileMap") { return; }
    if BUSY.swap(true, Ordering::Relaxed) { return; }
    let _guard = Guard;
    let regs = *env.cpu.regs();
    tick(env, qa);
    env.cpu.regs_mut().copy_from_slice(&regs);
}
fn tick(env: &mut Environment, qa: bool) {
    let state: id = msg_class![env; GameState gameState];
    if state == nil { return; }
    let data: id = msg![env; state zfGameData];
    if data == nil { return; }
    let state_code: i32 = msg![env; state state];
    let manager: id = msg_class![env; ZFTileManager tileManager];
    if manager == nil { return; }
    // The original tick itself checks state == 0 for the player's own farm.
    // Do not mutate visited farms or combat/other scenes.
    if qa { qa_command(env, state, data, manager, state_code); }
    let mut changed = 0;
    if state_code == 0 && crate::desktop_mods::instant_zombies_enabled() {
        let list = sprites(env);
        if list != nil {
            let count: NSUInteger = msg![env; list count];
            for i in 0..count.min(4096) {
                let sprite: id = msg![env; list objectAtIndex:i];
                let tile: id = msg![env; sprite tile];
                if tile == nil { continue; }
                let zombie: bool = msg![env; tile isZombie];
                let ready: bool = msg![env; tile isHarvestable];
                if !eligible(&key(env, tile), zombie, ready) { continue; }
                let point: CGPoint = msg![env; tile rootTile];
                if mature(env, manager, point) { changed += 1; }
            }
            release(env, list);
        }
    }
    if changed > 0 {
        crate::desktop_mods::growth_completed(changed);
        log!("Instant zombie growth: {} planted zombie(s) advanced on local farm; global clock unchanged", changed);
    }
    if qa { qa_report(env, state, data, state_code, changed); }
}

// Opt-in test fixture interface. Inert in normal play; never consumes user saves.
// Tests stage real original-game tiles, then click the production sandbox toggle.
fn qa_command(env: &mut Environment, state: id, data: id, manager: id, state_code: i32) {
    let path = crate::desktop_mods::data_dir().join("qa-growth-command.json");
    let Ok(bytes) = std::fs::read(&path) else { return; };
    let Ok(command) = serde_json::from_slice::<Value>(&bytes) else { return; };
    let _ = std::fs::remove_file(path);
    let op = command["op"].as_str().unwrap_or("");
    if op == "save" { let _: () = msg![env; state saveGame]; }
    if op == "fixture" && state_code == 0 {
        if let Some(rows) = command["tiles"].as_array() {
            for row in rows.iter().take(128) {
                let point = CGPoint { x: row["x"].as_f64().unwrap_or(0.) as f32, y: row["y"].as_f64().unwrap_or(0.) as f32 };
                let name = row["key"].as_str().unwrap_or("");
                if !name.starts_with("soil_") || !point.x.is_finite() || !point.y.is_finite() { continue; }
                let props: id = msg![env; manager tilePropertiesDictionary];
                let name = ns_string::from_rust_string(env, name.to_string());
                let prop: id = msg![env; props objectForKey:name];
                if prop == nil { continue; }
                let _: () = msg![env; manager replaceTile:point withGIDkey:name considerNeighbouringTiles:false];
                let (_, tile) = tile_at(env, point);
                if tile != nil {
                    let age = row["age"].as_f64().unwrap_or(0.).clamp(0., 86400. * 30.);
                    let date: id = msg_class![env; NSDate dateWithTimeIntervalSinceNow:(-age)];
                    let _: () = msg![env; tile setDate:date];
                    let _: () = msg![env; tile setPlantDate:date];
                    if row["fertilized"].as_bool().unwrap_or(false) { let _: () = msg![env; manager fertilizeTile:point]; }
                }
            }
        }
    }
    // QA may request a save only. Sandbox settings are always driven via the real UI.
    let _ = data;
    let _ = std::fs::write(crate::desktop_mods::data_dir().join("qa-growth-command-done.json"), &bytes);
}
fn qa_report(env: &mut Environment, _state: id, data: id, state_code: i32, changed: usize) {
    static LAST: OnceLock<Mutex<Instant>> = OnceLock::new();
    let mut last = LAST.get_or_init(|| Mutex::new(Instant::now() - Duration::from_secs(1))).lock().unwrap();
    if changed == 0 && last.elapsed() < Duration::from_millis(300) { return; }
    *last = Instant::now(); drop(last);
    let list = sprites(env);
    let mut tiles = Vec::new();
    if list != nil {
        let count: NSUInteger = msg![env; list count];
        for i in 0..count.min(4096) {
            let sprite: id = msg![env; list objectAtIndex:i];
            let tile: id = msg![env; sprite tile];
            if tile == nil { continue; }
            let k = key(env, tile);
            let zombie: bool = msg![env; tile isZombie];
            let plant: bool = msg![env; tile isPlant];
            let ready: bool = msg![env; tile isHarvestable];
            let fertilized: bool = msg![env; tile fertilized];
            let point: CGPoint = msg![env; tile rootTile];
            let date: id = msg![env; tile date];
            let plant_date: id = msg![env; tile plantDate];
            let end: id = msg![env; tile endCropTile];
            let end_key = if end == nil { String::new() } else { ns_string::to_rust_string(env, end).to_string() };
            let grow_time: f64 = msg![env; tile growTime];
            tiles.push(json!({"key":k,"x":point.x,"y":point.y,"zombie":zombie,"plant":plant,"ready":ready,"fertilized":fertilized,"date":ns_date::debug_time_interval(env,date),"plant_date":ns_date::debug_time_interval(env,plant_date),"grow_time":grow_time,"end_crop":end_key}));
        }
        release(env, list);
    }
    let actors: id = msg![env; data actorList];
    let actor_count: NSUInteger = if actors == nil { 0 } else { msg![env; actors count] };
    let report=json!({"schema":1,"state":state_code,"enabled":crate::desktop_mods::instant_zombies_enabled(),"changed":changed,"actors":actor_count,"tiles":tiles});
    let dir=crate::desktop_mods::data_dir();
    if let Ok(bytes)=serde_json::to_vec_pretty(&report) {
        let tmp=dir.join("qa-growth-state.pending");
        if std::fs::write(&tmp,bytes).is_ok() { let _=std::fs::rename(tmp,dir.join("qa-growth-state.json")); }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn only_live_zombie_stages_eligible() {
        for stage in ["seeded", "germinating", "seedling"] {
            assert!(eligible(&format!("soil_{stage}_zombie"),true,false));
            assert!(eligible(&format!("soil_{stage}_zombrute"),true,false));
            assert!(!eligible(&format!("soil_{stage}_carrots"),false,false));
            assert!(!eligible(&format!("soil_{stage}_zombie"),true,true));
        }
    }
    #[test] fn never_withers_revives_or_reharvests() {
        for key in ["soil_harvestable_zombie","soil_withered_zombie","soil_plowed","zombieCombiner","", "soil_seeded_fake"] {
            assert!(!eligible(key,false,false));
        }
        assert!(!eligible("soil_harvestable_zombie",true,true));
        assert!(!eligible("soil_withered_zombie",true,false));
    }
}

// MPL-2.0. Derive terminal-stage cache repair from the original, unmodified
// content. Some original SaveTile::setKey paths return early when transformsTo
// is absent. These terminal zombies must still be recognized as harvestable.
use crate::{Environment, msg};
use crate::objc::{id, nil};
use crate::frameworks::foundation::ns_string;
use std::collections::HashMap;
use std::sync::OnceLock;

fn catalog() -> &'static HashMap<String, f64> {
    static CATALOG: OnceLock<HashMap<String, f64>> = OnceLock::new();
    CATALOG.get_or_init(|| {
        let mut result = HashMap::new();
        let Ok(market) = plist::Value::from_file("Game/ZombieFarm.app/Market.plist") else { return result; };
        let Ok(tiles) = plist::Value::from_file("Game/ZombieFarm.app/TileProperties.plist") else { return result; };
        let Some(rows) = market.as_array() else { return result; };
        let Some(props) = tiles.as_dictionary() else { return result; };
        let mut zombies = HashMap::new();
        for row in rows {
            let Some(row) = row.as_dictionary() else { continue; };
            let name = row.get("name").and_then(|v| v.as_string());
            let unit = row.get("unitKey").and_then(|v| v.as_string()).unwrap_or("");
            if row.get("category").and_then(|v| v.as_string()) != Some("crop") || !unit.starts_with("ZombieActor") { continue; }
            let duration = row.get("growTime").and_then(|v| v.as_real().or_else(|| v.as_signed_integer().map(|n| n as f64)).or_else(|| v.as_unsigned_integer().map(|n| n as f64)));
            if let (Some(name), Some(duration)) = (name, duration) {
                if duration.is_finite() && duration > 0. { zombies.insert(name.to_owned(), duration); }
            }
        }
        for (key, prop) in props {
            if !key.starts_with("soil_harvestable_") { continue; }
            let Some(prop) = prop.as_dictionary() else { continue; };
            if prop.get("canHarvest").and_then(|v| v.as_boolean()) != Some(true) || prop.contains_key("transformsTo") { continue; }
            if let Some(duration) = prop.get("name").and_then(|v|v.as_string()).and_then(|name|zombies.get(name)) { result.insert(key.clone(), *duration); }
        }
        result
    })
}
fn byte(env: &mut Environment, tile: id, field: &str, value: u8) {
    if let Some(ptr) = env.objc.object_lookup_ivar(&env.mem, tile, &field.to_owned()) { env.mem.write(ptr.cast(), value); }
}
pub(super) fn repair(env: &mut Environment, tile: id, key: &str) {
    let Some(duration) = catalog().get(key) else { return; };
    let ready: bool = msg![env; tile isHarvestable];
    let zombie: bool = msg![env; tile isZombie];
    if ready && zombie { return; }
    byte(env,tile,"isZombie",1);
    byte(env,tile,"isPlant",0);
    byte(env,tile,"isHarvestable",1);
    byte(env,tile,"ignoreWitherRule",1);
    // There is intentionally no next transformation for these original tiles.
    byte(env,tile,"isTransformable",0);
    if let Some(ptr) = env.objc.object_lookup_ivar(&env.mem,tile,&"growTime".to_owned()) { env.mem.write(ptr.cast(), *duration); }
    let end: id = msg![env; tile endCropTile];
    if end == nil {
        let name = ns_string::from_rust_string(env,key.to_owned());
        let _: () = msg![env; tile setEndCropTile:name];
    }
}

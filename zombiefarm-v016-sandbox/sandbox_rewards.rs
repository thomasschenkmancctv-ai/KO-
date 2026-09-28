// MPL-2.0. Sandbox rewards use original resource and level-up code.
use crate::{Environment, msg, msg_class, objc::{id, nil}};
use std::sync::atomic::{AtomicU32, Ordering};
static REQUESTS: AtomicU32 = AtomicU32::new(0);
pub fn queue() -> bool {
    REQUESTS.fetch_update(Ordering::AcqRel, Ordering::Relaxed, |n| n.checked_add(1)).is_ok()
}
pub fn has_pending() -> bool { REQUESTS.load(Ordering::Relaxed) != 0 }
pub fn reject() {
    if REQUESTS.swap(0, Ordering::AcqRel) > 0 { crate::desktop_mods::menu_message("Enter your own farm before granting XP."); }
}
pub fn xp(env: &mut Environment, data: id) -> Option<i32> {
    let resources: id = msg![env; data resources];
    if resources == nil { return None; }
    let count: u32 = msg![env; resources count];
    if count < 3 { return None; }
    let number: id = msg![env; resources objectAtIndex:2u32];
    Some(msg![env; number intValue])
}
pub fn apply(env: &mut Environment, state: id, data: id) {
    let requests=REQUESTS.swap(0, Ordering::AcqRel);
    if requests==0 { return; }
    let mode:i32=msg![env; state state];
    if mode!=0 || !crate::desktop_mods::sandbox_enabled() {
        crate::desktop_mods::menu_message("XP not granted: enable Sandbox on your own farm."); return;
    }
    let Some(before)=xp(env,data) else { crate::desktop_mods::menu_message("XP data unavailable; no reward was applied."); return; };
    let Some(amount)=requests.checked_mul(1000).and_then(|n| i32::try_from(n).ok()).filter(|n| before.checked_add(*n).is_some()) else {
        crate::desktop_mods::menu_message("XP limit reached; no overflowing reward was applied.");return;
    };
    // Resource index 2 is XP in the preserved GameState::addResource:amount:.
    // This method performs the game's own multi-level threshold loop and UI updates.
    let _:()=msg![env; state addResource:2i32 amount:amount];
    let after=xp(env,data).unwrap_or(before);
    let level:i32=msg![env; data level];
    let _:()=msg![env; state saveGame];
    crate::desktop_mods::shutdown();
    crate::desktop_mods::menu_message(&format!("+{} XP granted. Total: {}. Level: {}.",after-before,after,level));
    log!("Sandbox XP: {} press(es), {} -> {}, level {}",requests,before,after,level);
}
#[cfg(test)] mod tests {
 #[test] fn checked_rewards(){for n in [1u32,3,20,100]{assert_eq!(n.checked_mul(1000).unwrap(),n*1000);}assert!(i32::MAX.checked_add(1000).is_none());}
}

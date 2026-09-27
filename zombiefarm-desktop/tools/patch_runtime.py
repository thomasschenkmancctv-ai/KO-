#!/usr/bin/env python3
"""Bounded desktop hooks; fail closed when the pinned runtime changes."""
from pathlib import Path
import shutil, sys
ROOT=Path(sys.argv[1] if len(sys.argv)>1 else 'engine')
MOD=Path(__file__).resolve().parents[1]/'runtime/desktop_mods.rs'
def replace(path,old,new,count=1):
    p=ROOT/path
    text=p.read_text()
    actual=text.count(old)
    if actual!=count:
        raise RuntimeError(f'{path}: expected {count} anchors, found {actual}')
    p.write_text(text.replace(old,new,count))
shutil.copy2(MOD,ROOT/'src/desktop_mods.rs')
replace('src/desktop_mods.rs','match key{Keycode::F1','match *key{Keycode::F1')
replace('src/desktop_mods.rs','set_size(dims.0,dims.1);}}}return true}},','set_size(dims.0,dims.1);}}}}return true}},')
replace('src/desktop_mods.rs','gl::Vertex2f(cx+r*angle.cos(),cy+r*angle.sin());}gl::End();','gl::Vertex2f(cx+r*angle.cos(),cy+r*angle.sin());}gl::Vertex2f(x,y+r);gl::End();')
replace('src/desktop_mods.rs','gl::BindTexture(gl::TEXTURE_2D,tex);gl::Color4f(1.,1.,1.,1.);let sc=size/f.size;','gl::BindTexture(gl::TEXTURE_2D,tex);if light{gl::Color4f(1.,1.,1.,1.);}else{gl::Color4f(0.20,0.14,0.08,1.);}let sc=size/f.size;')
replace('src/desktop_mods.rs','let(w,h)=window.size();let mut s=state().lock().unwrap();','let mut s=state().lock().unwrap();static CONFIGURED:OnceLock<()>=OnceLock::new();if CONFIGURED.set(()).is_ok(){let _=window.set_title("Zombie Farm - Desktop v0.12");let dims=match s.settings.profile{1=>(1100,506),2=>(900,720),3=>(1160,426),_=>(960,640)};let _=window.set_size(dims.0,dims.1);}let(w,h)=window.size();')
replace('src/desktop_mods.rs','let line=format!("{:.6},{:.6},{:.0}\\n",unix(),s.clock.value(),s.clock.rate);','let sample_path=data_dir().join("clock-samples.csv");if fs::metadata(&sample_path).map(|m|m.len()>1048576).unwrap_or(false){let _=fs::remove_file(data_dir().join("clock-samples.previous.csv"));let _=fs::rename(&sample_path,data_dir().join("clock-samples.previous.csv"));}let line=format!("{:.6},{:.6},{:.0}\\n",unix(),s.clock.value(),s.clock.rate);')
replace('src/lib.rs','mod paths;','mod paths;\npub mod desktop_mods;')
replace('src/bin.rs','    touchHLE::main(std::env::args())','    touchHLE::desktop_mods::prepare()?;\n    let result = touchHLE::main(std::env::args());\n    touchHLE::desktop_mods::shutdown();\n    result')
replace('src/libc/time.rs','    add_signed_seconds(base, config.offset_seconds)','    crate::desktop_mods::game_time(add_signed_seconds(base, config.offset_seconds))')
replace('src/paths.rs',"pub fn user_data_base_path() -> Cow<'static, Path> {", "pub fn user_data_base_path() -> Cow<'static, Path> {\n    if std::env::var_os(\"ZF_DESKTOP\").is_some() { return Cow::Owned(crate::desktop_mods::data_dir()); }")
replace('src/window.rs','            // Virtual accelerometer','            if crate::desktop_mods::event(&event, &mut self.window) { continue; }\n\n            // Virtual accelerometer')
replace('src/window.rs','    pub fn swap_window(&self) {\n        self.window.gl_swap_window();','    pub fn swap_window(&self) {\n        crate::desktop_mods::draw(&self.window);\n        self.window.gl_swap_window();')
replace('src/window.rs','.position_centered()\n                .opengl()', '.position_centered()\n                .resizable()\n                .opengl()')
replace('src/window.rs','        if !self.fullscreen && !Self::rotatable_fullscreen() {\n            return (0, 0, app_width, app_height);','        if !self.fullscreen && !Self::rotatable_fullscreen() && std::env::var_os("ZF_DESKTOP").is_none() {\n            return (0, 0, app_width, app_height);')
print('Desktop extension integration applied; guest binary untouched')

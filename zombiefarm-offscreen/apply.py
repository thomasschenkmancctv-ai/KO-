from pathlib import Path
import zipfile,shutil
root=Path('engine')
with zipfile.ZipFile('baseline/runtime-source.zip')as z:
 for n in z.namelist():
  if n.startswith('src/'):
   p=root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(n))
shutil.copy2('zombiefarm-offscreen/software_gl.rs',root/'src/software_gl.rs')
p=root/'src/lib.rs';s=p.read_text();assert 'mod software_gl;' not in s;s+='\nmod software_gl;\n';p.write_text(s)
p=root/'src/window.rs';s=p.read_text()
a='pub struct GLContext(sdl2::video::GLContext);'
b='''pub enum GLContext { Native(sdl2::video::GLContext), Software(crate::software_gl::Context) }
impl GLContext {
    pub fn bind(&self, window: &sdl2::video::Window) {
        match self {
            Self::Native(ctx) => window.gl_make_current(ctx).unwrap(),
            Self::Software(ctx) => ctx.bind().expect("Off-screen context bind"),
        }
    }
}'''
assert s.count(a)==1;s=s.replace(a,b)
s=s.replace('self.0.is_current()','match self { Self::Native(ctx) => ctx.is_current(), Self::Software(ctx) => ctx.is_current() }')
s=s.replace('let mut window = if Self::rotatable_fullscreen() {','''let mut window = if crate::software_gl::enabled() {
            sdl2::hint::set("SDL_FRAMEBUFFER_ACCELERATION", "0");
            let (width,height)=size_for_orientation(device_family,device_orientation,scale_hack);
            let mut builder=video_ctx.window(title,width,height);
            builder.position_centered().resizable();
            if fullscreen { builder.fullscreen_desktop(); }
            builder.build().expect("Software presentation window")
        } else if Self::rotatable_fullscreen() {''')
a='    pub fn create_gl_context(&self, version: GLVersion) -> Result<GLContext, String> {'
s=s.replace(a,a+'''
        if crate::software_gl::enabled() {
            return match version {
                GLVersion::GL21Compat => crate::software_gl::Context::new(&self.window).map(GLContext::Software),
                GLVersion::GLES11 => Err("Off-screen backend uses GLES1-on-GL2 translation".into()),
            };
        }''')
s=s.replace('Ok(GLContext(gl_ctx))','Ok(GLContext::Native(gl_ctx))')
s=s.replace('self.window.gl_make_current(&gl_ctx.0).unwrap()','gl_ctx.bind(&self.window)')
s=s.replace('self.video_ctx.gl_get_proc_address(procname) as *const _','crate::software_gl::proc_address(&self.video_ctx, procname)')
s=s.replace('self.video_ctx.gl_get_proc_address(s) as *const _','crate::software_gl::proc_address(&self.video_ctx, s)')
a='    pub fn set_share_with_current_context(&self, value: bool) {'
s=s.replace(a,a+'\n        if crate::software_gl::enabled() { crate::software_gl::set_share(value); return; }')
s=s.replace('self.window.gl_swap_window();','crate::software_gl::present(&self.window).expect("Frame presentation failed");')
s=s.replace('window.window.drawable_size()','crate::software_gl::drawable_size(&window.window)')
s=s.replace('self.window.drawable_size()','crate::software_gl::drawable_size(&self.window)')
assert 'gl_ctx.0' not in s;p.write_text(s)
p=root/'src/desktop_mods.rs';s=p.read_text();s=s.replace('window.drawable_size()','crate::software_gl::drawable_size(window)');s=s.replace('sdl2_sys::SDL_GL_GetCurrentContext()as usize','crate::software_gl::current_id()');s=s.replace('sdl2_sys::SDL_GL_GetCurrentContext() as usize','crate::software_gl::current_id()');s=s.replace('Windows desktop build 0.15','Windows/Whisky build 0.15.3');p.write_text(s)
print('Only context creation and frame presentation changed. Original game/runtime mechanics preserved.')

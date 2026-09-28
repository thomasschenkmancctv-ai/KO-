/* MPL-2.0. Zombie Farm compatibility backend. Original GLES/game unchanged. */
//! OSMesa renders the original GL stream to memory; SDL presents the pixels.
//! No WGL/EGL host context, GL window flag, registry patch, or system driver.
use std::{cell::{Cell, RefCell}, ffi::{c_void, CString}, ptr, sync::OnceLock};
use sdl2::video::Window;
use sdl2_sys as s;
type Handle = *mut c_void;
type Create = unsafe extern "system" fn(u32, i32, i32, i32, Handle) -> Handle;
type Destroy = unsafe extern "system" fn(Handle);
type Make = unsafe extern "system" fn(Handle, Handle, u32, i32, i32) -> u8;
type Current = unsafe extern "system" fn() -> Handle;
type GetProc = unsafe extern "system" fn(*const i8) -> Handle;
type Store = unsafe extern "system" fn(i32, i32);
type Color = unsafe extern "system" fn(Handle, *mut i32, *mut i32, *mut i32, *mut Handle) -> u8;
type Finish = unsafe extern "system" fn();
struct Api { library: usize, create: Create, destroy: Destroy, make: Make, current: Current, proc: GetProc, store: Store, color: Color, finish: Finish }
static API: OnceLock<Result<Api, String>> = OnceLock::new();
thread_local! { static SHARE: Cell<bool> = const { Cell::new(false) }; }
pub fn enabled() -> bool { static MODE: OnceLock<bool> = OnceLock::new(); *MODE.get_or_init(|| cfg!(target_os="windows") && std::env::var("ZF_SOFTWARE_GL").map(|v| v=="1").unwrap_or(false)) }
fn api() -> Result<&'static Api, String> {
    API.get_or_init(|| {
        let path = std::env::current_exe().map_err(|e|e.to_string())?.parent().ok_or("Missing runtime directory")?.join("compat/osmesa.dll");
        let path = CString::new(path.to_string_lossy().as_bytes()).map_err(|e|e.to_string())?;
        let library = unsafe { s::SDL_LoadObject(path.as_ptr()) };
        if library.is_null() { return Err(format!("Off-screen graphics DLL: {}",sdl2::get_error())); }
        macro_rules! symbol { ($name:literal,$ty:ty) => {{
            let p=unsafe{s::SDL_LoadFunction(library,concat!($name,"\0").as_ptr().cast())};
            if p.is_null(){ return Err(format!("Missing off-screen function {}: {}",$name,sdl2::get_error())); }
            unsafe{ std::mem::transmute::<Handle,$ty>(p) }
        }}; }
        Ok(Api { library:library as usize, create:symbol!("OSMesaCreateContextExt",Create), destroy:symbol!("OSMesaDestroyContext",Destroy), make:symbol!("OSMesaMakeCurrent",Make), current:symbol!("OSMesaGetCurrentContext",Current), proc:symbol!("OSMesaGetProcAddress",GetProc), store:symbol!("OSMesaPixelStore",Store), color:symbol!("OSMesaGetColorBuffer",Color), finish:symbol!("glFinish",Finish) })
    }).as_ref().map_err(Clone::clone)
}
fn size_valid(w:u32,h:u32)->Result<usize,String>{
    if w==0||h==0||w>8192||h>8192 {return Err(format!("Off-screen dimensions out of bounds: {w}x{h}"));}
    (w as usize).checked_mul(h as usize).and_then(|v|v.checked_mul(4)).ok_or_else(||"Off-screen buffer overflow".into())
}
fn size(window:*mut s::SDL_Window)->(u32,u32){
    let(mut w,mut h)=(0,0);unsafe{s::SDL_GetWindowSize(window,&mut w,&mut h)};(w.max(1) as u32,h.max(1) as u32)
}
pub fn drawable_size(window:&Window)->(u32,u32){if enabled(){window.size()}else{window.drawable_size()}}
pub fn current_id()->usize{if enabled(){api().map(|a|unsafe{(a.current)() as usize}).unwrap_or(0)}else{unsafe{s::SDL_GL_GetCurrentContext() as usize}}}
pub fn set_share(value:bool){SHARE.with(|v|v.set(value));}
pub fn proc_address(video:&sdl2::VideoSubsystem,name:&str)->*const c_void{
    if !enabled(){return video.gl_get_proc_address(name) as *const _;}
    let Ok(a)=api()else{return ptr::null()};let Ok(n)=CString::new(name)else{return ptr::null()};
    unsafe{let p=(a.proc)(n.as_ptr());if !p.is_null(){p.cast_const()}else{s::SDL_LoadFunction(a.library as Handle,n.as_ptr()).cast_const()}}
}
pub struct Context { handle:Handle, window:*mut s::SDL_Window, dimensions:Cell<(u32,u32)>, pixels:RefCell<Vec<u8>> }
impl Context {
    pub fn new(window:&Window)->Result<Self,String>{
        let a=api()?;
        let share=if SHARE.with(|v|v.get()){unsafe{(a.current)()}}else{ptr::null_mut()};
        let handle=unsafe{(a.create)(0x1908,24,8,0,share)};
        if handle.is_null(){return Err("OSMesa could not allocate a GL context".into());}
        let context=Self{handle,window:window.raw(),dimensions:Cell::new((0,0)),pixels:RefCell::new(Vec::new())};
        context.bind()?;
        eprintln!("Zombie Farm: OSMesa off-screen context active; native WGL/EGL bypassed.");
        Ok(context)
    }
    pub fn is_current(&self)->bool{self.dimensions.get()==size(self.window)&&api().map(|a|unsafe{(a.current)()==self.handle}).unwrap_or(false)}
    pub fn bind(&self)->Result<(),String>{
        let a=api()?;let(w,h)=size(self.window);let bytes=size_valid(w,h)?;
        let mut pixels=self.pixels.borrow_mut();
        // Finish outstanding work before moving a buffer referenced by Mesa.
        if pixels.len()!=bytes{unsafe{if !(a.current)().is_null(){(a.finish)();}};pixels.resize(bytes,0);}
        let ok=unsafe{(a.make)(self.handle,pixels.as_mut_ptr().cast(),0x1401,w as i32,h as i32)};
        if ok==0{return Err(format!("OSMesa bind failed at {w}x{h}"));}
        // Store first row at the top, matching SDL surfaces (GL coordinates unchanged).
        unsafe{(a.store)(0x11,0)};
        self.dimensions.set((w,h));Ok(())
    }
}
impl Drop for Context {fn drop(&mut self){if let Ok(a)=api(){unsafe{(a.destroy)(self.handle)}}}}
pub fn present(window:&Window)->Result<(),String>{
    if !enabled(){window.gl_swap_window();return Ok(());}
    let a=api()?;
    unsafe{
        (a.finish)();
        let handle=(a.current)();let(mut w,mut h,mut format)=(0,0,0);let mut pixels:Handle=ptr::null_mut();
        if handle.is_null()||(a.color)(handle,&mut w,&mut h,&mut format,&mut pixels)==0||pixels.is_null(){return Err("Off-screen framebuffer unavailable".into());}
        let surface=s::SDL_GetWindowSurface(window.raw());
        if surface.is_null(){return Err(format!("SDL software surface: {}",sdl2::get_error()));}
        // Resize can land between render and presentation: skip one stale frame.
        if (*surface).w!=w||(*surface).h!=h{return Ok(());}
        if s::SDL_LockSurface(surface)!=0{return Err(sdl2::get_error());}
        let result=s::SDL_ConvertPixels(w,h,sdl2::pixels::PixelFormatEnum::RGBA32 as u32,pixels,w*4,(*(*surface).format).format,(*surface).pixels,(*surface).pitch);
        s::SDL_UnlockSurface(surface);
        if result!=0{return Err(format!("Pixel presentation conversion: {}",sdl2::get_error()));}
        if s::SDL_UpdateWindowSurface(window.raw())!=0{return Err(format!("Window presentation: {}",sdl2::get_error()));}
    }
    Ok(())
}
#[cfg(test)]mod tests{
use super::*;
#[test]fn buffer_sizes_checked(){assert_eq!(size_valid(960,640).unwrap(),2457600);assert_eq!(size_valid(1,1).unwrap(),4);for(w,h)in[(0,480),(640,0),(u32::MAX,2),(2,u32::MAX),(8193,1)]{assert!(size_valid(w,h).is_err());}}
#[test]fn share_is_explicit(){set_share(false);assert!(!SHARE.with(|v|v.get()));set_share(true);assert!(SHARE.with(|v|v.get()));set_share(false);}
}

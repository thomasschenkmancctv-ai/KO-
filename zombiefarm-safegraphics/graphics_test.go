package main

import (
 "crypto/sha256"
 "fmt"
 "os"
 "os/exec"
 "path/filepath"
 "reflect"
 "strings"
 "testing"
)

func TestGraphicsDesktopPathExplicit(t *testing.T) {
 want:=[]string{"Game/ZombieFarm.app","--scale-hack=2","--gles1=gles1_on_gl2"}
 if !reflect.DeepEqual(runtimeArguments(),want) { t.Fatal(runtimeArguments()) }
 a:=runtimeArguments();a[2]="--gles1=gles1_native"
 if !reflect.DeepEqual(runtimeArguments(),want) {t.Fatal("shared args mutated")}
}
func TestWineOverridesPreserveUnrelatedEntries(t *testing.T) {
 cases:=map[string]string{
  "":"opengl32=n",
  "opengl32=b":"opengl32=n",
  "mscoree,mshtml=;opengl32=b":"mscoree,mshtml=;opengl32=n",
  "OPENGL32.DLL,d3d11=b;*opengl32=n,b;dxgi=n":"d3d11=b;dxgi=n;opengl32=n",
  "d3d11,dxgi=n,b":"d3d11,dxgi=n,b;opengl32=n",
 }
 for input,want:=range cases { if got:=nativeOpenGLOverride(input);got!=want {t.Errorf("%q -> %q wanted %q",input,got,want)} }
}
func TestSoftwareEnvironmentIsIsolatedAndDeterministic(t *testing.T) {
 t.Setenv("SDL_OPENGL_ES_DRIVER","1")
 original:=[]string{"Path=abc","SDL_OPENGL_ES_DRIVER=1","sdl_opengl_library=bad","GALLIUM_DRIVER=zink","WINEDLLOVERRIDES=opengl32=b;mscoree,mshtml=","MESA_GL_VERSION_OVERRIDE=1.1","ZF_USER_DATA=my-farm","OTHER=x=y"}
 before:=append([]string(nil),original...)
 cmd:=exec.Command("unused.exe");cmd.Dir=filepath.Join(t.TempDir(),"a folder");cmd.Env=original
 configureGraphics(cmd)
 wants:=map[string]string{"SDL_OPENGL_ES_DRIVER":"0","SDL_OPENGL_LIBRARY":filepath.Join(cmd.Dir,"compat","opengl32.dll"),"GALLIUM_DRIVER":"llvmpipe","LIBGL_ALWAYS_SOFTWARE":"true","WINEDLLOVERRIDES":"mscoree,mshtml=;opengl32=n","ZF_USER_DATA":"my-farm","OTHER":"x=y"}
 for k,v:=range wants {if envValue(cmd.Env,k)!=v {t.Errorf("%s=%s",k,envValue(cmd.Env,k))}}
 if envValue(cmd.Env,"MESA_GL_VERSION_OVERRIDE")!="" {t.Fatal("inherited forced GL version")}
 if !reflect.DeepEqual(before,original)||os.Getenv("SDL_OPENGL_ES_DRIVER")!="1" {t.Fatal("mutated parent settings")}
 for k:=range wants {count:=0;for _,entry:=range cmd.Env {name,_,_:=strings.Cut(entry,"=");if strings.EqualFold(k,name){count++}};if count!=1{t.Errorf("duplicate %s",k)}}
 first:=append([]string(nil),cmd.Env...);configureGraphics(cmd);if !reflect.DeepEqual(first,cmd.Env){t.Fatal("reconfiguration changed values")}
}
func TestGraphicsIntegrityRejectsMissingAndTamperedDriver(t *testing.T) {
 dir:=t.TempDir();os.MkdirAll(filepath.Join(dir,"compat"),0700)
 m:=Manifest{Files:map[string]Entry{}}
 if verifyGraphics(dir,m)==nil {t.Fatal("accepted absent DLLs")}
 for _,n:=range []string{"compat/opengl32.dll","compat/libgallium_wgl.dll"} {b:=[]byte("test-driver");os.WriteFile(filepath.Join(dir,filepath.FromSlash(n)),b,0600);m.Files[n]=Entry{fmt.Sprintf("%x",sha256.Sum256(b)),int64(len(b))}}
 if err:=verifyGraphics(dir,m);err!=nil{t.Fatal(err)}
 os.WriteFile(filepath.Join(dir,"compat/opengl32.dll"),[]byte("corrupted"),0600)
 if verifyGraphics(dir,m)==nil{t.Fatal("accepted corrupted graphics library")}
}
func TestGraphicsDoesNotDisableMemoryOrSkipGame(t *testing.T) {
 joined:=strings.Join(runtimeArguments()," ")
 for _,bad:=range []string{"--headless","--disable-direct-memory-access","--gdb","--gles1=gles1_native"} {if strings.Contains(joined,bad){t.Fatal("unexpected behavior change",bad)}}
}

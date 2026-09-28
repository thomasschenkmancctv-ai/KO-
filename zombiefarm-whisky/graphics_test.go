package main

import (
 "os/exec"
 "reflect"
 "strings"
 "testing"
)
func TestGraphicsDesktopPathExplicit(t *testing.T) {
 want:=[]string{"Game/ZombieFarm.app","--scale-hack=2","--gles1=gles1_on_gl2"}
 if !reflect.DeepEqual(runtimeArguments(),want) {t.Fatalf("unexpected args: %v",runtimeArguments())}
}
func TestGraphicsEveryRelaunchFreshArguments(t *testing.T) {
 a:=runtimeArguments(); a[2]="--gles1=gles1_native"
 if runtimeArguments()[2]!="--gles1=gles1_on_gl2" {t.Fatal("renderer contaminated across farm switch")}
}
func TestGraphicsEnvironmentNoDuplicateOrGlobalSideEffects(t *testing.T) {
 t.Setenv("SDL_OPENGL_ES_DRIVER","1")
 original:=[]string{"Path=abc","SDL_OPENGL_ES_DRIVER=1","sdl_opengl_es_driver=1","ZF_USER_DATA=test-farm","OTHER=x=y"}
 unchanged:=append([]string(nil),original...)
 c:=exec.Command("unused.exe");c.Env=original
 configureGraphics(c)
 want:=[]string{"Path=abc","ZF_USER_DATA=test-farm","OTHER=x=y","OTHER_DUMMY=unused"}
 want=want[:4];want=append(want,"SDL_OPENGL_ES_DRIVER=0")
 if !reflect.DeepEqual(c.Env,want) {t.Fatalf("unsafe environment: %v",c.Env)}
 if !reflect.DeepEqual(original,unchanged) {t.Fatal("modified shared parent environment slice")}
}
func TestGraphicsDoesNotDisableMemoryOrSkipGame(t *testing.T) {
 joined:=strings.Join(runtimeArguments()," ")
 for _, bad:=range []string{"--headless","--disable-direct-memory-access","--gdb","--gles1=gles1_native"} {
  if strings.Contains(joined,bad) {t.Fatalf("unrequested change: %s",bad)}
 }
}

package main

import (
 "fmt"
 "os/exec"
 "path/filepath"
 "strings"
)

// This release supplies the software implementation, not just a GLES option.
// Driver and environment changes are restricted to the launched game process.
func runtimeArguments() []string {
 return []string{"Game/ZombieFarm.app", "--scale-hack=2", "--gles1=gles1_on_gl2"}
}
func envValue(env []string, name string) string {
 var value string
 for _, entry := range env {
  key, v, ok := strings.Cut(entry, "=")
  if ok && strings.EqualFold(key, name) { value = v }
 }
 return value
}
func nativeOpenGLOverride(existing string) string {
 rules := []string{}
 for _, rule := range strings.Split(existing, ";") {
  keys, value, ok := strings.Cut(rule, "=")
  if !ok || strings.TrimSpace(keys)=="" { continue }
  keep := []string{}
  for _, key := range strings.Split(keys, ",") {
   key = strings.TrimSpace(key)
   normalized := strings.TrimPrefix(strings.ToLower(key), "*")
   normalized = strings.TrimSuffix(normalized, ".dll")
   if normalized != "opengl32" && key!="" { keep=append(keep,key) }
  }
  if len(keep)>0 { rules=append(rules, strings.Join(keep,",")+"="+value) }
 }
 return strings.Join(append(rules,"opengl32=n"),";")
}
func configureGraphics(cmd *exec.Cmd) {
 controlled := map[string]bool{
  "sdl_opengl_es_driver":true, "sdl_opengl_library":true, "winedlloverrides":true,
  "gallium_driver":true, "libgl_always_software":true, "lp_num_threads":true,
  "mesa_gl_version_override":true, "mesa_glsl_version_override":true,
  "mesa_extension_override":true, "path":true,
 }
 clean := make([]string, 0, len(cmd.Env)+7)
 for _, entry := range cmd.Env {
  key, _, _ := strings.Cut(entry,"=")
  if !controlled[strings.ToLower(key)] { clean=append(clean,entry) }
 }
 override := nativeOpenGLOverride(envValue(cmd.Env,"WINEDLLOVERRIDES"))
 // LoadLibrary with an absolute DLL path does not add that directory to the
 // dependency search. libgallium_wgl is an import of opengl32; expose it here.
 // Idempotent on restarts; no machine PATH or Wine registry is changed.
 graphicsDir:=filepath.Join(cmd.Dir,"compat")
 paths:=[]string{graphicsDir}
 for _,p:=range strings.Split(envValue(cmd.Env,"PATH"),";") {
  if p!="" && !strings.EqualFold(filepath.Clean(p),filepath.Clean(graphicsDir)) { paths=append(paths,p) }
 }
 cmd.Env=append(clean,
  "SDL_OPENGL_ES_DRIVER=0",
  "SDL_OPENGL_LIBRARY="+filepath.Join(graphicsDir,"opengl32.dll"),
  "WINEDLLOVERRIDES="+override,
  "GALLIUM_DRIVER=llvmpipe", "LIBGL_ALWAYS_SOFTWARE=true", "LP_NUM_THREADS=4",
  "PATH="+strings.Join(paths,";"))
}
func verifyGraphics(dir string, m Manifest) error {
 for _, name := range []string{"compat/opengl32.dll","compat/libgallium_wgl.dll"} {
  entry, ok := m.Files[name]
  if !ok { return fmt.Errorf("bundled graphics file missing: %s",name) }
  if err:=verifyFile(filepath.Join(dir,filepath.FromSlash(name)),entry);err!=nil {
   return fmt.Errorf("bundled graphics verification failed for %s: %w",name,err)
  }
 }
 return nil
}

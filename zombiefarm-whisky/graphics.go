package main

import (
 "os/exec"
 "strings"
)

// The native GLES probe can leave SDL in an EGL path that Whisky cannot create.
// Select desktop GL 2.1 translation before the first context is constructed.
// Arguments override saved renderer preferences without modifying those files.
// No JIT, simulation-clock, or guest-game changes are made here.
func runtimeArguments() []string {
 return []string{"Game/ZombieFarm.app", "--scale-hack=2", "--gles1=gles1_on_gl2"}
}
func configureGraphics(cmd *exec.Cmd) {
 clean := make([]string, 0, len(cmd.Env)+1)
 for _, entry := range cmd.Env {
  key, _, _ := strings.Cut(entry, "=")
  if !strings.EqualFold(key, "SDL_OPENGL_ES_DRIVER") { clean = append(clean, entry) }
 }
 cmd.Env = append(clean, "SDL_OPENGL_ES_DRIVER=0")
}

from pathlib import Path
# Wine's DLL override is read in its Unix loader. A Win32 child environment
# cannot reliably undo an inherited builtin opengl32 rule. A unique module
# filename is not eligible for builtin substitution and loads the actual bytes.
root=Path('zombiefarm-safegraphics')
for name in ['graphics.go','graphics_test.go']:
 p=root/name;s=p.read_text()
 # Change filesystem paths and argument library path, not old-override parsing.
 s=s.replace('compat/opengl32.dll','compat/zfsoftwaregl.dll')
 s=s.replace('"compat","opengl32.dll"','"compat","zfsoftwaregl.dll"')
 s=s.replace('"compat", "opengl32.dll"','"compat", "zfsoftwaregl.dll"')
 s=s.replace('filepath.Join(graphicsDir,"opengl32.dll")','filepath.Join(graphicsDir,"zfsoftwaregl.dll")')
 p.write_text(s)
p=root/'prepare.py';s=p.read_text()
s=s.replace('shutil.copy2(f,compat/n)',"shutil.copy2(f,compat/('zfsoftwaregl.dll' if n=='opengl32.dll' else n))")
s=s.replace("(d/'compat/opengl32.dll')", "(d/'compat/zfsoftwaregl.dll')")
s=s.replace("'llvmpipe' in log_text and 'Mesa 25.1.6' in log_text", "any('Driver info:' in line and 'llvmpipe' in line and 'Mesa 25.1.6' in line for line in log_text.splitlines())")
p.write_text(s)
print('Unique bundled driver selected; require actual driver-reported Mesa version, never launcher text.')

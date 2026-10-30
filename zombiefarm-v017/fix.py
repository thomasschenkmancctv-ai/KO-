from pathlib import Path
p=Path('engine/src/desktop_game.rs');s=p.read_text();s=s.replace('objectAtIndex:index as u32','objectAtIndex:(index as u32)').replace('setFflags:flags|0x1ff','setFflags:(flags|0x1ff)');p.write_text(s)

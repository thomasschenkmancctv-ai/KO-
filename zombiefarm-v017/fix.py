from pathlib import Path
p=Path('engine/src/desktop_game.rs');s=p.read_text();s=s.replace('objectAtIndex:index as u32','objectAtIndex:(index as u32)').replace('setFflags:flags|0x1ff','setFflags:(flags|0x1ff)');s=s.replace('cells.push(json!({"x":x,"y":y,"sx":sp.x,"sy":sp.y,','let sx=sp.x;let sy=sp.y;cells.push(json!({"x":x,"y":y,"sx":sx,"sy":sy,');p.write_text(s)

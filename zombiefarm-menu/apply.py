from pathlib import Path
import zipfile,shutil
R=Path('engine')
with zipfile.ZipFile('baseline/runtime-source.zip')as z:
 for n in z.namelist():
  if n.startswith('src/'):
   p=R/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(n))
with zipfile.ZipFile('previous/desktop-source-and-content.zip')as z:z.extractall('desktop')
shutil.copy2('zombiefarm-menu/farm_menu.rs',R/'src/farm_menu.rs')
shutil.copy2('zombiefarm-menu/saves.go','desktop/launcher/saves.go')
def edit(file,a,b):
 p=R/file;s=p.read_text();assert s.count(a)==1,(file,a[:80],s.count(a));p.write_text(s.replace(a,b))
edit('src/lib.rs','mod zombie_growth;','mod zombie_growth;\nmod farm_menu;')
edit('src/objc/messages.rs','    crate::zombie_growth::before_message(env, receiver, selector_name);','    crate::zombie_growth::before_message(env, receiver, selector_name);\n    if crate::farm_menu::override_message(env, receiver, selector_name) { return; }')
edit('src/zombie_growth.rs','    let scene: id = msg![env; receiver runningScene];','    let scene: id = msg![env; receiver runningScene];\n    crate::farm_menu::scene(env, scene);')
edit('src/frameworks/foundation/ns_run_loop.rs','            let next_due = uikit::handle_events(env);','            crate::farm_menu::poll(env);\n            let next_due = uikit::handle_events(env);')
p=R/'src/desktop_mods.rs';s=p.read_text().replace('0.14','0.15')
s=s.replace('fn atomic(path:', 'pub(crate) fn atomic(path:').replace('fn backup_saves()', 'pub(crate) fn backup_saves()')
s=s.replace('    crop: usize,','    crop: usize,\n    save_page: usize,\n    chosen_save: String,')
s=s.replace('            open: false,','            open: std::env::var("ZF_START_MENU").ok().as_deref()==Some("1"),')
s=s.replace('            page: 0,','            page: if std::env::var("ZF_START_MENU").ok().as_deref()==Some("1") {6} else {0},')
s=s.replace('            crop: 0,','            crop: 0,\n            save_page: 0,\n            chosen_save: String::new(),')
s=s.replace('        "close" => s.open = false,','''        "games" => {s.page=6;s.save_page=0;},
        "newgame" => s.page=8,
        "cancelnew" => s.page=6,
        "cancelLoad" => s.page=7,
        "confirmnew" => {crate::farm_menu::queue("new", "");s.message="Saving current farm and opening a separate new farm...".into();},
        "loadgames" => {s.page=7;s.save_page=0;},
        "nextsaves" => {let n=crate::farm_menu::catalog().slots.len();s.save_page=(s.save_page+1)%((n+3)/4).max(1);},
        "load0" | "load1" | "load2" | "load3" => {
            let i=s.save_page*4+action[4..].parse::<usize>().unwrap_or(0);
            if let Some(slot)=crate::farm_menu::catalog().slots.get(i) {s.chosen_save=slot.id.clone();s.page=9;}
        },
        "confirmload" => {crate::farm_menu::queue("load", &s.chosen_save);s.message="Saving this farm before loading the selected farm...".into();},
        "savegame" => {crate::farm_menu::queue("save", "");s.message="Saving farm...".into();},
        "tools" => s.page=0,
        "close" => s.open = false,''')
s=s.replace('        "back" => s.page = 0,','        "back" => s.page = match s.page {7|8=>6,9=>7,_=>0},')
s=s.replace('        _ => vec!["sandbox", "graphics", "display", "audit", "close"],','''        6 => vec!["close", "newgame", "loadgames", "savegame", "tools"],
        7 => vec!["load0", "load1", "load2", "load3", "nextsaves"],
        8 => vec!["confirmnew", "cancelnew"],
        9 => vec!["confirmload", "cancelLoad"],
        _ => vec!["games", "sandbox", "graphics", "display", "audit"],''')
s=s.replace('            ("Return to farm".into(), "".into()),','')
s=s.replace('        _ => vec![\n            ("Sandbox".into()', '''        6 => vec![("Continue".into(),crate::farm_menu::current_label()),("New Game".into(),"Separate farm".into()),("Load Game".into(),"Choose a save".into()),("Save Game".into(),"Save + backup".into()),("Tools & settings".into(),"".into())],
        7 => {let c=crate::farm_menu::catalog();let mut r:Vec<(String,String)>=(0..4).map(|i|c.slots.get(s.save_page*4+i).map(|v|(v.label.clone(),if v.id==c.active {"Current".into()} else {"Load".into()})).unwrap_or(("".into(),"".into()))).collect();r.push(("Next page".into(),format!("{} / {}",s.save_page+1,((c.slots.len()+3)/4).max(1))));r},
        8 => vec![("Create new farm".into(),"Keep existing".into()),("Cancel".into(),"".into())],
        9 => vec![("Load selected farm".into(),"Save current first".into()),("Cancel".into(),"".into())],
        _ => vec![
            ("Game menu".into(),"New / Load / Save".into()),
            ("Sandbox".into()''')
s=s.replace('["Farm settings","Sandbox","Graphics","Screen fit","Crop inspector","Crop preview"][s.page.min(5)as usize]', '["Farm settings","Sandbox","Graphics","Screen fit","Crop inspector","Crop preview","Zombie Farm","Load Game","New Game","Load this farm?"][s.page.min(9)as usize]')
s=s.replace('match s.page{1=>format!', 'match s.page{6=>format!("Current save: {}. Continue then press PLAY.\\nInvasions have no waiting timer.\\nNew Game keeps every existing farm.",crate::farm_menu::current_label()),7=>"Choose a saved farm. Each has separate progress.\\nCurrent progress is saved before loading another.\\nNo farms are overwritten or deleted.".into(),8=>"This creates a separate, fresh farm.\\nYour current farm is saved and kept.\\nReturn to it through Load Game.".into(),9=>format!("Selected: {}\\nCurrent farm will be saved first.\\nThe game restarts safely to load the selected farm.",s.chosen_save),1=>format!')
s+='\npub fn menu_message(text:&str) {state().lock().unwrap().message=text.into();}\n';p.write_text(s)
p=R/'src/zombie_growth.rs';s=p.read_text().replace('    if op == "save" {','''    if op == "cooldown" {
        let date:id=msg_class![env; NSDate date];
        let _:()=msg![env; data setLastInvasionDate:date];
    }
    if op == "army" && state_code==0 {
        let tm:id=msg_class![env; ZFToolManager toolManager];
        let unit=ns_string::from_rust_string(env,"ZombieActor".to_string());
        for i in 0..command["count"].as_u64().unwrap_or(0).min(16) {
            let point=CGPoint{x:10.0+i as f32,y:10.0};
            let _:()=msg![env; tm harvestZombieWithUnitKey:unit onTile:point];
        }
    }
    if op == "save" {''')
s=s.replace('    let report = json!({"schema":1','''    let gs:id=msg_class![env; GameState gameState];
    let can_invade:bool=msg![env; gs canInvade];
    let raw_can_invade=crate::farm_menu::raw_can_invade(env,gs);
    let army:i32=msg![env; gs curArmySize];
    let army_max:i32=msg![env; gs maxArmySize];
    let report = json!({"can_invade":can_invade,"original_can_invade":raw_can_invade,"army":army,"army_max":army_max,"schema":1''');p.write_text(s)
p=Path('desktop/launcher/main.go');s=p.read_text().replace('var version = "0.14"','var version = "0.15"')
a='\tcmd := exec.Command(filepath.Join(dir, exe), "Game/ZombieFarm.app", "--scale-hack=2")';start=s.index(a);end=s.index('\n\treturn nil\n}',start)
s=s[:start]+'''\tidx, e := loadIndex(root)
\tif e != nil { return e }
\tshowMenu := "1"
\tif os.Getenv("ZF_SKIP_START_MENU")=="1" {showMenu="0"}
\tfor {
\t\tdata, e = slotDir(root,idx.Active)
\t\tif e != nil { return e }
\t\tif e = os.MkdirAll(data,0700); e != nil {return e}
\t\tcmd := exec.Command(filepath.Join(dir, exe), "Game/ZombieFarm.app", "--scale-hack=2")
\t\tcmd.Dir = dir
\t\tcmd.Stdout = log
\t\tcmd.Stderr = log
\t\tcmd.Env = append(os.Environ(), "ZF_DESKTOP=1", "ZF_USER_DATA="+data, "ZF_SAVE_ROOT="+root, "ZF_START_MENU="+showMenu, "LD_LIBRARY_PATH="+filepath.Join(dir, "lib")+":"+os.Getenv("LD_LIBRARY_PATH"))
\t\tconfigureProcess(cmd)
\t\te = runVisible(cmd, root, log)
\t\tvar exitErr *exec.ExitError
\t\tif errors.As(e,&exitErr) && exitErr.ExitCode()==42 {
\t\t\tidx,e=consumeSwitch(root,idx)
\t\t\tif e!=nil {return fmt.Errorf("could not switch farms safely: %w",e)}
\t\t\tshowMenu="1"
\t\t\tfmt.Fprintf(log,"Save menu: switched to %s; previous guest exited before next launch.\\n",idx.Active)
\t\t\tcontinue
\t\t}
\t\tif e!=nil {return fmt.Errorf("the game stopped unexpectedly (%v).\\nDiagnostic log: %s", e, logfile)}
\t\tbreak
\t}
'''+s[end:];p.write_text(s)
p=Path('desktop/tools/package.py');p.write_text(p.read_text().replace('0.14','0.15'))
p=Path('desktop/tools/growth_regression.py');p.write_text(p.read_text().replace('panel(190,98);opened=True','panel(190,151);opened=True'))
print('v0.15 source applied; original farm resources preserved')

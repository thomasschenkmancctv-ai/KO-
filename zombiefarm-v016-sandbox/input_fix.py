from pathlib import Path
p=Path('engine/src/window.rs');s=p.read_text()
a='            self.event_queue.push_back(match event {'
b='''            // Coalesce only consecutive queued moves from this mouse. Keep every
            // press/release and all non-mouse events in their original order.
            if crate::desktop_mods::desktop_enabled() {
                if let E::MouseMotion { x, y, mousestate, .. } = event {
                    if mousestate.left() {
                        let point = transform_input_coords(self, (x as f32, y as f32), false);
                        if coalesce_mouse_move(&mut self.event_queue, point) { continue; }
                    }
                }
            }
'''+a
assert s.count(a)==1;s=s.replace(a,b)
s+='''
/// Replace an obsolete unconsumed drag point, never a button boundary.
pub(crate) fn coalesce_mouse_move(queue:&mut VecDeque<Event>,point:Coords)->bool {
    if let Some(Event::TouchesMove(touches))=queue.back_mut() {
        if touches.len()==1 && touches.contains_key(&FingerId::Mouse) {
            touches.insert(FingerId::Mouse,point);return true;
        }
    }
    false
}
''';p.write_text(s)
p=Path('engine/src/sandbox_rewards.rs');s=p.read_text();s+='''
#[cfg(test)] mod input_regression_tests {
 use crate::window::{Event,FingerId,coalesce_mouse_move};
 use std::collections::{HashMap,VecDeque};
 #[test] fn latest_drag_position_keeps_button_edges(){
  let touch=|p|HashMap::from([(FingerId::Mouse,p)]);
  let mut q=VecDeque::from([Event::TouchesDown(touch((0.,0.))),Event::TouchesMove(touch((1.,1.)))]);
  for n in 0..10000 {assert!(coalesce_mouse_move(&mut q,(n as f32,2.)));}
  assert_eq!(q.len(),2);
  if let Event::TouchesMove(p)=q.back().unwrap(){assert_eq!(p[&FingerId::Mouse],(9999.,2.));}else{panic!();}
  q.push_back(Event::TouchesUp(touch((9999.,2.))));
  assert!(!coalesce_mouse_move(&mut q,(1.,1.)));assert_eq!(q.len(),3);
 }
 #[test] fn multitouch_and_quit_are_never_coalesced(){
  let mut q=VecDeque::from([Event::TouchesMove(HashMap::from([(FingerId::Touch(1),(1.,1.))]))]);
  assert!(!coalesce_mouse_move(&mut q,(2.,2.)));
  q.push_back(Event::Quit);assert!(!coalesce_mouse_move(&mut q,(3.,3.)));
 }
}
''';p.write_text(s)
print('Bounded mouse-drag queue integrated; button and multitouch boundaries preserved')

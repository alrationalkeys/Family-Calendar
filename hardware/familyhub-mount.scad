// ============================================================================
// FamilyHub wall display — enclosure + mount kit (OpenSCAD)
// Tuned for the chosen parts:
//   SCREEN  Forzola 15.6" industrial touch monitor — 365 x 223 x 10 mm,
//           VESA 75x75, ports in a 170 mm strip along the BOTTOM edge that
//           bulges to 23 mm (the "port hump").
//   BRAIN   origimagic C3 mini PC (i3-5005U) — 128 x 127 x 43 mm, ports on
//           two opposite faces (LAN/HDMI/DC on one, USB/power button on the other).
//   AUDIO   HONKYOB USB speaker+mic bar — 130 x 61 x 46 mm (grilles + mic on
//           one 130x61 face). Lives in an optional side pocket (spk_pocket).
//
// GOAL: a clean, Skylight-like install where the mini PC and every cable are
// hidden behind the screen, and the whole thing lifts off the wall onto a
// counter stand with no tools. Pick a filament colour; only the screen shows.
//
// PARTS (set `part` below, F6 to render, export STL):
//   back_case   : box that bolts to the screen's VESA holes, cradles the C3
//                 (open at the back for airflow), routes cables out the bottom.
//   strap_bar   : bar across the open back (top edge) that keeps the C3 in.
//   cleat_case  : French-cleat half that bolts to the back_case (bottom edge).
//                 Doubles as the lower retaining bar for the C3.
//   cleat_wall  : French-cleat half that screws to the wall. (case hangs on it)
//   stand       : counter easel — its cleat tongue mates cleat_case, so the same
//                 display drops from wall to stand in seconds.
//   spk_pocket  : OPTIONAL side pocket for the USB speaker/mic bar, grille facing
//                 out the screen's side edge. Bolts to the case side wall (M3).
//   frame_seg   : OPTIONAL cosmetic front-frame edge piece. The 365mm frame is
//                 bigger than the 250mm bed, so it prints as joinable segments.
//   test_vesa / test_pc : small coupons — PRINT THESE FIRST to check fit.
//   preview     : everything assembled, to eyeball clearances.
//
// PRINT: PLA/PETG, 0.2mm, 3 perimeters, 20% infill.
//   back_case front-plate-down (cavity up) — no supports.
//   strap_bar, cleats, stand, pocket flat; frame segments face-down.
//   Always print test_vesa + test_pc first (~40 min) before the ~7h case.
//
// MEASURE BEFORE PRINTING (the "verify" parameters):
//   vesa_dy  if the VESA square isn't centred on the panel, its vertical offset
//   spk_*    the speaker bar's real outer dimensions
// ============================================================================

/* [What to render] */
part = "back_case"; // [back_case, strap_bar, cleat_case, cleat_wall, stand, spk_pocket, frame_seg, test_vesa, test_pc, preview]

/* [Screen — Forzola 15.6in] */
screen_w = 356;      // measured 14.0 in
screen_h = 229;      // measured 9.0 in
screen_t = 13;       // panel thickness (1.5 in total minus the 1 in housing)
vesa     = 75;       // VESA square (75x75)
vesa_dy  = 0;        // VERIFY: VESA centre offset from panel centre (+ = up)
// The raised housing on the back: centred, VESA holes on its FACE, ports on its
// bottom edge. Measured: 2.5 in in from top/bottom, 3.5 in in from the sides.
hump_w   = 178;      // 14 - 2*3.5 in
hump_hh  = 102;      // 9 - 2*2.5 in
hump_d   = 25;       // measured: the housing is ~1 in deep

/* [Mini PC — C3] */
pc_w     = 128;      // across (LAN/HDMI face points DOWN toward the cable slot)
pc_l     = 127;      // up/down
pc_h     = 43;       // thickness
pc_clear = 1.5;      // wiggle room per side

/* [Back case] */
wall   = 3;
fp     = 3;          // front plate thickness (bolts to VESA)
corner = 7;
vent   = true;
brk    = 12;         // corner bracket leg length
brk_h  = 10;         // corner bracket height
$fn    = 48;
case_w = pc_w + 2*(pc_clear + brk + wall);   // ~158
case_h = pc_l + 2*(pc_clear + wall);         // ~136
case_d = fp + pc_h + pc_clear + 4;           // ~51.5 — strap/cleat bars sit in the last 4mm

/* [French cleat] */
cleat_len   = 166;   // spans the case back; holes land on the corner bosses
cleat_h     = 26;
cleat_thick = 12;
cleat_gap   = 2;     // hanging clearance

/* [Counter stand] */
stand_lean  = 12;    // degrees back from vertical
stand_base  = 130;   // base depth (front-to-back footprint)

/* [Speaker pocket — HONKYOB bar, VERIFY dims] */
spk_l    = 127;      // measured 5 in — long axis (mounted vertically, along the screen edge)
spk_w    = 64;       // measured 2.5 in — grille face width -> pocket depth away from the screen
spk_t    = 44;       // measured 1.75 in — thickness -> pocket width across
spk_side = 1;        // 1 = right of the case (viewed from the back), -1 = left
spk_clear = 1;

/* [Optional front frame] */
frame_face  = 16;    // how wide the visible frame border is
frame_lip   = 7;     // overlap onto the screen's black border (<= real border)
seg_len     = 220;   // length of one printed segment (< bed size)

// ---------- helpers ----------
module rrect(w, h, r){ hull() for(x=[-1,1],y=[-1,1]) translate([x*(w/2-r), y*(h/2-r)]) circle(r); }
module slot(l, w, h){ hull(){ translate([-l/2+w/2,0,0]) cylinder(h=h, d=w); translate([l/2-w/2,0,0]) cylinder(h=h, d=w); } }

// ---------- back case ----------
// Origin = VESA centre on the screen's back face. +y is UP on the wall.
// Four bar bosses sit in the corners, in the 12mm margin beside the C3 (outside
// its footprint, so they never collide with it). Cleat holes line up with them.
boss_y_bot = -case_h/2 + wall + 5;
boss_y_top =  case_h/2 - wall - 5;
boss_xs    = [-(case_w/2 - wall - 5), case_w/2 - wall - 5];

module corner_bracket(sx, sy){
  // L-shaped post hugging one corner of the C3's footprint
  ix = sx*(pc_w/2 + pc_clear); iy = sy*(pc_l/2 + pc_clear);
  translate([0,0,fp]) {
    translate([min(ix, ix+sx*wall), min(iy, iy-sy*brk), 0]) cube([wall, brk, brk_h]);
    translate([min(ix, ix-sx*brk), min(iy, iy+sy*wall), 0]) cube([brk, wall, brk_h]);
  }
}

module back_case(){
  difference(){
    union(){
      linear_extrude(fp) rrect(case_w, case_h, corner);                       // front plate
      translate([0,0,fp-0.01]) linear_extrude(case_d-fp)                       // perimeter walls
        difference(){ rrect(case_w, case_h, corner); offset(-wall) rrect(case_w, case_h, corner); }
      for(sx=[-1,1], sy=[-1,1]) corner_bracket(sx, sy);                        // C3 cradle
      for(x=boss_xs, y=[boss_y_bot, boss_y_top])                               // bar bosses
        translate([x, y, case_d-12]) cylinder(h=12, d=10);
      // standoff pads so the C3 sits 2mm off the plate (air under the fan intake)
      for(sx=[-1,1], sy=[-1,1]) translate([sx*(pc_w/2-10), sy*(pc_l/2-10), fp]) cylinder(h=2, d=10);
    }
    // VESA holes through the front plate, countersunk on the cavity side for M4 heads
    for(x=[-vesa/2, vesa/2], y=[-vesa/2, vesa/2])
      translate([x, y, -1]){ cylinder(h=fp+2, d=4.5); translate([0,0,fp-1.6]) cylinder(h=2, d1=4.5, d2=8.5); }
    // bar-boss pilot holes (M3 self-tap, drilled from the back)
    for(x=boss_xs, y=[boss_y_bot, boss_y_top]) translate([x, y, case_d-13]) cylinder(h=15, d=2.7);
    // cable slots — bottom wall (C3's LAN/HDMI/USB/DC face points down into it, the
    // screen's cables come up through it) AND top wall (the C3's other port face:
    // 2x USB-A, USB-C, power button — keep it reachable for a keyboard).
    translate([-55, -case_h/2-wall-2, fp+6]) cube([110, wall+4, case_d]);
    translate([-55,  case_h/2-2,      fp+6]) cube([110, wall+4, case_d]);
    // speaker-pocket bolt holes in the side wall (M3 through, nut inside)
    for(y=[-spk_l/2+15, spk_l/2-15]) translate([spk_side*(case_w/2+1), y, fp+pc_h/2]) rotate([0,90,0]) cylinder(h=wall*2+2, d=3.4, center=true);
    // vents: slots in the top wall + both side walls (C3 fan intakes are on its sides)
    if(vent){
      // (top wall is now mostly slot; side walls carry the vents)
      for(s=[-1,1], i=[-3:3]) translate([s*(case_w/2)-wall/2-1.5, i*13, fp+6]) cube([wall+3, 5, case_d-fp-10]);
    }
  }
}

// bar across the top edge of the open back: keeps the C3 from tipping out
module strap_bar(){
  difference(){
    hull() for(x=boss_xs) translate([x, 0, 0]) cylinder(h=4, d=14);
    for(x=boss_xs) translate([x, 0, -1]){ cylinder(h=6, d=3.4); translate([0,0,2.4]) cylinder(h=3, d1=3.4, d2=6.5); }
  }
}

// ---------- French cleat pair ----------
// 45deg mating faces. Wall half bevels up-and-in; case half bevels down-and-in.
module cleat_bar(flip=false){
  difference(){
    cube([cleat_len, cleat_thick, cleat_h]);
    translate([-1, flip ? -1 : cleat_thick, flip ? cleat_h : 0])
      rotate([flip ? -45 : 45, 0, 0]) cube([cleat_len+2, cleat_h*2, cleat_h*2]);
    for(x=[cleat_len/2+boss_xs[0], cleat_len/2+boss_xs[1]])   // screw holes line up with the case bosses
      translate([x, cleat_thick/2, -1]){ cylinder(h=cleat_h+2, d=3.4); translate([0,0,cleat_h-3]) cylinder(h=4, d1=3.4, d2=7); }
  }
}
module cleat_wall(){ cleat_bar(flip=false); }   // screws to the wall (use M4/wood screws through the same holes)
module cleat_case(){ cleat_bar(flip=true);  }   // bolts to the back_case bottom bosses (M3)

// ---------- counter stand ----------
module stand(){
  h = 150;
  linear_extrude(cleat_len+30, center=true) polygon([[0,0],[stand_base,0],[0,h]]);
  translate([6,0,h*0.62])
    rotate([0,stand_lean,0]) translate([0,-cleat_len/2-15, -cleat_h/2])
      rotate([90,0,90]) cleat_wall();
  // lip at the base front so the screen's bottom edge can rest (port hump stays clear above it)
  translate([stand_base-8,-(cleat_len+30)/2,0]) cube([8, cleat_len+30, screen_t+hump_d+6]);   // lip clears panel + housing
}

// ---------- speaker pocket (optional) ----------
// A box beside the case: speaker bar stands vertically, grille face pointing
// OUT toward the screen's side edge. Front face (z=0) sits against the screen back.
module spk_pocket(){
  ix = spk_t + 2*spk_clear;  iy = spk_l + 2*spk_clear;  iz = spk_w + 2*spk_clear;
  ox = ix + 2*wall;          oy = iy + 2*wall;          oz = iz + fp;
  difference(){
    translate([-ox/2, -oy/2, 0]) cube([ox, oy, oz]);
    translate([-ix/2, -iy/2, fp]) cube([ix, iy, iz+1]);                        // cavity (open at the back)
    // grille: slots through the OUTER (+x) wall so sound + the mic see the room
    for(i=[-5:5]) translate([ox/2-wall-1, i*(iy/12), fp+6]) cube([wall+2, 3, iz-10]);
    // cable notch, bottom wall
    translate([-6, -oy/2-1, fp+4]) cube([12, wall+2, oz]);
    // bolt holes through the INNER (-x) wall, matching the case side wall
    for(y=[-spk_l/2+15, spk_l/2-15]) translate([-ox/2+wall/2, y, fp+pc_h/2]) rotate([0,90,0]) cylinder(h=wall+2, d=3.4, center=true);
  }
}

// ---------- optional cosmetic front frame (segmented) ----------
module frame_seg(len=seg_len){
  difference(){
    cube([len, frame_face, fp+screen_t+2]);
    translate([-1, frame_lip, fp]) cube([len+2, frame_face, screen_t+4]);
    for(x=[6, len-6]) translate([x, frame_face/2, -1]) cylinder(h=fp+3, d=3);
  }
}

// ---------- test coupons ----------
module test_vesa(){ difference(){ cube([vesa+24, vesa+24, fp], center=true);
  for(x=[-vesa/2,vesa/2],y=[-vesa/2,vesa/2]) translate([x,y,-fp]) cylinder(h=fp*3,d=4.5); } }
// a thin plate with the four corner brackets: the C3 should drop in with ~1.5mm play
module test_pc(){
  translate([-case_w/2+wall, -case_h/2+wall, 0]) cube([case_w-2*wall, case_h-2*wall, 2]);
  translate([0,0,-fp+2]) for(sx=[-1,1], sy=[-1,1]) corner_bracket(sx, sy);
}

// ---------- preview ----------
// Z=0 in every part is the HOUSING FACE (where the VESA bolts land); the panel
// itself is hump_d further back. Cables leave the housing's bottom edge and run
// in the hump_d-deep gap under the case's overhang — nothing to cut.
module screen_ghost(){
  color("black", 0.25) translate([-screen_w/2, -screen_h/2 - vesa_dy, -hump_d - screen_t]) cube([screen_w, screen_h, screen_t]);
  color("red", 0.35) translate([-hump_w/2, -hump_hh/2, -hump_d]) cube([hump_w, hump_hh, hump_d]);   // raised housing
}
module preview(){
  screen_ghost();
  back_case();
  color("tan") translate([0, boss_y_top, case_d]) strap_bar();
  color("tan") translate([-cleat_len/2, boss_y_bot - cleat_thick/2, case_d]) cleat_bar(flip=true);
  color("silver", 0.5) translate([-pc_w/2, -pc_l/2, fp+2]) cube([pc_w, pc_l, pc_h]);                 // the C3
  color("tan") translate([spk_side*(case_w/2 + (spk_t+2*spk_clear+2*wall)/2), 0, 0]) spk_pocket();
  // the case plate overhangs the housing top/bottom; plugs hang in the hump_d gap beneath
  echo(str("Case overhangs the housing by ", (case_h - hump_hh)/2, " mm top & bottom; cable gap under it = ", hump_d, " mm"));
  echo(str("Case ", case_w, " x ", case_h, " x ", case_d, " mm; bed must be >= ", max(case_w,case_h), " mm"));
}

// ---------- dispatch ----------
if(part=="back_case")       back_case();
else if(part=="strap_bar")  strap_bar();
else if(part=="cleat_case") cleat_case();
else if(part=="cleat_wall") cleat_wall();
else if(part=="stand")      stand();
else if(part=="spk_pocket") spk_pocket();
else if(part=="frame_seg")  frame_seg();
else if(part=="test_vesa")  test_vesa();
else if(part=="test_pc")    test_pc();
else if(part=="preview")    preview();

// ============================================================================
// FamilyHub wall display — enclosure + mount kit (OpenSCAD)
// Targeted to the HOWENS 15.6" touchscreen (ASIN B0D2D8CCY1):
//   screen 365 x 230 x 10 mm, VESA 75x75, ports on the BOTTOM edge.
//
// GOAL: a clean, Skylight-like install where the Raspberry Pi and every cable
// are hidden behind the screen, and the whole thing lifts off the wall onto a
// counter stand with no tools.
//
// PARTS (set `part` below, F6 to render, export STL):
//   back_case   : box that bolts to the screen's VESA holes, holds the Pi 5,
//                 vents the heat, and routes all cables down to the bottom ports.
//   cleat_case  : French-cleat half that bolts to the back_case.
//   cleat_wall  : French-cleat half that screws to the wall. (case hangs on it)
//   stand       : counter easel — its cleat tongue mates cleat_case, so the same
//                 display drops from wall to stand in seconds.
//   frame_seg   : OPTIONAL cosmetic front-frame edge piece. The 365mm frame is
//                 bigger than the 250mm bed, so it prints as joinable segments.
//   test_vesa / test_pi : small coupons — PRINT THESE FIRST to check hole fit.
//
// PRINT: PLA/PETG, 0.2mm, 3 perimeters, 20% infill.
//   back_case front-plate-down (cavity up) — no supports.
//   cleats & stand flat; frame segments face-down.
//   Always print test_vesa + test_pi first (~15 min) before the ~6h case.
// ============================================================================

/* [What to render] */
part = "back_case"; // [back_case, cleat_case, cleat_wall, stand, frame_seg, test_vesa, test_pi, preview]

/* [Screen — HOWENS 15.6in, edit if yours differs] */
screen_w = 365;
screen_h = 230;
screen_t = 10;       // panel thickness (1cm)
vesa     = 75;       // VESA square (75x75)

/* [Raspberry Pi 5 mounting] */
pi_hx = 58;          // hole spacing, long axis
pi_hy = 49;          // hole spacing, short axis
pi_screw = 2.5;      // M2.5 self-tap pilot

/* [Back case] */
case_w = 120;        // must clear the Pi board (85mm) — keep > 100
case_h = 108;
case_d = 34;         // depth: Pi + connectors + cable room
wall   = 3;
fp     = 3;          // front plate thickness (bolts to VESA)
corner = 7;
vent   = true;
$fn    = 48;

/* [French cleat] */
cleat_len   = 96;    // fits across the case back
cleat_h     = 26;
cleat_thick = 12;
cleat_gap   = 2;     // hanging clearance

/* [Counter stand] */
stand_lean  = 12;    // degrees back from vertical
stand_base  = 120;   // base depth (front-to-back footprint)
stand_wall  = 6;

/* [Optional front frame] */
frame_face  = 16;    // how wide the visible frame border is
frame_lip   = 7;     // overlap onto the screen's black border (<= real border)
seg_len     = 220;   // length of one printed segment (< bed size)

// ---------- helpers ----------
module rrect(w, h, r){ hull() for(x=[-1,1],y=[-1,1]) translate([x*(w/2-r), y*(h/2-r)]) circle(r); }

// ---------- back case ----------
module back_case(){
  difference(){
    union(){
      // solid front plate
      linear_extrude(fp) rrect(case_w, case_h, corner);
      // perimeter walls
      translate([0,0,fp-0.01])
        linear_extrude(case_d-fp)
          difference(){ rrect(case_w, case_h, corner); offset(-wall) rrect(case_w, case_h, corner); }
      // Pi standoffs (6mm tall posts)
      for(x=[-pi_hx/2, pi_hx/2], y=[-pi_hy/2, pi_hy/2])
        translate([x, y, fp]) cylinder(h=6, d=6);
      // bosses the cleat_case bolts into (from inside, through the back wall)
      for(x=[-cleat_len/2+10, cleat_len/2-10])
        translate([x, -case_h/2+wall+6, case_d-10]) cylinder(h=10, d=9);
    }
    // VESA holes through the front plate, countersunk on the cavity side for M4 heads
    for(x=[-vesa/2, vesa/2], y=[-vesa/2, vesa/2])
      translate([x, y, -1]){ cylinder(h=fp+2, d=4.5); translate([0,0,fp-1.6]) cylinder(h=2, d1=4.5, d2=8.5); }
    // Pi pilot holes
    for(x=[-pi_hx/2, pi_hx/2], y=[-pi_hy/2, pi_hy/2])
      translate([x, y, fp-1]) cylinder(h=8, d=pi_screw-0.2);
    // cleat boss pilot holes (drilled from the OUTSIDE/back)
    for(x=[-cleat_len/2+10, cleat_len/2-10])
      translate([x, -case_h/2+wall+6, case_d-11]) cylinder(h=13, d=3.2);
    // cable slot — bottom wall, cables run up from the screen's bottom ports
    translate([-23, -case_h/2-wall-2, fp+8]) cube([46, wall+4, case_d-fp-6]);
    // vents: slots in the top wall + a grille on the back
    if(vent){
      for(i=[-3:3]) translate([i*10, case_h/2-wall-1, fp+6]) cube([4, wall+3, case_d-fp-8]);
      for(ix=[-2:2]) for(iy=[-1:1])
        translate([ix*16, iy*16+8, case_d-1]) cube([4, 11, wall+3], center=true);
    }
  }
}

// ---------- French cleat pair ----------
// 45deg mating faces. Wall half bevels up-and-in; case half bevels down-and-in.
module cleat_bar(flip=false){
  difference(){
    cube([cleat_len, cleat_thick, cleat_h]);
    translate([-1, flip ? -1 : cleat_thick, flip ? cleat_h : 0])
      rotate([flip ? -45 : 45, 0, 0]) cube([cleat_len+2, cleat_h*2, cleat_h*2]);
    for(x=[cleat_len*0.2, cleat_len*0.8])         // screw holes
      translate([x, cleat_thick/2, -1]){ cylinder(h=cleat_h+2, d=4.2); translate([0,0,cleat_h-3]) cylinder(h=4, d1=4.2, d2=8); }
  }
}
module cleat_wall(){ cleat_bar(flip=false); }   // screws to the wall
module cleat_case(){ cleat_bar(flip=true);  }   // bolts to the back_case bosses

// ---------- counter stand ----------
// A wedge whose upright carries a cleat tongue; the display's cleat_case hooks
// onto it, leaning back `stand_lean` degrees. Wide base keeps the big screen stable.
module stand(){
  h = 150;
  // base + back leg as a solid wedge, then a cleat tongue on the upright face
  rotate([0,0,0]){
    // triangular side profile, extruded across a wide base
    linear_extrude(cleat_len+30, center=true)
      polygon([[0,0],[stand_base,0],[0,h]]);
  }
  // cleat tongue (same geometry as cleat_wall) on the near-vertical face,
  // tilted to the lean angle
  translate([6,0,h*0.62])
    rotate([0,stand_lean,0]) translate([0,-cleat_len/2-15, -cleat_h/2])
      rotate([90,0,90]) cleat_wall();
  // lip at the base front so the screen's bottom edge can rest (ports stay clear above it)
  translate([stand_base-8,-(cleat_len+30)/2,0]) cube([8, cleat_len+30, screen_t+8]);
}

// ---------- optional cosmetic front frame (segmented) ----------
// One edge piece; print 2 long (top/bottom, joined at center) + 2 sides, then
// glue/pin at the corners. Overlaps the screen border by `frame_lip`.
module frame_seg(len=seg_len){
  difference(){
    cube([len, frame_face, fp+screen_t+2]);
    translate([-1, frame_lip, fp]) cube([len+2, frame_face, screen_t+4]); // screen sits in here
    // corner alignment-pin holes at each end
    for(x=[6, len-6]) translate([x, frame_face/2, -1]) cylinder(h=fp+3, d=3);
  }
}

// ---------- test coupons ----------
module test_vesa(){ difference(){ cube([vesa+24, vesa+24, fp], center=true);
  for(x=[-vesa/2,vesa/2],y=[-vesa/2,vesa/2]) translate([x,y,-fp]) cylinder(h=fp*3,d=4.5); } }
module test_pi(){ difference(){ translate([0,0,fp/2]) cube([pi_hx+24, pi_hy+24, fp], center=true);
  for(x=[-pi_hx/2,pi_hx/2],y=[-pi_hy/2,pi_hy/2]){ translate([x,y,fp]) cylinder(h=6,d=6);
    translate([x,y,-1]) cylinder(h=10,d=pi_screw-0.2);} } }

// ---------- dispatch ----------
if(part=="back_case")      back_case();
else if(part=="cleat_case") cleat_case();
else if(part=="cleat_wall") cleat_wall();
else if(part=="stand")      stand();
else if(part=="frame_seg")  frame_seg();
else if(part=="test_vesa")  test_vesa();
else if(part=="test_pi")    test_pi();
else if(part=="preview"){ back_case(); translate([0,0,case_d+8]) color("tan") cleat_case(); }

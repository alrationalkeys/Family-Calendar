// ============================================================================
// FamilyHub wall display — parametric mount kit (OpenSCAD)
//
//   * bezel        : a snug frame the touchscreen drops into, front lip overlaps
//                    the screen's black border, rear lip retains it.
//   * cleat_wall   : French-cleat half that screws to the wall.
//   * cleat_frame  : French-cleat half that screws/glues to the bezel back.
//   * stand_foot   : desk/counter easel foot (print TWO) for the "on a stand" look.
//
// HOW TO USE
//   1. Measure your monitor and edit the "YOUR MONITOR" block below.
//   2. Set `part` to the piece you want, or use the Customizer.
//   3. F6 (render) -> Export as STL -> slice -> print.
//
// PRINT NOTES
//   - PLA/PETG both fine. 0.2mm layers, 3 perimeters, 15-20% infill.
//   - Bezel & cleats print flat, face down, no supports needed.
//   - Stand feet print on their flat side; the 45deg back leg is self-supporting.
//   - Print ONE bezel first as a "corner test" (set test_corner=true) to check the
//     fit before committing to the ~10h full frame print.
// ============================================================================

/* [What to render] */
part = "bezel";     // [bezel, cleat_wall, cleat_frame, stand_foot, all_preview]
test_corner = false; // bezel only: print just one corner to test fit fast

/* ======================= YOUR MONITOR (edit these) ======================= */
// Outer dimensions of the whole monitor slab, in millimeters.
mon_w = 360;   // width
mon_h = 230;   // height
mon_t = 11;    // thickness (deepest point incl. any rear bump)

// The black border around the glass on the FRONT. The frame lip overlaps this,
// so keep lip <= the smallest border or you'll cover live pixels.
lip   = 7;

// Ports to cut out of the frame wall. One row per port:
//   [ side, center_position, opening_width, opening_height ]
//   side = "bottom" | "top" | "left" | "right"
//   center_position = distance (mm) from the LEFT edge (for top/bottom)
//                     or from the TOP edge (for left/right) to the port center.
//   Measure to the middle of each connector. Add a couple mm of slack.
ports = [
  ["bottom", 300, 22, mon_t + 4],   // e.g. USB-C (power + touch)
  ["bottom", 260, 22, mon_t + 4],   // e.g. USB-C / HDMI
  ["bottom", 220, 16, mon_t + 4],   // e.g. mini-HDMI
  ["right",  120, 10, 10],          // e.g. power button / wheel
];
/* ========================================================================= */

/* [Fit & frame] */
clear   = 0.5;   // clearance per side around the monitor (loosen if too tight)
wall    = 3.2;   // frame wall thickness
back_lip= 4;     // rear retaining lip that keeps the screen from falling out
corner  = 6;     // outer corner radius
$fn     = 48;

/* [French cleat] */
cleat_len   = 160;  // length of each cleat bar
cleat_h     = 30;   // height of the cleat bar
cleat_thick = 12;   // material thickness of the cleat
cleat_gap   = 2;    // hanging clearance between the two halves

/* [Stand] */
stand_angle = 15;   // lean-back angle from vertical (deg)
stand_depth = 90;   // how far the foot reaches back
stand_wall  = 5;    // foot thickness

// ---- derived ----
cav_w = mon_w + 2*clear;             // inner cavity the monitor sits in
cav_h = mon_h + 2*clear;
cav_t = mon_t + clear;
out_w = cav_w + 2*wall;              // frame outer size
out_h = cav_h + 2*wall;
frame_depth = cav_t + wall;          // front face -> back opening

// rounded rectangle helper
module rrect(w, h, r) {
  hull() for (x=[-1,1], y=[-1,1])
    translate([x*(w/2-r), y*(h/2-r)]) circle(r);
}

// ---------------------------------------------------------------- bezel
module port_cut(p) {
  side = p[0]; pos = p[1]; ow = p[2]; oh = p[3];
  // cut through the wall on the given side; generous depth so it always clears
  d = wall + cav_t + 4;
  if (side=="bottom")
    translate([-out_w/2 + pos, -out_h/2 - 1, wall + clear])
      cube([ow, d, oh]);
  else if (side=="top")
    translate([-out_w/2 + pos, out_h/2 + 1 - d, wall + clear])
      cube([ow, d, oh]);
  else if (side=="left")
    translate([-out_w/2 - 1, out_h/2 - pos - ow, wall + clear])
      cube([d, ow, oh]);
  else if (side=="right")
    translate([out_w/2 + 1 - d, out_h/2 - pos - ow, wall + clear])
      cube([d, ow, oh]);
}

module bezel_full() {
  difference() {
    // outer shell
    linear_extrude(frame_depth) rrect(out_w, out_h, corner);

    // hollow the monitor cavity (open to the back)
    translate([0,0,wall])
      linear_extrude(frame_depth) rrect(cav_w, cav_h, max(1, corner-wall));

    // front viewing window (leaves the `lip` overlap on all sides)
    translate([0,0,-1])
      linear_extrude(wall+2) rrect(cav_w - 2*lip, cav_h - 2*lip, max(1, corner-wall-lip));

    // port cutouts
    for (p = ports) port_cut(p);
  }

  // rear retaining lip: thin inward flange at the very back on top+sides
  // (bottom left open so ports/cables clear and the screen slides in)
  difference() {
    translate([0,0,frame_depth])
      linear_extrude(back_lip) rrect(cav_w + 2*wall, cav_h + 2*wall, corner);
    translate([0,0,frame_depth-1])
      linear_extrude(back_lip+2) rrect(cav_w - 2, cav_h - 2, max(1,corner-wall));
    // leave the bottom edge open
    translate([0, -cav_h/2 - wall, frame_depth-1])
      cube([cav_w+2*wall+2, 2*wall+4, back_lip+4], center=true);
  }
}

// quick corner-only test coupon
module bezel_corner_test() {
  intersection() {
    bezel_full();
    translate([-out_w/2, out_h/2 - 70, -1]) cube([70, 70, frame_depth+back_lip+2]);
  }
}

// ---------------------------------------------------------------- cleats
// A French cleat: two bars with mating 45deg faces. The wall bar's bevel faces
// up-and-in; the frame bar's bevel faces down-and-in so it hooks over.
module cleat_bar(mirror45=false) {
  difference() {
    cube([cleat_len, cleat_thick, cleat_h]);
    // 45deg cut across the thickness
    translate([-1, mirror45 ? -1 : cleat_thick, mirror45 ? cleat_h : 0])
      rotate([mirror45 ? -45 : 45, 0, 0])
        cube([cleat_len+2, cleat_h*2, cleat_h*2]);
    // countersunk screw holes
    for (x = [cleat_len*0.15, cleat_len*0.5, cleat_len*0.85])
      translate([x, cleat_thick/2, -1]) {
        cylinder(h=cleat_h+2, d=4.2);
        translate([0,0,cleat_h-3]) cylinder(h=4, d1=4.2, d2=8);
      }
  }
}
module cleat_wall()  { cleat_bar(mirror45=false); }
module cleat_frame() { cleat_bar(mirror45=true);  }

// ---------------------------------------------------------------- stand
// Easel foot: vertical face the bezel rests against, angled back leg, and a
// bottom lip the frame's lower edge sits into. Print two, one per side.
module stand_foot() {
  h = out_h * 0.55;
  lean = tan(stand_angle);
  linear_extrude(stand_wall)
  polygon([
    [0,0],
    [stand_depth, 0],
    [0, h*0.35],                       // toe / base
    [ -0, 0]
  ]);
  // upright + back leg as a 2D profile, extruded
  linear_extrude(stand_wall)
  polygon([
    [0, 0],
    [0, h],
    [10, h],
    [10 + h*lean, 0]
  ]);
  // bottom retaining lip
  translate([-6, 0, 0]) cube([6, 14, stand_wall + mon_t + clear]);
}

// ---------------------------------------------------------------- dispatch
if (part == "bezel")        { if (test_corner) bezel_corner_test(); else bezel_full(); }
else if (part == "cleat_wall")  cleat_wall();
else if (part == "cleat_frame") cleat_frame();
else if (part == "stand_foot")  stand_foot();
else if (part == "all_preview") {
  bezel_full();
  translate([0, 0, frame_depth+back_lip+10]) { color("tan") cleat_frame(); }
}

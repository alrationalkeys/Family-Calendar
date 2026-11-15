// FamilyHub blind tilt - wand collar test (print second, ~10 min, no supports, 0.2 mm layers).
// A split ring that clamps the top of the wand with one M3 x 12 screw + nut. Wand measured with the gauge:
// too big for the 10 hole, loose in the 11 hole -> about 10.5-11 mm. The slot lets this close down from 11.2 to ~10.2.
// Test: clip it on the wand, tighten until you can twist the wand by turning the ring without it slipping.
$fn = 80;
bore = 11.2;        // open size; the screw squeezes it smaller
wall = 3;
h = 10;
slot = 2;           // gap the screw closes
ear = 8;            // clamp ear length past the ring
od = bore + 2 * wall;
difference() {
  union() {
    cylinder(d = od, h = h);
    translate([0, -(slot / 2 + 3.2), 0]) cube([od / 2 + ear, slot + 6.4, h]);     // clamp ears
  }
  translate([0, 0, -1]) cylinder(d = bore, h = h + 2);
  translate([0, -slot / 2, -1]) cube([od, slot, h + 2]);                           // split
  translate([od / 2 + ear / 2, 0, h / 2]) rotate([90, 0, 0]) {
    cylinder(d = 3.4, h = 30, center = true);                                      // M3 clearance
    translate([0, 0, slot / 2 + 3.2 - 2.4]) cylinder(d = 6.5, h = 5, $fn = 6);     // nut trap
  }
}

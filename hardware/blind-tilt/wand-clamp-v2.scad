// FamilyHub blind tilt - wand clamp test v2 (two halves, two screws). Replaces wand-collar-test.
// v1 was a one-piece split ring: the ears pulled together but the ring itself was too stiff to close, so it slid.
// v2 is two half-shells that are pulled straight onto the wand by an M3 screw on each side, so it clamps no matter
// what: fits a wand from about 10.2 to 11.4 mm. Small ribs inside bite into the wand.
// Print: both halves flat as exported, no supports, 0.2 mm layers, 4 walls. Hardware: 2x M3 x 16 screws + 2x M3 nuts.
$fn = 80;
bore = 10.3;        // a touch under the wand so the halves never meet before they grip
wall = 3.6;
h = 12;
gap = 1.4;          // space left between the halves
ear = 9;            // ear length past the ring
earT = 5.5;         // ear thickness (each half)
rib = 0.35;         // grip ribs inside the bore
od = bore + 2 * wall;
ex = od / 2 + ear / 2 - 0.5;      // screw position

module half() {
  difference() {
    union() {
      cylinder(d = od, h = h);
      translate([-(od / 2 + ear), 0, 0]) cube([od + 2 * ear, earT + gap / 2, h]);
    }
    translate([0, 0, -1]) cylinder(d = bore, h = h + 2);
    translate([-50, -50, -1]) cube([100, 50 + gap / 2, h + 2]);                 // keep one half
    for (s = [-1, 1]) translate([s * ex, 0, h / 2]) rotate([-90, 0, 0]) {
      cylinder(d = 3.5, h = 30);                                                // M3 clearance
      translate([0, 0, gap / 2 + earT - 2.6]) cylinder(d = 6.6, h = 5, $fn = 6); // pocket: nut one side, screw head the other
    }
  }
  for (a = [40, 90, 140]) rotate([0, 0, a]) translate([bore / 2 - rib, -0.6, 0]) cube([rib + 0.3, 1.2, h]);   // grip ribs
}
half();
translate([0, -4, 0]) mirror([0, 1, 0]) half();     // second half, laid out next to the first for printing

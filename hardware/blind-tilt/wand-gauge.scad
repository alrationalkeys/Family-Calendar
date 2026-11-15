// FamilyHub blind tilt - wand fit gauge (print this first, ~15 min, no supports).
// A flat card with round and hex holes. Slide your blind's wand into the holes: the tightest hole it passes through
// is its size. Tell me that number, and whether the round or the hex row fits better.
$fn = 60;
sizes = [7, 8, 9, 10, 11, 12, 13];      // mm
t = 3;                                   // card thickness
pitch = 19;
w = len(sizes) * pitch + 8;
module label(s, x, y) { translate([x, y, t - 0.6]) linear_extrude(0.8) text(str(s), size = 5, halign = "center", valign = "center", font = "Liberation Sans:style=Bold"); }
difference() {
  hull() for (x = [4, w - 4], y = [4, 56]) translate([x, y, 0]) cylinder(r = 4, h = t);
  for (i = [0 : len(sizes) - 1]) {
    x = 4 + pitch / 2 + i * pitch;
    translate([x, 44, -1]) cylinder(d = sizes[i] + 0.3, h = t + 2);                    // round row (diameter)
    translate([x, 17, -1]) cylinder(d = (sizes[i] + 0.3) / cos(30), h = t + 2, $fn = 6); // hex row (flat to flat)
    label(sizes[i], x, 30.5);
  }
}

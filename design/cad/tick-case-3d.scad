// TICK handheld enclosure - 3D model (mm). Two printed parts:
//   BODY  - front shell, open at the back
//   PANEL - flat back plate, screws into the body. Nothing is raised off it
//           and nothing is raised inside the body except the four corner
//           screw bosses, so the cavity is a plain flat box.
//
// Coordinates: x = 0 left .. 104 right (seen from the front)
//              y = 0 bottom .. 110 top
//              z = 0 back .. 40 front face
//
// VIEW = "assembly" | "exploded" | "body" | "panel" | "four"
VIEW = "assembly";

$fn = 40;

// ---- dimensions (same numbers as the rev C review drawing) ---------------
W = 104; H = 110; D = 40; WALL = 2.5; FILLET = 3;

MOD_W = 92; MOD_H = 60; MOD_T = 3;      // screen module, and its seat depth
VIS_W = 79; VIS_H = 49;                 // visible image = the front window
BEZEL_S = 6; BEZEL_T = 6;
GRIP_H = H - BEZEL_T - MOD_H;           // 44

BTN = 13; BTN_GAP = 26; BTN_CY = 88;    // square buttons, from the top
ENC = 12; ENC_CY = 88; ENC_CZ = D/2;    // encoder square, right wall, on the button line
USB_W = 60; USB_D = 14;                 // bottom slot: USB-C + both HDMI
TOP_W = 44; TOP_D = 22; TOP_EDGE = 5;   // wide corner opening in the top
TOP_CX = W - TOP_EDGE - TOP_W/2;

SCREW_IN = 6; BOSS_R = 4.2; BOSS_H = 9; PILOT = 2.5;
PANEL_T = 2.5;
PI_W = 85; PI_H = 56; PI_HX = 58; PI_HY = 49; PI_EDGE = 3.5;
CLEAR = 0.3;                            // print clearance added to every hole

// ---- helpers -------------------------------------------------------------
module rounded_box(w, h, d, r) {
    hull() for (x = [r, w-r], y = [r, h-r], z = [r, d-r])
        translate([x, y, z]) sphere(r = r);
}
// A square hole with print clearance, cut along +z from the given face
module hole(w, h) { translate([-CLEAR/2, -CLEAR/2, 0]) cube([w+CLEAR, h+CLEAR, 60]); }

// ---- BODY ----------------------------------------------------------------
module body() {
    difference() {
        rounded_box(W, H, D, FILLET);

        // cavity, open at the back (z = 0)
        translate([WALL, WALL, -1]) cube([W-2*WALL, H-2*WALL, D-WALL+1]);

        // screen window through the front wall
        translate([BEZEL_S + (MOD_W-VIS_W)/2, GRIP_H + (MOD_H-VIS_H)/2, D-WALL-1])
            cube([VIS_W, VIS_H, WALL+2]);
        // buttons
        for (dx = [-BTN_GAP/2, BTN_GAP/2])
            translate([W/2+dx-BTN/2, H-BTN_CY-BTN/2, D-WALL-1]) hole(BTN, BTN);

        // encoder, through the right wall
        translate([W-WALL-1, H-ENC_CY-ENC/2, ENC_CZ-ENC/2])
            rotate([0, 90, 0]) translate([-ENC, 0, 0]) cube([ENC+CLEAR, ENC+CLEAR, WALL+2]);

        // wide opening in the top face, right corner
        translate([TOP_CX-TOP_W/2, H-WALL-1, D/2-TOP_D/2]) cube([TOP_W, WALL+2, TOP_D]);

        // USB-C + micro-HDMI slot in the bottom face
        translate([W/2-USB_W/2, -1, D/2-USB_D/2]) cube([USB_W, WALL+2, USB_D]);
    }
    // corner bosses for the back-panel screws
    for (x = [SCREW_IN, W-SCREW_IN], y = [SCREW_IN, H-SCREW_IN])
        translate([x, y, 0]) difference() {
            cylinder(r = BOSS_R, h = BOSS_H);
            translate([0, 0, 1.5]) cylinder(r = PILOT/2, h = BOSS_H);
        }
}

// ---- BACK PANEL ----------------------------------------------------------
module panel() {
    difference() {
        // flat plate, nothing raised off it
        hull() for (x = [FILLET, W-FILLET], y = [FILLET, H-FILLET])
            translate([x, y, 0]) cylinder(r = FILLET, h = PANEL_T);
        // speaker grille
        for (c = [0:8], r = [0:6])
            translate([(W-59)/2 + c*7, (H-32)/2 + 4 + r*5, -1]) cube([3, 2.2, PANEL_T+2]);
        // screw holes
        for (x = [SCREW_IN, W-SCREW_IN], y = [SCREW_IN, H-SCREW_IN])
            translate([x, y, -1]) cylinder(r = 1.7, h = PANEL_T+2);
    }
}

// ---- mock parts, so the pictures show what goes where --------------------
module mock_screen() {
    color("#15181c") translate([BEZEL_S, GRIP_H, D-WALL-MOD_T]) cube([MOD_W, MOD_H, MOD_T]);
    color("#3d8fd0") translate([BEZEL_S+(MOD_W-VIS_W)/2, GRIP_H+(MOD_H-VIS_H)/2, D-WALL-0.2])
        cube([VIS_W, VIS_H, 0.8]);
}
module mock_buttons() {
    cols = ["#d8382c", "#e8b219"];
    for (i = [0, 1]) {
        dx = (i == 0 ? -BTN_GAP/2 : BTN_GAP/2);
        color(cols[i]) translate([W/2+dx, H-BTN_CY, D-WALL-2]) cylinder(r = 7.6, h = 6.5);
    }
}
module mock_encoder() {
    color("#1d3f2a") translate([W-WALL-3, H-ENC_CY-13, ENC_CZ-9.5]) cube([3, 26, 19]);
    color("#9aa3a8") translate([W-WALL, H-ENC_CY, ENC_CZ]) rotate([0, 90, 0]) cylinder(r = 3, h = 14);
}
module mock_pi() {
    color("#1b5e3a") translate([(W-PI_W)/2, 18, PANEL_T]) cube([PI_W, PI_H, 1.6]);
    color("#6b7176") translate([(W-PI_W)/2+10, 18, PANEL_T+1.6]) cube([60, 14, 13]);
}

// ---- views ---------------------------------------------------------------
module assembly() {
    color("#e9e6de") body();
    mock_screen(); mock_buttons(); mock_encoder();
    color("#d9d5cc") panel();
    mock_pi();
}
module exploded() {
    color("#e9e6de") body();
    mock_screen(); mock_buttons(); mock_encoder();
    translate([0, -78, -30]) { color("#d9d5cc") panel(); mock_pi(); }
}

// spin the model rather than the camera: the gimbal makes a true back view awkward
module turned() { translate([W, 0, D]) rotate([0, 180, 0]) assembly(); }

if (VIEW == "assembly") assembly();
else if (VIEW == "back") turned();
else if (VIEW == "exploded") exploded();
else if (VIEW == "body") color("#e9e6de") body();
else if (VIEW == "panel") { color("#d9d5cc") panel(); }
else if (VIEW == "four") {
    for (i = [0:3]) translate([i*150, 0, 0])
        translate([W/2, H/2, D/2]) rotate([0, 0, i*90]) translate([-W/2, -H/2, -D/2]) assembly();
}

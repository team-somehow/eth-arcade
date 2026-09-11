// TICK handheld - dimensioned 2D review drawing, rev C (all values in mm)
// Six orthographic views. This is the review sheet; the 3D model follows.

// ---- overall -------------------------------------------------------------
W       = 104;   // overall width of the front face
H       = 110;   // overall height of the front face
D       = 40;    // overall depth
WALL    = 2.5;   // shell wall thickness

// ---- screen --------------------------------------------------------------
MOD_W   = 92;    // module including its black bezel
MOD_H   = 60;
VIS_W   = 79;    // visible image, measured off the running panel
VIS_H   = 49;
BEZEL_T = 6;     // face above the module
BEZEL_S = 6;     // face each side of the module
GRIP_H  = H - BEZEL_T - MOD_H;   // 44 of face below the screen

// ---- controls ------------------------------------------------------------
BTN     = 13;    // square button holes
BTN_GAP = 26;    // centre to centre
BTN_CY  = 88;    // button centre, from the top of the face
ENC     = 12;    // square encoder hole, right side face
ENC_CY  = 88;    // encoder centre from the top - on the button line
ENC_CZ  = D/2;   // encoder centre through the depth

// ---- openings ------------------------------------------------------------
// Bottom slot is sized to clear the USB-C AND both micro-HDMI sockets, which
// sit on the same edge of the Pi 5. Wide on purpose: position stops mattering.

// Wide opening in the top face, at its right-hand corner.
TOP_W   = 28;
TOP_D   = 14;
TOP_EDGE = 5;                    // gap left to the right-hand edge
TOP_CX  = W - TOP_EDGE - TOP_W/2;

// ---- back panel ----------------------------------------------------------
SCREW    = 3.2;  // M3 clearance
SCREW_IN = 6;    // screw centres, in from each corner
PI_W = 85; PI_H = 56;            // Raspberry Pi 5 board
PI_HX = 58; PI_HY = 49;          // its mounting hole spacing
PI_EDGE = 3.5;                   // holes in from the board edge
GRILLE_COLS = 9; GRILLE_ROWS = 7; SLOT_W = 3; SLOT_H = 2.2; SLOT_GX = 7; SLOT_GY = 5;

// ---- drawing helpers -----------------------------------------------------
LW = 0.4;
module line(p1, p2, t = LW) {
    d = p2 - p1; a = atan2(d[1], d[0]);
    translate(p1) rotate(a) translate([0, -t/2]) square([norm(d), t]);
}
module frame(w, h, t = LW) {
    difference() { square([w, h]); translate([t, t]) square([w-2*t, h-2*t]); }
}
module ring(r, t = LW) { difference() { circle(r); circle(r - t); } }
module dashed(p1, p2, dash = 2) {
    d = p2 - p1; L = norm(d); n = floor(L / (dash*2));
    for (i = [0:n]) line(p1 + d*(i*2*dash)/L, p1 + d*min(L, (i*2+1)*dash)/L, 0.3);
}
module dbox(w, h) {
    dashed([0,0],[w,0]); dashed([w,0],[w,h]); dashed([w,h],[0,h]); dashed([0,h],[0,0]);
}
module tick(p, vertical = false) {
    translate(p) rotate(vertical ? 90 : 0) translate([-0.2, -1.6]) square([0.4, 3.2]);
}
module dim_h(x1, x2, y, label, size = 3.4) {
    line([x1, y], [x2, y]); tick([x1, y], true); tick([x2, y], true);
    translate([(x1+x2)/2, y + 1.4]) text(label, size = size, halign = "center");
}
module dim_v(y1, y2, x, label, size = 3.4) {
    line([x, y1], [x, y2]); tick([x, y1]); tick([x, y2]);
    translate([x + 1.6, (y1+y2)/2 - size/2]) text(label, size = size);
}
module note(p, txt, size = 3.2) { translate(p) text(txt, size = size); }
module title(p, txt) { translate(p) text(txt, size = 5.5); }

// ---- 1 FRONT -------------------------------------------------------------
module view_front() {
    frame(W, H, 0.6);
    translate([BEZEL_S, GRIP_H]) frame(MOD_W, MOD_H);                       // module
    translate([BEZEL_S + (MOD_W-VIS_W)/2, GRIP_H + (MOD_H-VIS_H)/2])        // window
        frame(VIS_W, VIS_H, 0.6);
    for (dx = [-BTN_GAP/2, BTN_GAP/2])
        translate([W/2 + dx - BTN/2, H - BTN_CY - BTN/2]) frame(BTN, BTN, 0.6);

    dim_h(0, W, -9, str(W, "  overall width"));
    dim_h(BEZEL_S, BEZEL_S + MOD_W, H + 5, str(MOD_W, "  screen module"));
    dim_h(0, BEZEL_S, H + 13, str(BEZEL_S));
    dim_h(W - BEZEL_S, W, H + 13, str(BEZEL_S));
    dim_v(0, H, W + 9, str(H, "  overall height"));
    dim_v(H - BEZEL_T, H, W + 33, str(BEZEL_T, " bezel"));
    dim_v(GRIP_H, GRIP_H + MOD_H, W + 33, str(MOD_H, " screen"));
    dim_v(0, GRIP_H, W + 33, str(GRIP_H, " grip"));
    dim_v(H - BTN_CY, H, -20, str(BTN_CY, " to btn"));
    dim_h(W/2 - BTN_GAP/2, W/2 + BTN_GAP/2, H - BTN_CY - 13, str(BTN_GAP, " ctc"));
    note([W/2 - 27, H - BTN_CY - 25], str(BTN, " x ", BTN, " square buttons"), 3);
    note([BEZEL_S + 3, GRIP_H + MOD_H - 8], str(VIS_W, " x ", VIS_H, " window"), 3);
    title([0, H + 25], "1  FRONT");
}

// ---- 2 BACK --------------------------------------------------------------
module view_back() {
    frame(W, H, 0.6);
    gw = (GRILLE_COLS-1)*SLOT_GX + SLOT_W; gh = (GRILLE_ROWS-1)*SLOT_GY + SLOT_H;
    translate([(W - gw)/2, (H - gh)/2 + 4]) {
        for (c = [0:GRILLE_COLS-1], r = [0:GRILLE_ROWS-1])
            translate([c*SLOT_GX, r*SLOT_GY]) square([SLOT_W, SLOT_H]);
        dim_h(0, gw, -10, str(gw, " x ", gh, " grille"));
    }
    // Pi 5 board and its four mounting holes, seen through the back
    translate([(W - PI_W)/2, 14]) {
        dbox(PI_W, PI_H);
        for (hx = [PI_EDGE, PI_EDGE + PI_HX], hy = [PI_EDGE, PI_EDGE + PI_HY])
            translate([hx, hy]) ring(1.3, 0.4);
    }
    dim_h(0, W, H + 5, str(W));
    dim_v(0, H, W + 9, str(H));
    note([(W-PI_W)/2, 8], str("Pi 5 ", PI_W, " x ", PI_H, " sits loose on the flat lid"), 2.9);
    note([6, H - 12], "lid - presses on, no screws", 2.9);
    title([0, H + 25], "2  BACK  (lid)");
}

// ---- 3 LEFT --------------------------------------------------------------
module view_left() {
    frame(D, H, 0.6);
    dim_h(0, D, -9, str(D, " depth"));
    dim_v(0, H, D + 9, str(H));
    note([D + 15, H/2 - 16], "no openings -", 3);
    note([D + 15, H/2 - 22], "this face is solid", 3);
    title([0, H + 25], "3  LEFT");
}

// ---- 4 RIGHT -------------------------------------------------------------
module view_right() {
    frame(D, H, 0.6);
    translate([ENC_CZ - ENC/2, H - ENC_CY - ENC/2]) frame(ENC, ENC, 0.6);
    dim_h(0, D, -9, str(D, " depth"));
    dim_v(H - ENC_CY, H, D + 9, str(ENC_CY, " to centre"));
    dim_h(ENC_CZ - ENC/2, ENC_CZ + ENC/2, H - ENC_CY + 11, str(ENC));
    dim_h(0, ENC_CZ, -17, str(ENC_CZ, " to centre"));
    note([D + 9, H - ENC_CY - 26], str(ENC, " x ", ENC, " square,"), 3);
    note([D + 9, H - ENC_CY - 32], "rotary encoder shaft", 3);
    title([0, H + 25], "4  RIGHT");
}

// ---- 5 TOP ---------------------------------------------------------------
module view_top() {
    frame(W, D, 0.6);
    translate([TOP_CX - TOP_W/2, (D - TOP_D)/2]) frame(TOP_W, TOP_D, 0.6);
    dim_h(0, W, -9, str(W));
    dim_h(TOP_CX - TOP_W/2, TOP_CX + TOP_W/2, D + 5, str(TOP_W, " wide"));
    dim_h(TOP_CX + TOP_W/2, W, D + 13, str(TOP_EDGE));
    dim_v((D - TOP_D)/2, (D + TOP_D)/2, W + 9, str(TOP_D));
    note([2, D + 22], "wide corner opening - cable exit / venting", 3);
    title([0, D + 30], "5  TOP");
}

// ---- 6 BOTTOM ------------------------------------------------------------
module view_bottom() {
    frame(W, D, 0.6);
    dim_h(0, W, -9, str(W));
    dim_v(0, D, W + 9, str(D, " depth"));
    note([2, D + 22], "solid - no openings. The cable leaves through the TOP.", 3);
    title([0, D + 30], "6  BOTTOM");
}

// ---- sheet ---------------------------------------------------------------
translate([0,   250]) view_front();
translate([200, 250]) view_back();
translate([400, 250]) view_left();
translate([520, 250]) view_right();
translate([0,   140]) view_top();
translate([200, 140]) view_bottom();

translate([0, 410]) title([0, 0], "TICK handheld enclosure - all six faces - rev C");
translate([0, 398]) note([0, 0], str("overall ", W, " W x ", H, " H x ", D, " D   |   wall ", WALL, "   |   all dimensions mm   |   for approval before the 3D model"), 4);

translate([0, 100]) note([0, 0], "DECIDED (was open, now fixed - say so if any of these are wrong)", 4.2);
translate([0, 92]) note([0, 0], "A. Bottom face is solid. The USB-C cable leaves via the top opening, so the Pi must sit with its USB-C edge facing the TOP.", 3.4);
translate([0, 84]) note([0, 0], str("B. Top opening ", TOP_W, " x ", TOP_D, " in the right corner, ", TOP_EDGE, " from the edge - cable exit, and it vents the hot side of the Pi."), 3.4);
translate([0, 76]) note([0, 0], str("C. Encoder centre ", ENC_CY, " down the right face, centred through the depth at ", ENC_CZ, "."), 3.4);
translate([0, 68]) note([0, 0], "D. Left face solid, and both interiors are completely flat - no standoffs, no bosses, nothing to locate parts. Tape or foam at assembly.", 3.4);
translate([0, 60]) note([0, 0], "E. Two parts, no screws: a deep front body and a shallow back lid, pressed together on a 5mm tongue-and-socket lip (0.15 clearance per side).", 3.4);

translate([0, 44]) note([0, 0], "STILL UNVERIFIED BY YOU", 4.2);
translate([0, 36]) note([0, 0], str("1. Screen module ", MOD_W, " x ", MOD_H, " - everything keys off this. Worth one caliper check: 2mm out and the panel either rattles or will not drop in."), 3.4);
translate([0, 28]) note([0, 0], "2. Window assumes the 79 x 49 image is centred in the module bezel. If yours is offset, the window sits crooked over the picture.", 3.4);
translate([0, 20]) note([0, 0], "3. Pi 5 orientation: USB-C edge must face DOWN for note A to hold. That puts USB-A and Ethernet on a long edge - currently enclosed.", 3.4);

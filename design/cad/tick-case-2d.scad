// TICK handheld - dimensioned 2D review drawing (all values in mm)
// Renders four orthographic views. Nothing here is the 3D model yet.

// ---- agreed dimensions ----------------------------------------------------
W       = 104;   // overall width of the front face
H       = 110;   // overall height of the front face
D       = 40;    // overall depth
WALL    = 2.5;   // shell wall thickness
BEZEL_T = 6;     // bezel above the screen module
BEZEL_S = 6;     // bezel each side
MOD_W   = 92;    // screen module, bezel included
MOD_H   = 60;
VIS_W   = 79;    // visible image area (measured off the running panel)
VIS_H   = 49;
GRIP_H  = H - BEZEL_T - MOD_H;   // 44mm of face below the screen
BTN     = 13;    // square button holes
BTN_GAP = 26;    // centre-to-centre spacing of the two buttons
BTN_CY  = BEZEL_T + MOD_H + 22;  // button centre, measured from the top
ENC     = 12;    // square encoder hole in the right side face
ENC_CY  = 46;    // encoder centre from the top
ENC_CZ  = D/2;   // encoder centre through the depth
// USB-C now exits the BOTTOM face, deliberately oversized so the connector
// cannot miss it whichever way the Pi ends up sitting.
USB_W   = 40;
USB_D   = 12;
USB_CX  = W/2;                   // centred across the bottom face
// Wide opening in the TOP face, at its right-hand corner.
TOP_W   = 34;
TOP_D   = 16;
TOP_CX  = W - 6 - TOP_W/2;
PI_W    = 85;    // Raspberry Pi 5 board
PI_H    = 56;

// ---- drawing helpers ------------------------------------------------------
LW = 0.4;
module line(p1, p2, t = LW) {
    d = p2 - p1; a = atan2(d[1], d[0]);
    translate(p1) rotate(a) translate([0, -t/2]) square([norm(d), t]);
}
module frame(w, h, t = LW) {
    difference() { square([w, h]); translate([t, t]) square([w-2*t, h-2*t]); }
}
module dashed(p1, p2, dash = 2) {
    d = p2 - p1; n = floor(norm(d) / (dash*2));
    for (i = [0:n]) {
        a = p1 + d * (i*2*dash) / norm(d);
        b = p1 + d * min(norm(d), (i*2+1)*dash) / norm(d);
        line(a, b, 0.3);
    }
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

// ---- FRONT ----------------------------------------------------------------
module view_front() {
    frame(W, H, 0.6);
    // screen module, then the visible image inside it
    translate([BEZEL_S, GRIP_H]) frame(MOD_W, MOD_H);
    translate([BEZEL_S + (MOD_W-VIS_W)/2, GRIP_H + (MOD_H-VIS_H)/2]) frame(VIS_W, VIS_H);
    // buttons, measured from the top of the face
    for (dx = [-BTN_GAP/2, BTN_GAP/2])
        translate([W/2 + dx - BTN/2, H - BTN_CY - BTN/2]) frame(BTN, BTN);
    // the Pi board behind the face, for clearance
    PY0 = 40;
    translate([(W-PI_W)/2, PY0]) dashed([0,0],[PI_W,0]);
    translate([(W-PI_W)/2, PY0]) dashed([0,0],[0,PI_H]);
    translate([(W-PI_W)/2, PY0+PI_H]) dashed([0,0],[PI_W,0]);
    translate([(W-PI_W)/2+PI_W, PY0]) dashed([0,0],[0,PI_H]);
    note([(W-PI_W)/2 + 3, PY0 + 3], "Pi 5  85 x 56 (behind)", 2.8);

    dim_h(0, W, -8, str(W, " overall width"));
    dim_h(BEZEL_S, BEZEL_S+MOD_W, H+5, str(MOD_W, " screen module"));
    dim_h(0, BEZEL_S, H+13, str(BEZEL_S));
    dim_h(W-BEZEL_S, W, H+13, str(BEZEL_S));
    dim_v(0, H, W+8, str(H, " overall height"));
    dim_v(H-BEZEL_T, H, W+30, str(BEZEL_T, " bezel"));
    dim_v(GRIP_H, GRIP_H+MOD_H, W+48, str(MOD_H, " screen"));
    dim_v(0, GRIP_H, W+30, str(GRIP_H, " grip"));
    dim_v(H-BTN_CY, H, -26, str(BTN_CY));
    dim_h(W/2-BTN_GAP/2, W/2+BTN_GAP/2, H-BTN_CY-12, str(BTN_GAP, " ctc"));
    note([W/2 - 26, H - BTN_CY - 24], str(BTN, " x ", BTN, " square buttons"), 3);
    note([BEZEL_S + 9, GRIP_H + MOD_H - 9], str(VIS_W, " x ", VIS_H, " visible image"), 3);
    title([0, H + 24], "FRONT");
}

// ---- RIGHT SIDE -----------------------------------------------------------
module view_side() {
    frame(D, H, 0.6);
    translate([ENC_CZ - ENC/2, H - ENC_CY - ENC/2]) frame(ENC, ENC);
    dim_h(0, D, -8, str(D, " depth"));
    dim_v(H - ENC_CY - ENC/2, H, D + 8, str(ENC_CY, " to centre"));
    dim_h(ENC_CZ - ENC/2, ENC_CZ + ENC/2, H - ENC_CY + 12, str(ENC));
    note([D + 8, H - ENC_CY - 16], str(ENC, " x ", ENC, " square"), 3);
    note([D + 8, H - ENC_CY - 22], "hole for rotary encoder", 3);
    title([0, H + 24], "RIGHT SIDE");
}

// ---- BACK -----------------------------------------------------------------
GRILLE_ROWS = 7; GRILLE_COLS = 9; SLOT_W = 3; SLOT_H = 12; SLOT_GX = 7; SLOT_GY = 5;
module view_back() {
    frame(W, H, 0.6);
    gw = GRILLE_COLS * SLOT_GX; gh = GRILLE_ROWS * SLOT_GY;
    translate([(W - gw)/2, (H - gh)/2 - 6]) {
        for (c = [0:GRILLE_COLS-1]) for (r = [0:GRILLE_ROWS-1])
            translate([c*SLOT_GX, r*SLOT_GY]) square([SLOT_W, 2.2]);
        dim_h(0, gw, -8, str(round(gw), " grille"));
    }
    note([6, 8], "back panel, screwed on", 3);
    title([0, H + 24], "BACK  (speaker grille)");
}

// ---- TOP ------------------------------------------------------------------
module view_top() {
    frame(W, D, 0.6);
    translate([TOP_CX - TOP_W/2, (D - TOP_D)/2]) frame(TOP_W, TOP_D);
    dim_h(0, W, -8, str(W));
    dim_h(TOP_CX - TOP_W/2, W, D + 5, str(TOP_W + 6, " from right edge"));
    dim_h(TOP_CX - TOP_W/2, TOP_CX + TOP_W/2, D + 13, str(TOP_W));
    dim_v((D-TOP_D)/2, (D+TOP_D)/2, W + 8, str(TOP_D));
    note([4, D + 22], "wide opening, TOP RIGHT corner - purpose/size to confirm", 3);
    title([0, D + 30], "TOP");
}

// ---- BOTTOM ---------------------------------------------------------------
module view_bottom() {
    frame(W, D, 0.6);
    translate([USB_CX - USB_W/2, (D - USB_D)/2]) frame(USB_W, USB_D);
    dim_h(0, W, -8, str(W));
    dim_h(USB_CX - USB_W/2, USB_CX + USB_W/2, D + 5, str(USB_W, " wide USB-C slot"));
    dim_v((D-USB_D)/2, (D+USB_D)/2, W + 8, str(USB_D));
    note([4, D + 14], "oversized on purpose - cable boot clears, position forgiving", 3);
    title([0, D + 22], "BOTTOM  (USB-C)");
}

// ---- sheet ----------------------------------------------------------------
translate([0, 210])    view_front();
translate([200, 210])  view_side();
translate([0, 114])    view_top();
translate([0, 50])     view_bottom();
translate([200, 40])   view_back();

translate([0, 380]) title([0, 0], "TICK handheld - dimensioned review drawing  rev B");
translate([0, 368]) note([0, 0], "all dimensions in mm - review only, the 3D model comes after you approve", 4);
translate([0, 358]) note([0, 0], str("overall ", W, " W x ", H, " H x ", D, " D   |   shell wall ", WALL), 4);
translate([0, 22])  note([0, 0], "NOTES", 4.5);
translate([0, 14])  note([0, 0], "1. Screen module 92 x 60 (bezel included) sits behind the front face; opening exposes the 79 x 49 visible image only.", 3.4);
translate([0, 6])   note([0, 0], "2. Openings are on TOP (right corner), RIGHT (encoder) and BOTTOM (USB-C), per your note.", 3.4);
translate([0, -2])  note([0, 0], "3. USB-C slot is 40 x 12 - far larger than the connector, so the Pi's exact position inside does not matter.", 3.4);
translate([0, -10]) note([0, 0], "4. TOP RIGHT opening 34 x 16 is a placeholder - tell me what passes through it and I will size it properly.", 3.4);
translate([0, -18]) note([0, 0], "5. Encoder hole 12 x 12 in the RIGHT side face. Height and depth position still ASSUMED.", 3.4);
translate([0, -26]) note([0, 0], "6. Speaker grille on the BACK face only. No speaker fitted yet - the Pi 5 has no analog audio out.", 3.4);
translate([0, -34]) note([0, 0], "7. Buttons are 13 x 13 square holes, 26 centre-to-centre, centres 88 from the top.", 3.4);

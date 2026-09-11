# Device flow: Arc testnet, 2026-09-11

The firmware's real-funds path (`TICK_FUNDING=arc-testnet`, `firmware/arc.py`) run end to end against Arc testnet with the real device key, without the screen: the same deposit watcher, `openFor` and `close` the game uses.

- Escrow: [`0x4FA3D366A08aD06D60A0aB141FFb9981EDeE8627`](https://testnet.arcscan.app/address/0x4FA3D366A08aD06D60A0aB141FFb9981EDeE8627)
- Player (and house owner): [`0x7ee85B080701330bf53Be62B7E72fcDD034eCCac`](https://testnet.arcscan.app/address/0x7ee85B080701330bf53Be62B7E72fcDD034eCCac)
- Device: [`0x3E0A93BDaA49710f4052B6e17A4Ac2b3f2f6562E`](https://testnet.arcscan.app/address/0x3E0A93BDaA49710f4052B6e17A4Ac2b3f2f6562E)

| Step | What | Status | Tx |
|---|---|---|---|
| Deposit | Player sends the device 0.05 USDC as a native send (what MetaMask's send screen does) | success | [`0xfff4…79f9`](https://testnet.arcscan.app/tx/0xfff4ea8c3a983b718b0606f54061acb1ec1ca71bfa5926a1a58583d668d779f9) |
| Open | Device sees the transfer, keeps 0.01 for gas, approves the escrow once and calls `openFor`: session 1, 0.04 in the player's name, 0.16 reserved | success, 8.4 s after the deposit | [`0x24f3…c0ec`](https://testnet.arcscan.app/tx/0x24f3990c01acc45b0e23462b346b0c249d090bd77f5c6c47ddb82102d92cc0ec) |
| Close | Device closes at 0.045 (a 0.005 win); the escrow pays the player directly | success | [`0x97c9…bfaf`](https://testnet.arcscan.app/tx/0x97c982d75198b90af0f29a7cc1e05a49e7283e06c28c851d5e8724078f04bfaf) |

## After

| | |
|---|---|
| Player USDC | 29.790958 → 29.785433: −0.05 sent, +0.045 paid back, −0.000525 gas |
| Device USDC | 0.002000 → 0.005018: +0.01 fee, −0.006982 gas for approve, open and close |
| Session 1 open | false |

**PASS**: the session was opened in the sender's name, and the cash-out went straight from the escrow to the address the USDC came from.

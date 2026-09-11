// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {Script, console} from "forge-std/Script.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {TickEscrow} from "../src/TickEscrow.sol";

/// Deploys TickEscrow owned by the deployer.
///
/// It makes no USDC calls: Arc's USDC checks an Arc-only precompile on every
/// transfer, which Foundry's local simulation does not have, so a transfer here
/// would fail before broadcast. Fund the house with smoke.sh or cast instead.
///
///   forge script script/Deploy.s.sol --rpc-url arc_testnet --broadcast
contract Deploy is Script {
    function run() external returns (TickEscrow book) {
        uint256 key = vm.envUint("ARC_DEPLOYER_KEY");
        IERC20 usdc = IERC20(vm.envOr("USDC", address(0x3600000000000000000000000000000000000000)));

        vm.startBroadcast(key);
        book = new TickEscrow(usdc, vm.addr(key));
        vm.stopBroadcast();

        console.log("TickEscrow:", address(book));
    }
}

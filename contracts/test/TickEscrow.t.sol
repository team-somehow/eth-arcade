// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {Test} from "forge-std/Test.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {TickEscrow} from "../src/TickEscrow.sol";
import {MockUSDC} from "./mocks/MockUSDC.sol";

/// This test contract is the owner, and so the house.
contract TickEscrowTest is Test {
    uint256 constant USDC = 1e6;

    MockUSDC usdc;
    TickEscrow book;
    address player = makeAddr("player");
    address relayer = makeAddr("relayer");
    address stranger = makeAddr("stranger");
    uint256 devicePk = 0xDE71CE;
    address device;
    address player2 = makeAddr("player2");
    uint256 device2Pk = 0xB0B;
    address device2;

    function setUp() public {
        usdc = new MockUSDC();
        book = new TickEscrow(usdc, address(this));
        device = vm.addr(devicePk);
        device2 = vm.addr(device2Pk);
        usdc.mint(address(this), 1_000 * USDC);
        usdc.mint(player, 100 * USDC);
        usdc.mint(player2, 100 * USDC);
        usdc.approve(address(book), type(uint256).max);
        vm.prank(player);
        usdc.approve(address(book), type(uint256).max);
        vm.prank(player2);
        usdc.approve(address(book), type(uint256).max);
        book.fund(100 * USDC);
    }

    function _open(uint256 amount) internal returns (uint256) {
        vm.prank(player);
        return book.open(amount, device);
    }

    function _open2(uint256 amount) internal returns (uint256) {
        vm.prank(player2);
        return book.open(amount, device2);
    }

    function _sign(uint256 id, uint256 finalBalance) internal view returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(devicePk, book.closeDigest(id, finalBalance));
        return abi.encodePacked(r, s, v);
    }

    // ---- opening -----------------------------------------------------------

    function test_OpenReservesHouseMoney() public {
        _open(10 * USDC);
        assertEq(book.houseBalance(), 100 * USDC, "player deposit is not house money");
        assertEq(book.playerFunds(), 10 * USDC);
        assertEq(book.reserved(), 40 * USDC);
        assertEq(book.freeHouse(), 60 * USDC);
        assertEq(book.openSessions(), 1);
    }

    function test_OpenRevertsWhenHouseTooSmall() public {
        vm.prank(player);
        vm.expectRevert(TickEscrow.HouseTooSmall.selector);
        book.open(26 * USDC, device); // would reserve 104 of 100
    }

    function test_ConcurrentSessionsShareTheHouse() public {
        _open(20 * USDC); // reserves 80
        vm.prank(player);
        vm.expectRevert(TickEscrow.HouseTooSmall.selector);
        book.open(6 * USDC, device); // would reserve 24 of the 20 left
        _open(5 * USDC);
        assertEq(book.freeHouse(), 0);
    }

    function test_OpenRevertsOverMaxDeposit() public {
        book.setLimits(5 * USDC, 40_000, 1 days);
        vm.prank(player);
        vm.expectRevert(TickEscrow.BadAmount.selector);
        book.open(6 * USDC, device);
    }

    function test_PauseStopsNewSessionsButNotCloses() public {
        uint256 id = _open(10 * USDC);
        book.setPaused(true);
        vm.prank(player);
        vm.expectRevert(TickEscrow.IsPaused.selector);
        book.open(10 * USDC, device);
        vm.prank(device);
        book.close(id, 10 * USDC);
        assertEq(book.openSessions(), 0);
    }

    // ---- closing -----------------------------------------------------------

    function test_LossGoesToHouse() public {
        uint256 id = _open(10 * USDC);
        vm.prank(device);
        book.close(id, 4 * USDC);
        assertEq(usdc.balanceOf(player), 94 * USDC);
        assertEq(book.houseBalance(), 106 * USDC);
        assertEq(book.reserved(), 0);
        assertEq(book.playerFunds(), 0);
        assertEq(book.openSessions(), 0);
    }

    function test_WinPaidByHouse() public {
        uint256 id = _open(10 * USDC);
        vm.prank(device);
        book.close(id, 30 * USDC);
        assertEq(usdc.balanceOf(player), 120 * USDC);
        assertEq(book.houseBalance(), 80 * USDC);
    }

    function test_WinIsCapped() public {
        uint256 id = _open(10 * USDC);
        vm.prank(device);
        book.close(id, 1_000 * USDC);
        assertEq(usdc.balanceOf(player), 140 * USDC, "deposit + 4x reserve");
        assertEq(book.houseBalance(), 60 * USDC);
    }

    function test_OnlyDeviceCanClose() public {
        uint256 id = _open(10 * USDC);
        vm.prank(player);
        vm.expectRevert(TickEscrow.NotDevice.selector);
        book.close(id, 50 * USDC);
        vm.expectRevert(TickEscrow.NotDevice.selector);
        book.close(id, 0); // the house cannot close either
    }

    function test_CloseWithSigFromRelayer() public {
        uint256 id = _open(10 * USDC);
        bytes memory sig = _sign(id, 12 * USDC);
        vm.prank(relayer);
        book.closeWithSig(id, 12 * USDC, sig);
        assertEq(usdc.balanceOf(player), 102 * USDC);
        assertEq(usdc.balanceOf(relayer), 0);
    }

    function test_SignatureBindsTheBalance() public {
        uint256 id = _open(10 * USDC);
        bytes memory sig = _sign(id, 12 * USDC);
        vm.expectRevert(TickEscrow.BadSignature.selector);
        book.closeWithSig(id, 50 * USDC, sig);
    }

    function test_CannotCloseTwice() public {
        uint256 id = _open(10 * USDC);
        bytes memory sig = _sign(id, 12 * USDC);
        book.closeWithSig(id, 12 * USDC, sig);
        vm.expectRevert(TickEscrow.NotOpen.selector);
        book.closeWithSig(id, 12 * USDC, sig);
    }

    // ---- several players ---------------------------------------------------

    function test_TwoPlayersSettleIndependently() public {
        uint256 a = _open(10 * USDC);
        uint256 b = _open2(5 * USDC);
        assertEq(book.playerFunds(), 15 * USDC);
        assertEq(book.reserved(), 60 * USDC);
        assertEq(book.openSessions(), 2);

        vm.prank(device2);
        book.close(b, 8 * USDC); // player2 wins 3
        vm.expectRevert(TickEscrow.SessionsOpen.selector);
        book.withdraw(1, address(this)); // player's session is still open

        vm.prank(device);
        book.close(a, 2 * USDC); // player loses 8
        assertEq(usdc.balanceOf(player), 92 * USDC);
        assertEq(usdc.balanceOf(player2), 103 * USDC);
        assertEq(book.houseBalance(), 105 * USDC);
        assertEq(book.openSessions(), 0);
        book.withdraw(105 * USDC, address(this));
        assertEq(usdc.balanceOf(address(book)), 0);
    }

    function test_DeviceCannotCloseAnotherPlayersSession() public {
        _open(10 * USDC);
        uint256 b = _open2(10 * USDC);
        vm.prank(device);
        vm.expectRevert(TickEscrow.NotDevice.selector);
        book.close(b, 50 * USDC);
        bytes memory sig = _sign(b, 50 * USDC); // signed by player's device, not player2's
        vm.expectRevert(TickEscrow.BadSignature.selector);
        book.closeWithSig(b, 50 * USDC, sig);
    }

    function test_SignatureIsBoundToItsSession() public {
        uint256 a = _open(10 * USDC);
        uint256 b = _open(10 * USDC); // same device, second session
        bytes memory sig = _sign(a, 40 * USDC);
        vm.expectRevert(TickEscrow.BadSignature.selector);
        book.closeWithSig(b, 40 * USDC, sig);
    }

    function test_PlayerCannotReclaimAnothersSession() public {
        _open(10 * USDC);
        uint256 b = _open2(10 * USDC);
        vm.warp(block.timestamp + 1 days);
        vm.prank(player);
        vm.expectRevert(TickEscrow.NotPlayer.selector);
        book.reclaim(b);
    }

    function test_OneStuckSessionKeepsTheHouseLocked() public {
        uint256 a = _open(10 * USDC); // this device goes quiet
        uint256 b = _open2(10 * USDC);
        vm.prank(device2);
        book.close(b, 10 * USDC);
        vm.expectRevert(TickEscrow.SessionsOpen.selector);
        book.withdraw(1, address(this));

        vm.warp(block.timestamp + 1 days);
        vm.prank(player);
        book.reclaim(a);
        book.withdraw(100 * USDC, address(this));
        assertEq(usdc.balanceOf(player), 100 * USDC);
        assertEq(usdc.balanceOf(player2), 100 * USDC);
    }

    // ---- house -------------------------------------------------------------

    function test_HouseCannotWithdrawDuringASession() public {
        _open(10 * USDC);
        vm.expectRevert(TickEscrow.SessionsOpen.selector);
        book.withdraw(1, address(this));
    }

    function test_HouseWithdrawsWinningsAfterSessionsClose() public {
        uint256 id = _open(10 * USDC);
        vm.prank(device);
        book.close(id, 4 * USDC);
        book.withdraw(106 * USDC, stranger);
        assertEq(usdc.balanceOf(stranger), 106 * USDC);
        assertEq(usdc.balanceOf(address(book)), 0);
    }

    function test_WithdrawCannotExceedHouse() public {
        vm.expectRevert(TickEscrow.BadAmount.selector);
        book.withdraw(101 * USDC, address(this));
    }

    function test_OnlyOwnerFundsWithdrawsAndPauses() public {
        vm.startPrank(stranger);
        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, stranger));
        book.fund(1);
        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, stranger));
        book.withdraw(1, stranger);
        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, stranger));
        book.setPaused(true);
        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, stranger));
        book.setLimits(0, 0, 0);
        vm.stopPrank();
    }

    function test_PauseDrainWithdraw() public {
        uint256 id = _open(10 * USDC);
        book.setPaused(true);
        vm.expectRevert(TickEscrow.SessionsOpen.selector);
        book.withdraw(1, address(this));
        vm.warp(block.timestamp + 1 days); // the device went quiet
        vm.prank(player);
        book.reclaim(id);
        book.withdraw(100 * USDC, address(this));
        assertEq(usdc.balanceOf(player), 100 * USDC);
        assertEq(usdc.balanceOf(address(book)), 0);
    }

    // ---- opening for a player ----------------------------------------------

    /// A device holding USDC a player sent it opens the session in their name.
    function test_OpenForPaysThePlayerNotTheCaller() public {
        usdc.mint(device, 10 * USDC);
        vm.startPrank(device);
        usdc.approve(address(book), type(uint256).max);
        uint256 id = book.openFor(player, 10 * USDC, device);
        (address p, address d,,,,) = book.sessions(id);
        assertEq(p, player);
        assertEq(d, device);
        book.close(id, 12 * USDC);
        vm.stopPrank();
        assertEq(usdc.balanceOf(player), 112 * USDC);
        assertEq(usdc.balanceOf(device), 0, "the caller gets nothing back");
    }

    function test_OpenForRefundGoesToThePlayer() public {
        usdc.mint(device, 10 * USDC);
        vm.startPrank(device);
        usdc.approve(address(book), type(uint256).max);
        uint256 id = book.openFor(player, 10 * USDC, device);
        vm.stopPrank();
        vm.warp(block.timestamp + 1 days);
        vm.prank(device);
        vm.expectRevert(TickEscrow.NotPlayer.selector);
        book.reclaim(id);
        vm.prank(player);
        book.reclaim(id);
        assertEq(usdc.balanceOf(player), 110 * USDC);
    }

    function test_OpenForRejectsNoPlayer() public {
        vm.expectRevert(TickEscrow.BadPlayer.selector);
        book.openFor(address(0), 10 * USDC, device);
    }

    // ---- timeout -----------------------------------------------------------

    function test_ReclaimAfterTimeout() public {
        uint256 id = _open(10 * USDC);
        vm.prank(player);
        vm.expectRevert(TickEscrow.TooEarly.selector);
        book.reclaim(id);

        vm.warp(block.timestamp + 1 days);
        vm.prank(stranger);
        vm.expectRevert(TickEscrow.NotPlayer.selector);
        book.reclaim(id);
        vm.prank(player);
        book.reclaim(id);
        assertEq(usdc.balanceOf(player), 100 * USDC);
        assertEq(book.reserved(), 0);
        assertEq(book.openSessions(), 0);
        assertEq(book.houseBalance(), 100 * USDC);
    }

    function test_HouseCannotDelayARefund() public {
        uint256 id = _open(10 * USDC);
        book.setLimits(100 * USDC, 40_000, 365 days);
        vm.warp(block.timestamp + 1 days);
        vm.prank(player);
        book.reclaim(id);
        assertEq(usdc.balanceOf(player), 100 * USDC);
    }

    // ---- invariant ---------------------------------------------------------

    function testFuzz_AlwaysSolvent(uint256 deposit, uint256 finalBalance) public {
        deposit = bound(deposit, 1, 25 * USDC);
        uint256 id = _open(deposit);
        assertGe(usdc.balanceOf(address(book)), book.playerFunds() + book.reserved());
        vm.prank(device);
        book.close(id, finalBalance);
        assertLe(usdc.balanceOf(player), 100 * USDC + 4 * deposit);
        assertEq(usdc.balanceOf(player) + usdc.balanceOf(address(book)), 200 * USDC, "no money created or lost");
    }
}

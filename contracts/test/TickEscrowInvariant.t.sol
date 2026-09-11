// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {Test} from "forge-std/Test.sol";
import {StdInvariant} from "forge-std/StdInvariant.sol";
import {TickEscrow} from "../src/TickEscrow.sol";
import {MockUSDC} from "./mocks/MockUSDC.sol";

/// Three players, each with a device, and the house (this handler is the
/// owner). The fuzzer calls these in random order with random amounts.
contract Handler is Test {
    uint256 constant USDC = 1e6;

    MockUSDC public usdc;
    TickEscrow public book;
    address[] public players;
    mapping(address => uint256) public pkOf; // device => key
    uint256[] public ids;
    /// Sessions still open, so close and reclaim always hit one.
    uint256[] openIds;
    mapping(uint256 => uint256) slotOf; // id => index in openIds

    /// Every USDC ever minted; it must all be somewhere.
    uint256 public minted;
    /// Ghosts that must stay zero.
    uint256 public withdrawnWhileOpen;
    uint256 public stuckWithdraws; // refused although no session was open
    uint256 public wrongPayouts;

    /// What actually happened, so a run that skipped everything cannot pass.
    uint256 public closed;
    uint256 public reclaimed;
    uint256 public withdrawn;
    uint256 public mostPlayersAtOnce;
    mapping(address => uint256) openBy;
    uint256 playersWithOpen;

    constructor() {
        usdc = new MockUSDC();
        book = new TickEscrow(usdc, address(this));
        usdc.approve(address(book), type(uint256).max);
        _fund(20 * USDC);
        for (uint256 i; i < 3; i++) {
            address p = makeAddr(string.concat("player", vm.toString(i)));
            players.push(p);
            pkOf[vm.addr(0xD0 + i)] = 0xD0 + i;
            usdc.mint(p, 100 * USDC);
            minted += 100 * USDC;
            vm.prank(p);
            usdc.approve(address(book), type(uint256).max);
        }
    }

    function idsLength() external view returns (uint256) {
        return ids.length;
    }

    function allHolders() external view returns (address[] memory holders) {
        holders = new address[](players.length + 2);
        for (uint256 i; i < players.length; i++) {
            holders[i] = players[i];
        }
        holders[players.length] = address(this);
        holders[players.length + 1] = address(book);
    }

    // ---- actions -----------------------------------------------------------

    function open(uint256 who, uint256 amount) external {
        who = bound(who, 0, players.length - 1);
        amount = bound(amount, 1, 5 * USDC);
        address p = players[who];
        if (usdc.balanceOf(p) < amount) return;
        // The owner tops the house up so the session fits; otherwise withdrawals
        // starve it and players rarely overlap. HouseTooSmall is a unit test.
        uint256 reserve = amount * book.winCapBps() / 10_000;
        uint256 free = book.freeHouse();
        if (reserve > free) _fund(reserve - free);
        vm.prank(p);
        uint256 id = book.open(amount, vm.addr(0xD0 + who));
        ids.push(id);
        slotOf[id] = openIds.length;
        openIds.push(id);
        if (openBy[p]++ == 0 && ++playersWithOpen > mostPlayersAtOnce) mostPlayersAtOnce = playersWithOpen;
    }

    function close(uint256 pick, uint256 finalBalance, bool withSig) external {
        if (openIds.length == 0) return;
        uint256 id = openIds[bound(pick, 0, openIds.length - 1)];
        (address p, address device, uint256 cap) = _session(id);
        finalBalance = bound(finalBalance, 0, 2 * cap); // half the time above the cap

        uint256 before = usdc.balanceOf(p);
        if (withSig) {
            book.closeWithSig(id, finalBalance, _sign(device, id, finalBalance));
        } else {
            vm.prank(device);
            book.close(id, finalBalance);
        }
        if (usdc.balanceOf(p) - before != (finalBalance < cap ? finalBalance : cap)) wrongPayouts++;
        closed++;
        _ended(p, id);
    }

    function reclaim(uint256 pick) external {
        if (openIds.length == 0) return;
        _reclaim(openIds[bound(pick, 0, openIds.length - 1)]);
    }

    /// Tried at any moment: must fail while a session is open and succeed otherwise.
    function withdraw(uint256 amount) public {
        uint256 house = book.houseBalance();
        if (house == 0) return;
        amount = bound(amount, 1, house);
        bool sessionsOpen = book.openSessions() != 0;
        try book.withdraw(amount, address(this)) {
            if (sessionsOpen) withdrawnWhileOpen++;
            withdrawn++;
        } catch {
            if (!sessionsOpen) stuckWithdraws++;
        }
    }

    /// The owner's way out: pause, let every open session end, withdraw, unpause.
    function drain(uint256 amount) external {
        book.setPaused(true);
        while (openIds.length > 0) {
            _reclaim(openIds[openIds.length - 1]);
        }
        withdraw(amount);
        book.setPaused(false);
    }

    function fund(uint256 amount) external {
        _fund(bound(amount, 1, 10 * USDC));
    }

    function _reclaim(uint256 id) internal {
        (address p,, uint96 deposit,, uint64 reclaimAfter,) = book.sessions(id);
        if (block.timestamp < reclaimAfter) vm.warp(reclaimAfter);
        uint256 before = usdc.balanceOf(p);
        vm.prank(p);
        book.reclaim(id);
        if (usdc.balanceOf(p) - before != deposit) wrongPayouts++;
        reclaimed++;
        _ended(p, id);
    }

    function _ended(address p, uint256 id) internal {
        if (--openBy[p] == 0) playersWithOpen--;
        uint256 last = openIds[openIds.length - 1];
        openIds[slotOf[id]] = last;
        slotOf[last] = slotOf[id];
        openIds.pop();
    }

    /// `cap` is the most the session can pay out: deposit + reserve.
    function _session(uint256 id) internal view returns (address p, address device, uint256 cap) {
        uint96 deposit;
        uint96 reserve;
        (p, device, deposit, reserve,,) = book.sessions(id);
        cap = uint256(deposit) + reserve;
    }

    function _sign(address device, uint256 id, uint256 finalBalance) internal view returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pkOf[device], book.closeDigest(id, finalBalance));
        return abi.encodePacked(r, s, v);
    }

    function _fund(uint256 amount) internal {
        usdc.mint(address(this), amount);
        minted += amount;
        book.fund(amount);
    }
}

contract TickEscrowInvariantTest is StdInvariant, Test {
    Handler handler;
    TickEscrow book;
    MockUSDC usdc;

    function setUp() public {
        handler = new Handler();
        book = handler.book();
        usdc = handler.usdc();
        bytes4[] memory selectors = new bytes4[](6);
        selectors[0] = Handler.open.selector;
        selectors[1] = Handler.close.selector;
        selectors[2] = Handler.reclaim.selector;
        selectors[3] = Handler.withdraw.selector;
        selectors[4] = Handler.fund.selector;
        selectors[5] = Handler.drain.selector;
        targetSelector(FuzzSelector({addr: address(handler), selectors: selectors}));
        targetContract(address(handler));
    }

    /// The contract always holds every open deposit plus every open reserve.
    function invariant_Solvent() public view {
        assertGe(usdc.balanceOf(address(book)), book.playerFunds() + book.reserved());
    }

    /// The running totals match the open sessions, however they interleave.
    function invariant_TotalsMatchOpenSessions() public view {
        uint256 deposits;
        uint256 reserves;
        uint256 count;
        for (uint256 i; i < handler.idsLength(); i++) {
            (,, uint96 deposit, uint96 reserve,, bool isOpen) = book.sessions(handler.ids(i));
            if (isOpen) {
                deposits += deposit;
                reserves += reserve;
                count++;
            }
        }
        assertEq(book.playerFunds(), deposits, "playerFunds");
        assertEq(book.reserved(), reserves, "reserved");
        assertEq(book.openSessions(), count, "openSessions");
    }

    function invariant_NoMoneyCreatedOrLost() public view {
        address[] memory holders = handler.allHolders();
        uint256 sum;
        for (uint256 i; i < holders.length; i++) {
            sum += usdc.balanceOf(holders[i]);
        }
        assertEq(sum, handler.minted());
    }

    function invariant_HouseNeverWithdrewDuringASession() public view {
        assertEq(handler.withdrawnWhileOpen(), 0);
    }

    /// The lock never traps house money once the sessions have ended.
    function invariant_HouseCanWithdrawOnceSessionsEnd() public view {
        assertEq(handler.stuckWithdraws(), 0);
    }

    function invariant_EveryPayoutExact() public view {
        assertEq(handler.wrongPayouts(), 0);
    }

    /// Every run must have had different players' sessions open at once and
    /// used every way out, or the invariants above proved nothing.
    function afterInvariant() public view {
        assertGe(handler.mostPlayersAtOnce(), 2, "no two players were ever open at once");
        assertGt(handler.closed(), 0, "nothing closed");
        assertGt(handler.reclaimed(), 0, "nothing reclaimed");
        assertGt(handler.withdrawn(), 0, "the house never withdrew");
    }
}

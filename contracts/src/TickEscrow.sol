// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {SafeCast} from "@openzeppelin/contracts/utils/math/SafeCast.sol";

/// @title TickEscrow
/// @notice USDC escrow for TICK play sessions, with the owner as the house.
///
/// Both sides' money is locked:
///  - **Player.** A player locks USDC for a device and plays off-chain. One
///    close settles the whole session: the player is paid the device's final
///    balance, a loss stays with the house and a win is paid from it. If the
///    device never closes, the player takes the deposit back after a timeout.
///  - **House.** The owner funds the house. Opening a session holds back
///    `deposit * winCapBps / 10_000` of house money, so a win is always
///    payable. The owner can withdraw only while no session is open, and never
///    touches a player's deposit. To drain the house, pause new sessions and
///    wait for the open ones to close or time out.
///
/// Amounts are USDC's ERC-20 units (6 decimals) — on Arc, never the 18-decimal
/// native view of the same balance.
contract TickEscrow is Ownable, EIP712 {
    using SafeERC20 for IERC20;

    struct Session {
        address player; // paid on close
        address device; // sends or signs the close
        uint96 deposit; // locked by the player
        uint96 reserve; // house money held back to cover a win
        uint64 reclaimAfter; // fixed at open, so later limit changes cannot delay a refund
        bool open;
    }

    bytes32 private constant CLOSE_TYPEHASH = keccak256("Close(uint256 sessionId,uint256 finalBalance)");

    IERC20 public immutable usdc;

    mapping(uint256 => Session) public sessions;
    uint256 public nextSessionId = 1;
    uint256 public openSessions;
    /// Deposits in open sessions: held here but owed to players, not the house.
    uint256 public playerFunds;
    /// House money held back to cover open sessions.
    uint256 public reserved;
    /// Stops new sessions; open ones still close.
    bool public paused;

    uint256 public maxSessionDeposit = 100e6;
    /// Most a session can win, in basis points of its deposit. 40_000 = 4x.
    uint256 public winCapBps = 40_000;
    /// After this long an unclosed session can be reclaimed by its player.
    uint256 public sessionTimeout = 1 days;

    event SessionOpened(
        uint256 indexed id, address indexed player, address indexed device, uint256 deposit, uint256 reserve
    );
    event SessionClosed(uint256 indexed id, uint256 finalBalance, uint256 payout, int256 housePnl);
    event SessionReclaimed(uint256 indexed id, uint256 refund);
    event HouseFunded(uint256 amount);
    event HouseWithdrawn(address indexed to, uint256 amount);
    event PausedSet(bool paused);
    event LimitsSet(uint256 maxSessionDeposit, uint256 winCapBps, uint256 sessionTimeout);

    error BadAmount();
    error BadDevice();
    error BadPlayer();
    error HouseTooSmall();
    error IsPaused();
    error SessionsOpen();
    error NotOpen();
    error NotDevice();
    error NotPlayer();
    error BadSignature();
    error TooEarly();

    constructor(IERC20 usdc_, address owner_) Ownable(owner_) EIP712("TickEscrow", "1") {
        usdc = usdc_;
    }

    // ---- house -------------------------------------------------------------

    /// Everything the contract holds except deposits owed back to open sessions.
    function houseBalance() public view returns (uint256) {
        return usdc.balanceOf(address(this)) - playerFunds;
    }

    /// House money not held back for open sessions: what new sessions can reserve.
    function freeHouse() public view returns (uint256) {
        uint256 house = houseBalance();
        return house > reserved ? house - reserved : 0;
    }

    function fund(uint256 amount) external onlyOwner {
        if (amount == 0) revert BadAmount();
        usdc.safeTransferFrom(msg.sender, address(this), amount);
        emit HouseFunded(amount);
    }

    /// Only while no session is open, so no player can be left unpaid.
    function withdraw(uint256 amount, address to) external onlyOwner {
        if (openSessions != 0) revert SessionsOpen();
        if (amount == 0 || amount > houseBalance()) revert BadAmount();
        usdc.safeTransfer(to, amount);
        emit HouseWithdrawn(to, amount);
    }

    function setPaused(bool paused_) external onlyOwner {
        paused = paused_;
        emit PausedSet(paused_);
    }

    /// Applies to sessions opened afterwards; open ones keep their reserve and timeout.
    function setLimits(uint256 maxSessionDeposit_, uint256 winCapBps_, uint256 sessionTimeout_) external onlyOwner {
        maxSessionDeposit = maxSessionDeposit_;
        winCapBps = winCapBps_;
        sessionTimeout = sessionTimeout_;
        emit LimitsSet(maxSessionDeposit_, winCapBps_, sessionTimeout_);
    }

    // ---- sessions ----------------------------------------------------------

    /// Lock `amount` USDC from the caller for a session played on `device`.
    /// The caller is paid on close; `device` is the only key that can close it.
    function open(uint256 amount, address device) external returns (uint256) {
        return _open(msg.sender, amount, device);
    }

    /// Lock `amount` USDC from the caller for `player`, who is paid on close.
    /// This is how a device opens a session with USDC a player sent it: the
    /// caller pays in, and the payout can only ever go to `player`.
    function openFor(address player, uint256 amount, address device) external returns (uint256) {
        if (player == address(0)) revert BadPlayer();
        return _open(player, amount, device);
    }

    function _open(address player, uint256 amount, address device) private returns (uint256 id) {
        if (paused) revert IsPaused();
        if (amount == 0 || amount > maxSessionDeposit) revert BadAmount();
        if (device == address(0)) revert BadDevice();
        uint256 reserve = amount * winCapBps / 10_000;
        if (reserve > freeHouse()) revert HouseTooSmall();

        usdc.safeTransferFrom(msg.sender, address(this), amount);
        playerFunds += amount;
        reserved += reserve;
        openSessions++;

        id = nextSessionId++;
        sessions[id] = Session({
            player: player,
            device: device,
            deposit: SafeCast.toUint96(amount),
            reserve: SafeCast.toUint96(reserve),
            reclaimAfter: SafeCast.toUint64(block.timestamp + sessionTimeout),
            open: true
        });
        emit SessionOpened(id, player, device, amount, reserve);
    }

    /// The device settles its own session.
    function close(uint256 id, uint256 finalBalance) external {
        if (msg.sender != sessions[id].device) revert NotDevice();
        _close(id, finalBalance);
    }

    /// Anyone submits a close the device signed, so the device needs no gas.
    function closeWithSig(uint256 id, uint256 finalBalance, bytes calldata signature) external {
        if (ECDSA.recover(closeDigest(id, finalBalance), signature) != sessions[id].device) revert BadSignature();
        _close(id, finalBalance);
    }

    /// The EIP-712 digest a device signs to close `id` at `finalBalance`.
    function closeDigest(uint256 id, uint256 finalBalance) public view returns (bytes32) {
        return _hashTypedDataV4(keccak256(abi.encode(CLOSE_TYPEHASH, id, finalBalance)));
    }

    /// The device never closed: after the timeout the player takes the deposit back.
    function reclaim(uint256 id) external {
        Session storage s = sessions[id];
        if (!s.open) revert NotOpen();
        if (msg.sender != s.player) revert NotPlayer();
        if (block.timestamp < s.reclaimAfter) revert TooEarly();
        _release(s);
        usdc.safeTransfer(s.player, s.deposit);
        emit SessionReclaimed(id, s.deposit);
    }

    function _close(uint256 id, uint256 finalBalance) internal {
        Session storage s = sessions[id];
        if (!s.open) revert NotOpen();
        _release(s);
        uint256 cap = uint256(s.deposit) + s.reserve;
        uint256 payout = finalBalance < cap ? finalBalance : cap;
        if (payout > 0) usdc.safeTransfer(s.player, payout);
        emit SessionClosed(id, finalBalance, payout, int256(uint256(s.deposit)) - int256(payout));
    }

    function _release(Session storage s) private {
        s.open = false;
        openSessions--;
        playerFunds -= s.deposit;
        reserved -= s.reserve;
    }
}

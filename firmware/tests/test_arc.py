import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import pygame

from arc import ArcFunding, House, Incoming, calldata
from games.box import BoxGame
from games.box_model import BoxModel
from decimal import Decimal

from input import InputAction
from names import Standing
from screens.board import BoardFeed
from screens.money import (ARRIVAL_HOLD_S, ARRIVAL_S, CONFIRM_ARM_S, PAYING_HOLD_S,
                           RECEIPT_S, MoneyScreen, handle_money_events)
from test_box import warm
from wallet import MICRO, DemoFunding, Wallet

PLAYER = '0x7ee85B080701330bf53Be62B7E72fcDD034eCCac'
DEVICE = '0x3E0A93BDaA49710f4052B6e17A4Ac2b3f2f6562E'
ESCROW = '0xC50dC94A6b9AB85A5B541Da9DB5df83870A41b3B'
FEE = 10_000


class FakeChain:
    """TickEscrow's rules without a network: a 4x reserve and capped payouts."""
    address = DEVICE

    def __init__(self):
        self.head = 100
        self.transfers = []          # (block, Incoming)
        self.free = 100 * MICRO
        self.max_deposit = 100 * MICRO
        self.paused = False
        self.approved = False
        self.open = {}               # id -> (player, deposit, reserve)
        self.next_id = 1
        self.paid = []               # (player, payout)
        self.refunds = []
        self.fail_close = False

    def arrive(self, sender, amount):
        self.head += 1
        self.transfers.append((self.head, Incoming(sender, amount, f'0xtx{self.head}:0')))

    def block(self):
        return self.head

    def incoming(self, first, last):
        return [i for block, i in self.transfers if first <= block <= last]

    def house(self):
        return House(self.free, 40_000, self.max_deposit, self.paused)

    def allowance(self):
        return 2 ** 255 if self.approved else 0

    def approve_escrow(self):
        self.approved = True
        return '0xapprove'

    def session_open(self, sid):
        return sid in self.open

    def open_for(self, player, amount):
        assert self.approved, 'the escrow pulls USDC only after an approve'
        reserve = amount * 4
        self.free -= reserve
        sid, self.next_id = self.next_id, self.next_id + 1
        self.open[sid] = (player, amount, reserve)
        return sid, amount, reserve, f'0xopen{sid}'

    def close(self, sid, final):
        if self.fail_close:
            raise OSError('network down')
        player, deposit, reserve = self.open.pop(sid)
        payout = min(final, deposit + reserve)
        self.free += deposit + reserve - payout
        self.paid.append((player, payout))
        return payout, f'0xclose{sid}'

    def transfer(self, to, amount):
        self.refunds.append((to, amount))
        return '0xrefund'


class ArcFundingTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.state = Path(folder.name) / 'arc-testnet.json'
        env = mock.patch.dict(os.environ, {'TICK_ESCROW_ADDRESS': ESCROW})
        env.start()
        self.addCleanup(env.stop)
        self.chain = FakeChain()
        self.funding = self.make()
        self.wallet = Wallet(self.funding.balance, self.funding)

    def make(self):
        return ArcFunding(chain=self.chain, state_path=self.state, gas_fee=FEE, start=False,
                          lookup=lambda player: None)    # no Sepolia in tests

    def deposit(self, amount, sender=PLAYER):
        if self.funding.last_block is None:
            self.funding.step()
        self.chain.arrive(sender, amount)
        self.funding.step()
        return self.funding.sync(self.wallet)

    def test_usdc_that_arrived_before_the_first_run_is_not_a_deposit(self):
        self.chain.arrive(PLAYER, MICRO)
        self.funding.step()
        self.assertEqual((self.funding.sessions, self.chain.open), ([], {}))

    def test_a_deposit_opens_a_session_in_the_senders_name(self):
        news = self.deposit(MICRO)
        self.assertEqual(news[0][:3], ('opened', MICRO - FEE, PLAYER))
        self.assertEqual(self.chain.open[1], (PLAYER, MICRO - FEE, 4 * (MICRO - FEE)))
        self.assertEqual(self.wallet.balance, MICRO - FEE)
        self.assertEqual(self.wallet.cap, 5 * (MICRO - FEE))
        self.assertTrue(self.funding.in_session)

    def test_cash_out_pays_the_final_balance_to_the_player(self):
        self.deposit(MICRO)
        self.wallet.balance = 1_500_000       # won some
        self.funding.sync(self.wallet)
        self.assertTrue(self.funding.cash_out(self.wallet))
        self.assertEqual(self.wallet.balance, 0)
        self.funding.step()
        news = self.funding.sync(self.wallet)
        self.assertEqual(news[-1], ('cashed_out', [(1_500_000, PLAYER, '0xclose1')]))
        self.assertEqual(self.chain.paid, [(PLAYER, 1_500_000)])
        self.assertFalse(self.funding.in_session)
        self.assertIsNone(self.wallet.cap)
        self.assertEqual(self.funding.last_cashout, (1_500_000, PLAYER, '0xclose1'))

    def test_two_deposits_pay_out_oldest_first(self):
        self.deposit(MICRO)
        self.deposit(MICRO)
        self.assertEqual(self.wallet.balance, 2 * (MICRO - FEE))
        self.wallet.balance = 6 * MICRO       # more than one session's cap
        self.funding.sync(self.wallet)
        self.funding.cash_out(self.wallet)
        self.funding.step()
        first = 5 * (MICRO - FEE)
        self.assertEqual(self.chain.paid, [(PLAYER, first), (PLAYER, 6 * MICRO - first)])

    def test_a_deposit_the_house_cannot_cover_is_sent_back(self):
        self.chain.free = MICRO               # a 0.99 deposit needs 3.96 held back
        news = self.deposit(MICRO)
        self.assertEqual(self.chain.refunds, [(PLAYER, MICRO - FEE)])
        self.assertEqual(news[0][:4], ('refunded', MICRO - FEE, PLAYER, 'HOUSE TOO SMALL'))
        self.assertEqual(self.wallet.balance, 0)

    def test_dust_only_tops_up_the_gas(self):
        self.deposit(FEE)
        self.assertEqual((self.chain.open, self.chain.refunds, self.wallet.balance), ({}, [], 0))

    def test_each_transfer_is_taken_once(self):
        self.deposit(MICRO)
        self.funding.last_block -= 1          # the same range read again
        self.funding.step()
        self.assertEqual(len(self.chain.open), 1)

    def test_a_restart_resumes_the_session_and_its_balance(self):
        self.deposit(MICRO)
        self.wallet.balance = 700_000
        self.funding.sync(self.wallet)
        again = self.make()
        self.assertEqual((again.balance, again.cap, again.player), (700_000, 5 * (MICRO - FEE), PLAYER))

    def test_an_interrupted_cash_out_finishes_after_a_restart(self):
        self.deposit(MICRO)
        self.chain.fail_close = True
        self.funding.cash_out(self.wallet)
        with self.assertRaises(OSError):
            self.funding.step()
        self.chain.fail_close = False
        again = self.make()
        self.assertEqual(again.pending_cashout, MICRO - FEE)
        again.step()
        self.assertEqual(self.chain.paid, [(PLAYER, MICRO - FEE)])
        self.assertEqual(again.sync(Wallet(0, again))[-1][0], 'cashed_out')

    def test_a_session_that_ended_while_off_is_dropped(self):
        self.deposit(MICRO)
        self.chain.open.clear()               # the player reclaimed it
        again = self.make()
        wallet = Wallet(again.balance, again)
        again.step()
        again.sync(wallet)
        self.assertEqual((again.sessions, wallet.balance), ([], 0))

    def with_names(self, *answers):
        """The funding again, with ENS giving `answers` in turn; an exception is raised."""
        asked = []

        def lookup(player):
            asked.append(player)
            answer = answers[len(asked) - 1]
            if isinstance(answer, Exception):
                raise answer
            return answer
        self.funding = ArcFunding(chain=self.chain, state_path=self.state, gas_fee=FEE,
                                  start=False, lookup=lookup)
        self.funding.NAME_S = 0
        self.wallet = Wallet(self.funding.balance, self.funding)
        return asked

    def test_a_player_gets_their_name_once_the_scorekeeper_has_named_them(self):
        asked = self.with_names(None, 'fancy-panda.tick.eth')
        self.deposit(MICRO)
        self.assertEqual(self.funding.names, {})           # not named yet
        self.funding.step()
        self.assertIn(('named', PLAYER, 'fancy-panda.tick.eth'), self.funding.sync(self.wallet))
        self.funding.step()                                # and not asked about again
        self.assertEqual(asked, [PLAYER, PLAYER])

    def test_a_player_named_after_cashing_out_still_gets_their_name(self):
        """The scorekeeper often names a wallet only once its first session has closed."""
        self.with_names(None, 'fierce-lynx.tick.eth')
        self.deposit(MICRO)
        self.funding.cash_out(self.wallet)
        self.funding.step()
        self.assertFalse(self.funding.in_session)
        self.funding.step()
        self.assertEqual(self.funding.names, {PLAYER: 'fierce-lynx.tick.eth'})

    def test_ens_trouble_never_gets_in_the_way_of_the_money(self):
        self.with_names(OSError('sepolia down'))
        news = self.deposit(MICRO)
        self.assertEqual(news[0][:3], ('opened', MICRO - FEE, PLAYER))
        self.assertEqual(self.funding.names, {})

    def test_calldata_matches_the_abi(self):
        # cast calldata 'close(uint256,uint256)' 1 15000
        self.assertEqual(calldata('close(uint256,uint256)', 1, 15000),
                         '0x596c8976' + f'{1:064x}' + f'{15000:064x}')


class Capped:
    """A backend whose sessions pay out at most `cap`."""
    name, live = 'USDC', True

    def __init__(self, cap):
        self.cap = cap


class BoxRulesForRealFundsTests(unittest.TestCase):
    def test_a_press_that_could_win_past_the_cap_is_refused(self):
        m = BoxModel(Wallet(MICRO, Capped(MICRO)), stake=500_000)
        now = warm(m)
        self.assertFalse(m.buy(now))
        self.assertEqual((m.refused, m.wallet.balance), ('cap', MICRO))
        m.wallet.funding.cap = 10 * MICRO
        self.assertTrue(m.buy(now))
        self.assertEqual(m.refused, '')

    def test_cancelling_refunds_the_box_bought_for_next(self):
        m = BoxModel(Wallet(MICRO, DemoFunding()), stake=500_000)
        now = warm(m)
        self.assertTrue(m.buy(now))
        self.assertEqual(m.cancel_pending(), 500_000)
        self.assertEqual((m.pending, m.wallet.balance), (None, MICRO))


def standing(name: str, pnl: str, player: str | None = None, plays: int = 3) -> Standing:
    return Standing(f'{name}.tick.eth', player or f'0x{abs(hash(name)):040x}'[:42],
                    plays, 1, Decimal(pnl), Decimal('0.5'))


# The board before and after our player's run is scored: last of six to third.
BEFORE = [standing('turbo-lynx', '812'), standing('misty-crab', '402.50'),
          standing('neon-yak', '101'), standing('sly-moose', '52'),
          standing('quiet-vole', '12'), standing('amber-otter', '-18.40', PLAYER, 11)]
AFTER = sorted([row for row in BEFORE if row.player != PLAYER]
               + [standing('amber-otter', '137.40', PLAYER, 12)],
               key=lambda row: (-row.pnl, -row.wins, row.name))


class ReadingFeed(BoardFeed):
    """A BoardFeed whose reader runs where the test can see it: `want` reads now,
    on this thread, obeying `hold` exactly as the real one does. That is what
    makes the read the board fires on opening land at the moment it really would."""

    def want(self) -> None:
        self.refresh()


class ArcScreenTests(unittest.TestCase):
    """The money screen, end to end on a fake chain: coin in, cash out, ticket."""

    def setUp(self):
        pygame.init()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        env = mock.patch.dict(os.environ, {'TICK_ESCROW_ADDRESS': ESCROW})
        env.start()
        self.addCleanup(env.stop)
        self.chain = FakeChain()
        self.funding = ArcFunding(chain=self.chain, state_path=Path(folder.name) / 's.json',
                                  gas_fee=FEE, start=False, lookup=lambda player: None)
        self.game = BoxGame(seed=1, sound=False, source='sim', wallet=Wallet(0, self.funding))
        self.addCleanup(self.game.close)
        self.money = MoneyScreen(self.game)
        self.canvas = pygame.Surface((480, 320))

    def deposit(self, amount=MICRO):
        """A player sends USDC and the device opens a session for it."""
        self.funding.step()
        self.chain.arrive(PLAYER, amount)
        self.funding.step()
        self.game.sync_funding()

    def test_it_opens_on_insert_coin_with_no_money_in(self):
        self.money.open()
        self.assertEqual(self.money.face, 'waiting')
        self.money.draw(self.canvas)                     # QR, address, waiting rider
        self.assertIsNone(self.money.handle_action(InputAction.A))   # nothing to press
        self.assertEqual(self.money.handle_action(InputAction.B), 'home')

    def test_a_deposit_while_waiting_becomes_the_coin_drop(self):
        self.money.open()
        self.deposit()
        self.money.update(.1)
        self.assertEqual(self.money.face, 'arrival')
        self.assertEqual(self.money.deposit, (MICRO - FEE, PLAYER))
        self.assertIsNone(self.game.coin_in)             # taken, so it plays once
        self.money.draw(self.canvas)
        self.assertEqual(self.game.model.wallet.balance, MICRO - FEE)

    def test_a_on_the_coin_drop_goes_straight_into_the_game(self):
        self.money.open()
        self.deposit()
        self.money.update(.1)
        self.assertEqual(self.money.handle_action(InputAction.A), 'game')

    def test_the_coin_drop_falls_back_to_the_launcher_on_its_own(self):
        self.money.open()
        self.deposit()
        self.money.update(.1)
        self.money.update(ARRIVAL_S + ARRIVAL_HOLD_S + .1)
        self.assertEqual(handle_money_events(self.money, [], [InputAction.A]), 'funded')
        self.assertIsNone(handle_money_events(self.money, [], []))   # once only

    def test_a_deposit_landing_elsewhere_does_not_replay_later(self):
        self.deposit()                                   # money lands on the launcher
        self.money.open()
        self.money.update(.1)
        self.assertEqual(self.money.face, 'confirm')

    def test_money_in_opens_the_cash_out_question(self):
        self.deposit()
        self.money.open()
        self.assertEqual(self.money.face, 'confirm')
        self.money.draw(self.canvas)
        # The A that opened the card cannot also send the money.
        self.assertFalse(self.money.armed)
        self.money.handle_action(InputAction.A)
        self.assertEqual(self.money.face, 'confirm')
        self.assertIsNone(self.funding.pending_cashout)
        self.assertEqual(self.money.handle_action(InputAction.B), 'home')

    def test_a_second_press_sends_the_money_and_prints_a_ticket(self):
        self.deposit()
        self.money.open()
        self.money.update(CONFIRM_ARM_S)
        self.assertTrue(self.money.armed)
        self.money.handle_action(InputAction.A)
        self.assertEqual(self.money.face, 'paying')
        self.assertEqual(self.funding.pending_cashout, MICRO - FEE)
        self.money.draw(self.canvas)                     # steps ticking, notes flying
        self.assertIsNone(self.money.handle_action(InputAction.B))   # it is sending

        self.funding.step()
        self.game.sync_funding()
        self.money.update(.1)
        self.assertEqual(self.chain.paid, [(PLAYER, MICRO - FEE)])
        self.assertEqual(self.money.face, 'receipt')
        ticket = self.game.ticket
        self.assertEqual((ticket.paid, ticket.paid_in), (MICRO - FEE, MICRO - FEE))
        self.assertEqual(ticket.player, PLAYER)
        self.money.draw(self.canvas)

    def test_a_late_payout_lets_you_walk_away_without_stopping_it(self):
        self.deposit()
        self.money.open()
        self.money.update(CONFIRM_ARM_S)
        self.money.handle_action(InputAction.A)
        self.assertIsNone(self.money.handle_action(InputAction.B))   # while it sends
        self.money.update(PAYING_HOLD_S + .1)
        self.assertTrue(self.money.stuck)
        self.money.draw(self.canvas)                                 # says it keeps sending
        self.assertEqual(self.money.handle_action(InputAction.B), 'home')
        # Leaving changed nothing about the money: the worker still owes it.
        self.assertEqual(self.funding.pending_cashout, MICRO - FEE)
        self.funding.step()
        self.game.sync_funding()
        self.assertEqual(self.chain.paid, [(PLAYER, MICRO - FEE)])

    def test_the_ticket_hands_itself_to_the_leaderboard(self):
        self.deposit()
        self.money.open()
        self.money.update(CONFIRM_ARM_S)
        self.money.handle_action(InputAction.A)
        self.funding.step()
        self.game.sync_funding()
        self.money.update(.1)
        self.assertEqual(self.money.handle_action(InputAction.A), 'board')
        self.money.update(RECEIPT_S + .1)
        self.assertEqual(handle_money_events(self.money, [], []), 'board')

    def test_the_ticket_reports_the_run_and_then_starts_a_new_one(self):
        self.deposit()
        self.game.run_boxes, self.game.run_hits, self.game.run_best = 12, 7, 48 * MICRO
        self.money.open()
        self.money.update(CONFIRM_ARM_S)
        self.money.handle_action(InputAction.A)
        self.funding.step()
        self.game.sync_funding()
        self.assertEqual((self.game.ticket.boxes, self.game.ticket.hits,
                          self.game.ticket.best), (12, 7, 48 * MICRO))
        self.assertEqual((self.game.run_boxes, self.game.run_hits, self.game.run_in), (0, 0, 0))

    def test_an_old_ticket_never_stands_in_for_the_next_payout(self):
        self.deposit()
        self.money.open()
        self.money.update(CONFIRM_ARM_S)
        self.money.handle_action(InputAction.A)
        self.funding.step()
        self.game.sync_funding()
        self.money.update(.1)
        self.assertEqual(self.money.face, 'receipt')
        self.deposit()                                   # a new player, a new run
        self.money.open()
        self.assertIsNone(self.game.ticket)
        self.money.update(CONFIRM_ARM_S)
        self.money.handle_action(InputAction.A)
        self.assertEqual(self.money.face, 'paying')      # not the old receipt

    def test_a_named_player_is_shown_by_their_name(self):
        self.funding.lookup = lambda player: 'fancy-panda.tick.eth'
        self.deposit()
        self.assertIn('WELCOME fancy-panda.tick.eth', self.game.banner()[0])
        self.money.open()
        self.money.draw(self.canvas)                     # CASH OUT to fancy-panda
        self.money.update(CONFIRM_ARM_S)
        self.money.handle_action(InputAction.A)
        self.funding.step()
        self.game.sync_funding()
        self.assertIn('SENT 0.99 TO fancy-panda.tick.eth', self.game.banner()[0])
        self.money.update(.1)
        self.money.draw(self.canvas)                     # the ticket, in their name

    def test_running_out_mid_play_asks_the_app_for_the_money_screen(self):
        from games.box import handle_box_events
        self.game.buy()                                  # nothing in the wallet
        self.assertFalse(self.game.wallet_open)          # the paper loader stays shut
        self.assertEqual(handle_box_events(self.game, [], [InputAction.A]), 'money')
        self.assertIsNone(handle_box_events(self.game, [], []))      # once only

    def test_a_deposit_during_play_stays_in_play(self):
        from games.box import handle_box_events
        self.deposit()
        self.assertIsNone(handle_box_events(self.game, [], []))


class LoopTests(unittest.TestCase):
    """The whole arcade loop through the real app: coin in, play, cash out,
    ticket, the board moving, and round again."""

    def setUp(self):
        pygame.init()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        env = mock.patch.dict(os.environ, {'TICK_ESCROW_ADDRESS': ESCROW})
        env.start()
        self.addCleanup(env.stop)
        self.chain = FakeChain()
        self.funding = ArcFunding(chain=self.chain, state_path=Path(folder.name) / 's.json',
                                  gas_fee=FEE, start=False, lookup=lambda player: None)
        from app import App
        self.app = App('box')
        self.addCleanup(self.app.game.close)
        self.app.game.model.wallet.funding = self.funding
        self.app.game.model.wallet.balance = 0
        self.standings = [BEFORE]
        self.app.board.feed = ReadingFeed(lambda: self.standings[-1])
        self.app.board.feed.refresh()

    def step(self, *actions):
        if self.app.current != 'game':
            self.app.screen_up().update(1 / 30)
            self.app.game.watch(1 / 30)
        else:
            self.app.game.update(1 / 30)
        self.app._dispatch([], list(actions))
        self.app._draw()

    def until(self, done, limit=600):
        for _ in range(limit):
            self.step()
            if done():
                return
        self.fail('never got there')

    def test_the_loop(self):
        app = self.app
        app.home.focus = 1                      # the money button
        self.step(InputAction.A)
        self.assertEqual((app.current, app.money.face), ('money', 'waiting'))

        self.funding.step()
        self.chain.arrive(PLAYER, 25 * MICRO)
        self.funding.step()
        self.until(lambda: app.money.face == 'arrival')
        self.step(InputAction.A)                # PLAY NOW, straight into the game
        self.assertEqual(app.current, 'game')
        self.step(InputAction.B)
        self.assertEqual(app.current, 'home')

        app.home.focus = 1
        self.step(InputAction.A)
        self.assertEqual(app.money.face, 'confirm')
        self.until(lambda: app.money.armed)
        self.step(InputAction.A)                # the second, deliberate press
        self.assertEqual(app.money.face, 'paying')
        self.funding.step()
        self.until(lambda: app.money.face == 'receipt')
        self.assertEqual(app.game.ticket.paid, 25 * MICRO - FEE)

        # The board is handed the run before it is opened, so the read the
        # opening fires cannot replace the picture we came to watch change.
        self.standings.append(AFTER)
        self.until(lambda: app.current == 'board')
        self.assertTrue(app.board.waiting)
        self.assertEqual(app.board.my_rank(app.board.feed.rows), 6)

        app.board.feed.refresh()                # the scorekeeper writes
        self.until(lambda: app.board.move is not None)
        move = app.board.move
        self.assertEqual((move.start, move.end, move.up), (5, 2, True))
        self.until(lambda: app.board.again)
        self.assertEqual(app.board.my_rank(app.board.feed.rows), 3)
        self.step(InputAction.A)                # PLAY AGAIN closes the loop
        self.assertEqual((app.current, app.money.face), ('money', 'waiting'))


if __name__ == '__main__':
    unittest.main()

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
from input import InputAction
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


class ArcScreenTests(unittest.TestCase):
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

    def test_the_wallet_screen_draws_before_and_during_a_session(self):
        self.game.open_wallet()
        self.game.draw(pygame.Surface((480, 320)))       # QR code, waiting
        self.funding.step()
        self.chain.arrive(PLAYER, MICRO)
        self.funding.step()
        self.game.sync_funding()
        self.assertEqual(self.game.model.wallet.balance, MICRO - FEE)
        self.assertIn('FROM 0x7ee8..CCac', self.game.banner()[0])
        self.game.open_wallet()
        self.game.draw(pygame.Surface((480, 320)))       # balance, cash out

    def test_a_deposit_on_the_qr_screen_goes_back_to_the_launcher(self):
        from games.box import handle_box_events
        self.game.open_wallet()
        self.funding.step()
        self.chain.arrive(PLAYER, MICRO)
        self.funding.step()
        self.game.sync_funding()
        self.assertFalse(self.game.wallet_open)
        # The A that was headed for CASH OUT in the same frame is dropped.
        self.assertEqual(handle_box_events(self.game, [], [InputAction.A]), 'funded')
        self.assertIsNone(self.funding.pending_cashout)
        self.assertTrue(self.funding.in_session)
        self.assertIsNone(handle_box_events(self.game, [], []))    # once only

    def test_a_deposit_during_play_stays_in_play(self):
        from games.box import handle_box_events
        self.funding.step()
        self.chain.arrive(PLAYER, MICRO)
        self.funding.step()
        self.game.sync_funding()
        self.assertIsNone(handle_box_events(self.game, [], []))

    def test_a_in_the_wallet_cashes_out(self):
        self.funding.step()
        self.chain.arrive(PLAYER, MICRO)
        self.funding.step()
        self.game.sync_funding()
        self.game.open_wallet()
        self.game.handle_action(InputAction.A)
        self.assertEqual(self.funding.pending_cashout, MICRO - FEE)
        self.funding.step()
        self.game.sync_funding()
        self.assertEqual(self.chain.paid, [(PLAYER, MICRO - FEE)])
        self.assertIn('SENT 0.99 TO 0x7ee8..CCac', self.game.banner()[0])

    def test_a_named_player_is_shown_by_their_name(self):
        self.funding.lookup = lambda player: 'fancy-panda.tick.eth'
        self.funding.step()
        self.chain.arrive(PLAYER, MICRO)
        self.funding.step()
        self.game.sync_funding()
        self.assertIn('WELCOME fancy-panda.tick.eth', self.game.banner()[0])
        self.game.open_wallet()
        self.game.draw(pygame.Surface((480, 320)))       # CASH OUT TO fancy-panda.tick.eth
        self.game.handle_action(InputAction.A)
        self.funding.step()
        self.game.sync_funding()
        self.assertIn('SENT 0.99 TO fancy-panda.tick.eth', self.game.banner()[0])


if __name__ == '__main__':
    unittest.main()

"""The real-money state machine, with a fake chain: no network, no keys.

This is the point of keeping every on-chain call behind `Chain`. The rules that
decide whether a player's deposit becomes a session, and whether their winnings
come back, are testable on a laptop in milliseconds.
"""
import tempfile
import unittest
from pathlib import Path

from tick.chain import House, Incoming
from tick.escrow import EscrowFunding, Session
from tick.money import MICRO, Wallet


class FakeChain:
    """Everything `Chain` does, in memory."""

    def __init__(self, free=10_000 * MICRO, cap_bps=40_000, most=25 * MICRO, paused=False):
        self.address = '0x' + '11' * 20
        self.head = 100
        self.log: list[tuple[int, Incoming]] = []
        self.opened: list[tuple] = []
        self.closed: list[tuple] = []
        self.sent_back: list[tuple] = []
        self.approved = False
        self._allowance = 0
        self.house_state = House(free, cap_bps, most, paused)
        self.open_ids: set[int] = set()
        self.next_id = 1

    def block(self): return self.head
    def send(self, sender, amount, key=None):
        """A USDC transfer into the device, in the next block."""
        self.head += 1
        self.log.append((self.head, Incoming(sender, amount, key or f'0xtx{len(self.log)}:0')))
    def incoming(self, first, last):
        return [i for block, i in self.log if first <= block <= last]
    def house(self): return self.house_state
    def allowance(self): return self._allowance
    def approve_escrow(self):
        self.approved, self._allowance = True, 2 ** 256 - 1
        return '0xapprove'
    def session_open(self, sid): return sid in self.open_ids
    def open_for(self, player, amount):
        sid, self.next_id = self.next_id, self.next_id + 1
        reserve = amount * self.house_state.win_cap_bps // 10_000
        self.open_ids.add(sid)
        self.opened.append((sid, player, amount))
        return sid, amount, reserve, f'0xopen{sid}'
    def close(self, sid, final):
        self.open_ids.discard(sid)
        self.closed.append((sid, final))
        return final, f'0xclose{sid}'
    def transfer(self, to, amount):
        self.sent_back.append((to, amount))
        return '0xrefund'


class EscrowCase(unittest.TestCase):
    def funding(self, chain=None, **kwargs):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        chain = chain or FakeChain()
        return EscrowFunding('arc-testnet', chain=chain, state_dir=Path(self.folder.name),
                             gas_fee=10_000, start=False, **kwargs), chain


class TestDeposits(EscrowCase):
    def test_a_deposit_opens_a_session_in_the_senders_name(self):
        funding, chain = self.funding()
        player = '0x' + 'ab' * 20
        funding.step()                       # first pass just marks where to read from
        chain.send(player, 5 * MICRO)
        funding.step()
        self.assertEqual(len(chain.opened), 1)
        sid, opened_for, amount = chain.opened[0]
        self.assertEqual(opened_for, player)
        self.assertEqual(amount, 5 * MICRO - 10_000)     # the gas fee is kept
        self.assertTrue(chain.approved)

    def test_the_same_transfer_is_never_taken_twice(self):
        funding, chain = self.funding()
        funding.step()
        chain.send('0x' + 'ab' * 20, 5 * MICRO)
        funding.step()
        funding.last_block -= 5              # as a retried range would
        funding.step()
        self.assertEqual(len(chain.opened), 1)

    def test_dust_below_the_gas_fee_is_kept_not_opened(self):
        funding, chain = self.funding()
        funding.step()
        chain.send('0x' + 'ab' * 20, 5_000)
        funding.step()
        self.assertEqual(chain.opened, [])
        self.assertEqual(chain.sent_back, [])

    def test_money_the_house_cannot_back_goes_straight_home(self):
        funding, chain = self.funding(FakeChain(free=1))
        player = '0x' + 'ab' * 20
        funding.step()
        chain.send(player, 5 * MICRO)
        funding.step()
        self.assertEqual(chain.opened, [])
        self.assertEqual(chain.sent_back, [(player, 5 * MICRO - 10_000)])

    def test_a_deposit_over_the_maximum_goes_straight_home(self):
        funding, chain = self.funding(FakeChain(most=MICRO))
        player = '0x' + 'ab' * 20
        funding.step()
        chain.send(player, 5 * MICRO)
        funding.step()
        self.assertEqual(chain.opened, [])
        self.assertEqual(len(chain.sent_back), 1)

    def test_the_device_ignores_money_from_itself(self):
        funding, chain = self.funding()
        funding.step()
        chain.send(chain.address, 5 * MICRO)
        funding.step()
        self.assertEqual(chain.opened, [])


class TestBalanceAndCap(EscrowCase):
    def test_an_opened_session_credits_the_wallet_and_sets_a_cap(self):
        funding, chain = self.funding()
        funding.step()
        chain.send('0x' + 'ab' * 20, 5 * MICRO)
        funding.step()
        wallet = Wallet(0, funding)
        funding.sync(wallet)
        self.assertEqual(wallet.balance, 5 * MICRO - 10_000)
        # deposit + reserve: what the escrow will actually pay out.
        self.assertEqual(wallet.cap, funding.sessions[0].cap)
        self.assertGreater(wallet.cap, wallet.balance)

    def test_no_session_means_no_cap_so_demo_play_is_unlimited(self):
        funding, _ = self.funding()
        self.assertIsNone(funding.cap)


class TestCashOut(EscrowCase):
    def test_cashing_out_closes_the_session_and_pays_the_final_balance(self):
        funding, chain = self.funding()
        funding.step()
        chain.send('0x' + 'ab' * 20, 5 * MICRO)
        funding.step()
        wallet = Wallet(0, funding)
        funding.sync(wallet)
        wallet.credit(2 * MICRO)              # won some
        funding.sync(wallet)
        final = wallet.balance
        self.assertTrue(funding.cash_out(wallet))
        self.assertEqual(wallet.balance, 0)
        funding.step()
        self.assertEqual(chain.closed, [(1, final)])
        self.assertIsNone(funding.pending_cashout)

    def test_cashing_out_with_nothing_open_does_nothing(self):
        funding, _ = self.funding()
        self.assertFalse(funding.cash_out(Wallet(0, funding)))

    def test_an_interrupted_cash_out_finishes_on_the_next_run(self):
        funding, chain = self.funding()
        funding.step()
        chain.send('0x' + 'ab' * 20, 5 * MICRO)
        funding.step()
        wallet = Wallet(0, funding)
        funding.sync(wallet)
        funding.cash_out(wallet)
        # Restart from the saved state, as a power cut would.
        again = EscrowFunding('arc-testnet', chain=chain, state_dir=funding.state_dir,
                              gas_fee=10_000, start=False)
        self.assertIsNotNone(again.pending_cashout)
        again.step()
        self.assertEqual(len(chain.closed), 1)

    def test_a_session_closed_while_the_device_was_off_is_forgotten(self):
        funding, chain = self.funding()
        funding.sessions = [Session(9, '0x' + 'ab' * 20, MICRO, MICRO)]
        funding.balance = MICRO
        funding.step()                        # session 9 is not open on chain
        self.assertEqual(funding.sessions, [])
        self.assertEqual(funding.balance, 0)


class TestState(EscrowCase):
    def test_state_survives_a_restart(self):
        funding, chain = self.funding()
        funding.step()
        chain.send('0x' + 'ab' * 20, 5 * MICRO)
        funding.step()
        again = EscrowFunding('arc-testnet', chain=chain, state_dir=funding.state_dir,
                              gas_fee=10_000, start=False)
        self.assertEqual(len(again.sessions), 1)
        self.assertEqual(again.balance, funding.balance)

    def test_state_from_another_escrow_is_ignored(self):
        funding, chain = self.funding()
        funding.step()
        chain.send('0x' + 'ab' * 20, 5 * MICRO)
        funding.step()
        import json
        data = json.loads(funding.state_path.read_text())
        data['escrow'] = '0x' + 'ff' * 20
        funding.state_path.write_text(json.dumps(data))
        again = EscrowFunding('arc-testnet', chain=chain, state_dir=funding.state_dir,
                              gas_fee=10_000, start=False)
        self.assertEqual(again.sessions, [])

    def test_the_qr_code_is_an_eip_681_send_to_the_device(self):
        funding, chain = self.funding()
        self.assertTrue(funding.qr_text.startswith(f'ethereum:{chain.address}@'))


if __name__ == '__main__':
    unittest.main()

"""TICK SDK -- build a crypto arcade game for the handheld in one file.

    from tick import Game, run

    class MyGame(Game):
        title = 'MY GAME'
        window_s = 10.0

        def on_action(self, ctx, action):
            if action.name == 'A':
                ctx.bet(ctx.price, ctx.price * 1.001)

        def draw(self, ctx, screen):
            from tick.hud import clear, draw_hud
            clear(screen)
            draw_hud(ctx, screen)

    run(MyGame())

What you get for those lines: a live price feed (simulated, an exchange, or
on-chain pools), a round clock that never stops, odds priced from measured
volatility, an integer-USDC wallet that can be paper money or real escrowed
funds, a rotary encoder and two buttons, a 480x320 canvas that rotates itself
onto a portrait panel, and a full set of arcade sound cues.

Layers, low to high -- take any one of them on its own:

    tick.feeds       PriceTick, open_feed, PoolStream      where numbers come from
    tick.market      Market                                what they mean
    tick.pricing     probability, multiple                 what a bet is worth
    tick.money       Wallet, micro-USDC                    what money is
    tick.escrow      EscrowFunding                         real money, settled on-chain
    tick.identity    Standings, name_of                    who the player is
    tick.rounds      RoundClock                            when bets settle
    tick.bets        BetBook                               placing and paying
    tick.game        Game, GameContext                     what you write
    tick.runtime     run()                                 the loop
    tick.hud/ui      Ladder, draw_hud, Sounds              what it looks like
"""
from __future__ import annotations

__version__ = '0.1.0'

from .bets import Bet, BetBook, Settlement
from .env import load_env_file, load_env_near
from .feeds import (Block, PoolBook, PoolPrice, PoolStream, Recorder, ReplayFeed,
                    SOURCES, open_feed)
from .game import Game, GameContext
from .input import InputAction
from .market import Market
from .money import (MICRO, DemoFunding, Deposit, Wallet, format_usdc, parse_usdc,
                    places_for, stake_micro, to_micro)
from .pricing import multiple, probability, scale_to_window, sigma
from .rounds import Round, RoundClock
from .runtime import Runtime, run
from .ticks import ASSETS, Asset, PriceTick, current_asset

__all__ = [
    '__version__',
    # writing a game
    'Game', 'GameContext', 'run', 'Runtime', 'InputAction',
    # the market
    'PriceTick', 'Asset', 'ASSETS', 'current_asset', 'open_feed', 'SOURCES', 'Market',
    'PoolStream', 'PoolBook', 'Block', 'PoolPrice', 'Recorder', 'ReplayFeed',
    # odds
    'probability', 'multiple', 'sigma', 'scale_to_window',
    # money
    'Wallet', 'DemoFunding', 'Deposit', 'MICRO', 'to_micro', 'parse_usdc',
    'format_usdc', 'places_for', 'stake_micro',
    # rounds and bets
    'RoundClock', 'Round', 'Bet', 'BetBook', 'Settlement',
    # settings
    'load_env_file', 'load_env_near',
]

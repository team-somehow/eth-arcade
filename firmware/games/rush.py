"""RUSH: a continuously cranked pixel market rider, with a dummy USDC wallet."""
from __future__ import annotations
import math
import os
import time
import pygame
from games.box_run import NAVY, PANEL, GRID, CREAM, MUTED, YELLOW, MINT, RED, Sounds, label, diamond, footer
from games.rush_model import RushModel
from input import InputAction, event_position
from markets.feed import CoinbaseFeed, SimulatedFeed


def rider(s: pygame.Surface, x: int, y: int, boost: float, clock: float):
    """Original tiny pixel motorbike; its engine animation reflects hand motion."""
    for wheel in (x-15, x+18):
        pygame.draw.circle(s, CREAM, (wheel,y), 8)
        pygame.draw.circle(s, NAVY, (wheel,y), 4)
        if int(clock*12)%2:
            pygame.draw.line(s, MUTED, (wheel-4,y), (wheel+4,y), 2)
    pygame.draw.lines(s, YELLOW, False, [(x-15,y),(x-3,y-13),(x+8,y),(x-15,y)], 4)
    pygame.draw.line(s, YELLOW, (x+8,y), (x+18,y-15), 4)
    pygame.draw.line(s, CREAM, (x+12,y-18), (x+22,y-18), 3)
    pygame.draw.rect(s, MINT, (x-5,y-29,12,13))
    pygame.draw.line(s, MINT, (x+4,y-24), (x+15,y-18), 4)
    pygame.draw.rect(s, CREAM, (x-3,y-39,13,11))
    pygame.draw.rect(s, YELLOW, (x-5,y-41,17,6))
    pygame.draw.rect(s, NAVY, (x+5,y-34,6,3))
    if boost > .12:
        length = int(8 + boost*22 + 4*math.sin(clock*30))
        pygame.draw.polygon(s, YELLOW, [(x-15,y-14),(x-24-length,y-10),(x-20,y-4)])
        pygame.draw.polygon(s, RED, [(x-21,y-12),(x-20-length*.7,y-10),(x-22,y-6)])


class RushGame:
    def __init__(self, seed: int | None = None, sound: bool = True, source: str | None = None):
        source = source or os.environ.get('TICK_MARKET_SOURCE', 'sim')
        if source not in ('sim', 'coinbase'):
            raise ValueError('TICK_MARKET_SOURCE must be sim or coinbase')
        self.feed = CoinbaseFeed() if source == 'coinbase' else SimulatedFeed(seed)
        self.model = RushModel()
        self.sounds = Sounds() if sound else None
        self.source = source
        self.clock = time.monotonic()
        self.animation = 0.0
        self.distance = 0.0
        self.held: dict[int, float] = {}
        self.wallet_open = False
        self.amount_index = 1
        self.amounts = [10,25,100]
        self.message = ''
        self.message_until = 0.0
        self.last_sound_at = 0.0

    def enter(self):
        self.held.clear()
        self.wallet_open = False

    def close(self):
        self.feed.close()

    def play(self, name: str):
        if self.sounds:
            self.sounds.play(name)

    def open_wallet(self):
        if not self.model.active:
            self.wallet_open = True
            self.held.clear()

    def handle_action(self, action: InputAction) -> str | None:
        m = self.model
        now = self.clock
        if action == InputAction.QUIT:
            return 'quit'
        if self.wallet_open:
            if action in (InputAction.UP, InputAction.DOWN):
                self.amount_index = (self.amount_index + (1 if action == InputAction.UP else -1)) % 3
            elif action == InputAction.A:
                amount = self.amounts[self.amount_index]
                m.wallet.load(amount)
                self.wallet_open = False
                self.message, self.message_until = f'+{amount} DEMO USDC LOADED', now+2
                self.play('select')
            elif action == InputAction.B:
                self.wallet_open = False
            return None
        if action in (InputAction.UP, InputAction.DOWN):
            m.crank(1 if action == InputAction.UP else -1, now)
            if m.active and now-self.last_sound_at > .09:
                self.play('move')
                self.last_sound_at = now
        elif action == InputAction.A:
            if m.wallet.balance < m.STAKE and not m.active:
                self.open_wallet()
            elif m.start(now):
                self.play('lock')
                self.message = ''
            elif not m.active:
                self.message, self.message_until = 'WAITING FOR FRESH PRICE', now+2
        elif action == InputAction.B:
            if m.active:
                m.request_exit(now)
                self.held.clear()
            else:
                self.held.clear()
                return 'home'
        return None

    def update(self, dt: float):
        self.clock = time.monotonic()
        self.animation += dt
        m = self.model
        old_rides = m.rides
        for key in list(self.held):
            self.held[key] -= dt
            if self.held[key] <= 0:
                self.handle_action(InputAction.UP if key in (pygame.K_UP,pygame.K_w) else InputAction.DOWN)
                if key in self.held:
                    self.held[key] = .06
        # Stale exposure cannot be silently repriced before its exit is marked.
        m.update(dt, self.clock)
        for tick in self.feed.poll(dt, self.clock):
            m.on_tick(tick, self.clock)
        if old_rides != m.rides:
            self.play('hit' if m.last_pnl is not None and m.last_pnl >= 0 else 'miss')
            self.held.clear()
        self.distance += dt * (12 + 115*m.throttle if m.active else 8)

    def handle_touch(self, pos: tuple[int,int]):
        x,y = pos
        if y >= 274:
            return self.handle_action(InputAction.B if x < 240 else InputAction.A)
        if y < 38 and x >= 260:
            self.open_wallet()
        elif self.wallet_open:
            return self.handle_action(InputAction.UP if x >= 240 else InputAction.DOWN)
        elif 105 <= y < 242:
            return self.handle_action(InputAction.UP if x >= 240 else InputAction.DOWN)
        return None

    def draw(self, s: pygame.Surface, _fonts: dict | None = None):
        m = self.model
        s.fill(NAVY)
        label(s, 'RUSH', 14, 6, 23, CREAM)
        label(s, f'{m.wallet.balance:.2f} DEMO USDC', 239, 11, 16, MINT)
        pygame.draw.line(s, GRID, (14,36),(466,36))
        if self.wallet_open:
            self.draw_wallet(s)
            return
        mode = 'SIM + PAPER' if self.source == 'sim' else 'LIVE + PAPER'
        label(s, mode, 14, 43, 15, MUTED)
        if m.tick:
            label(s, f'ETH ${m.tick.price:,.2f}', 242, 43, 17, CREAM)
        else:
            label(s, 'CONNECTING...', 258,43,16,YELLOW)
        side = 'LONG' if m.side == 1 else 'SHORT'
        if m.active:
            label(s, f'{m.pnl:+.4f}', 14, 63, 29, MINT if m.pnl>=0 else RED)
            label(s, 'USDC', 179, 77, 14, MUTED)
            label(s, f'{m.leverage:04.1f}x', 354, 64, 28, YELLOW)
        else:
            label(s, f'{side} / 10 IN', 14, 68, 23, YELLOW)
            label(s, 'CRANK TO RIDE', 266, 73, 17, CREAM)
        self.draw_world(s)
        if m.active:
            pygame.draw.rect(s, PANEL, (14,211,452,24), border_radius=3)
            for i in range(20):
                c = (YELLOW if i<15 else RED) if i < round(m.throttle*20) else GRID
                pygame.draw.rect(s,c,(19+i*22,215,17,16))
            if m.phase == 'exit_pending':
                label(s, 'EXIT PENDING / WAITING FOR FEED', 240,242,16,RED,True)
            elif not m.fresh(self.clock):
                label(s, 'FEED STALE / NO NEW EXPOSURE',240,242,16,RED,True)
            else:
                label(s, 'KEEP TURNING',14,243,18,YELLOW)
                label(s, f'{int(m.elapsed):02d}s / MAX 10x',285,246,15,MUTED)
            footer(s, '< EXIT', 'RIDING')
        else:
            if self.clock < self.message_until:
                text, color = self.message, MINT
            elif m.last_pnl is not None:
                text, color = f'LAST {m.last_pnl:+.4f} / {m.last_reason.upper()}', MINT if m.last_pnl>=0 else RED
            else:
                text, color = 'HOLD UP = CRANK / DOWN = SHORT', MUTED
            label(s, text[:43], 14,214,15,color)
            label(s, 'YELLOW STARTS. RED EXITS.',14,242,17,CREAM)
            footer(s, '< HOME', 'RIDE >' if m.wallet.balance>=m.STAKE else 'LOAD >')
        if m.tick and not m.fresh(self.clock):
            pygame.draw.rect(s, NAVY, (74,135,332,36))
            label(s, 'PRICE STALE',240,140,23,RED,True)

    def draw_world(self, s: pygame.Surface):
        m = self.model
        plot = pygame.Rect(14,105,452,98)
        pygame.draw.rect(s, PANEL, plot)
        clip = s.get_clip()
        s.set_clip(plot)
        # The city/engine motion is arcade animation, not extra market movement.
        for i in range(14):
            x = int((i*43-self.distance*.3)%560)-40
            height = 15+(i*17)%52
            pygame.draw.rect(s,GRID,(x,199-height,27,height))
            if i%3==0:
                pygame.draw.rect(s,(59,74,73),(x+9,204-height,4,4))
        prices = list(m.history)
        if len(prices)>1:
            lo,hi = min(prices),max(prices)
            span = max(hi-lo, prices[-1]*.001)
            mid = (lo+hi)/2
            points = [(14+int(i/(len(prices)-1)*451),round(170-(p-mid)/span*42)) for i,p in enumerate(prices)]
            pygame.draw.lines(s,CREAM,False,points,3)
            road_y = min(points,key=lambda point:abs(point[0]-135))[1]
        else:
            road_y=177
            pygame.draw.line(s,CREAM,(14,road_y),(466,road_y),3)
        rider(s,135,road_y-8,m.throttle,self.animation)
        if m.throttle>.2:
            for i in range(7):
                x=int((i*73-self.distance*2)%500)
                y=110+(i*19)%70
                pygame.draw.line(s,MUTED,(x,y),(x+int(5+m.throttle*14),y),1)
        if len(prices)>1:
            diamond(s,447,points[-1][1]-16,YELLOW)
        s.set_clip(clip)

    def draw_wallet(self,s:pygame.Surface):
        label(s,'LOAD DEMO USDC',240,53,27,YELLOW,True)
        label(s,'LOCAL TEST BALANCE / NO REAL MONEY',240,92,15,MUTED,True)
        for i,amount in enumerate(self.amounts):
            rect=pygame.Rect(16+i*155,126,140,67)
            pygame.draw.rect(s,YELLOW if i==self.amount_index else PANEL,rect,border_radius=4)
            label(s,f'+{amount}',rect.centerx,142,28,NAVY if i==self.amount_index else CREAM,True)
        label(s,'UP / DOWN TO CHOOSE',240,208,17,MUTED,True)
        label(s,'No wallet or transfer is connected.',240,240,15,CREAM,True)
        footer(s,'< BACK','LOAD >')


def handle_rush_events(game: RushGame, events: list, actions: list[InputAction]) -> str | None:
    for event in events:
        if event.type == pygame.WINDOWFOCUSLOST:
            game.held.clear()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_f:
                game.open_wallet()
            elif event.key in (pygame.K_UP,pygame.K_DOWN,pygame.K_w,pygame.K_s) and not game.wallet_open:
                game.held[event.key]=.10
        elif event.type == pygame.KEYUP:
            game.held.pop(event.key,None)
        pos=event_position(event)
        if pos is not None:
            target=game.handle_touch(pos)
            if target:
                return target
    for action in actions:
        target=game.handle_action(action)
        if target:
            return target
    return None

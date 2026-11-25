# -*- coding: utf-8 -*-
"""
NHC — 전투 프로토타입 (Python / tkinter 단일 파일)

실행:  python nhc_battle.py
필요:  파이썬 3.8+ (tkinter 포함). 외부 패키지 없음.

이번 갱신에서 바뀐 점
---------------------
3. C 재조정 — 3스킬 '파멸의 예연': 지정한 적이 3턴간 받는 피해 1.5배 (격파 상태와 곱연산 중첩).
4. 연출/색상 — N 3스킬 '진입 저지 저격'(분홍), H 3스킬 '진-걸착'(파란).
5. 어드민 패널 — 전투 중 'maki' 입력으로 열림(ESC 로 닫기). 탭 구조(이동/증강/기타)로 재구성.
   - 이동: 스테이지1(1~5)·보스1(6)·스테이지2(7~11)·보스2(12) 즉시 이동, 아군 상태 완전 복구.
   - 기타: 아군 완전 회복 / SP 최대 / 현재 적 전멸.
6. 스테이지 2(PHASE 7~12) — 몹 이름과 배경색이 바뀌어 새 스테이지임을 체감할 수 있다.
   보스를 잡고 다음 스테이지로 넘어갈 때 'STAGE n' 전환 배너가 뜬다.
7. 보스 '코즈믹:혼돈' — 체력 850 / 격파체력 180 / 기본 공격 24(하향), 화면 전폭 카드.
   - 한 라운드에 3번 행동한다. 단, SP가 6이 되어 광역기를 쓰는 라운드에는 그 행동 하나만 한다
     (다른 공격과 함께 하지 않음). 행동 지정 단계에서 '혼돈이 느껴진다' 경고가 먼저 떠서
     방어/회피로 대비할 수 있다. 광역기 [차원 붕괴] — 아군 전원 35 피해.
   - 이후 6의 배수 페이즈마다 더 강해진 개체로 재등장.
8. 이전 갱신(속도 시스템·즉시 SP 반영 등)은 그대로 유지.
9. 형상해석(가챠) — 전투 중 E 키로 여는 창. 적 처치와 스테이지 클리어로 조각을 획득한다.
    ★★ 형상(검사 N·수호자 H·예언자 C)을 해석 화면에서 장착하고 전투에 사용할 수 있다.
"""

import math
import os
import random
import threading
import time
import tkinter as tk
import tkinter.font as tkfont

from nhc_data import *


from nhc_gacha import GachaMixin
from nhc_library import LibraryMixin
from nhc_workshop import WorkshopMixin
from nhc_admin.panel import AdminMixin
from nhc_admin.aspects import AdminAspectsMixin


class Unit:
    def __init__(self, uid, name, role, side, hp, brk, skills=None,
                 normal_dmg=10, skill_dmg=0, skill_cost=3):
        self.id = uid
        self.name = name
        self.role = role
        self.side = side
        self.hp = self.max_hp = hp
        self.brk = self.max_brk = brk
        self.sp = 0
        self.max_sp = MAX_SP
        self.status = None          # 'guard' / 'evade' / None
        self.broken = False
        self.broken_skips = 0
        self.curse_turns = 0        # 파멸의 예연 — 남은 저주 턴 수
        self.fate_turns = 0         # 운명 — 남은 지속 피해 횟수
        self.stun_turns = 0         # 카즈나 — 행동 불가 횟수
        self.immortal_turns = 0     # 불사의 가호 — 남은 불사 턴 수 (체력 1 밑으로 안 내려감)
        self.skills = skills or []
        self.aspect_id = "%s_base" % uid.lower() if side == "ally" else None
        self.fate_hp_spent = 0
        self.fate_ready = False
        self.hero_buff = False
        self.hero_revive_used = False
        self.hero_passive_shield_gained = 0
        self.hero_echo_used = False
        self.hero_echo_channel = None
        self.imperial_prayer = 0
        self.imperial_princess = False
        self.imperial_command_used = False
        self.imperial_hope_cooldown = 0
        self.imperial_guardian_round = None
        self.imperial_guardian_empty_reward_round = None
        self.imperial_safety_round = None
        self.imperial_safety_used = False
        self.imperial_n = False
        self.imperial_guardian_target = None
        self.shield = 0
        self.speed_penalty = 0
        self.ub_foresight = 0       # 언더보스/C — 예지
        self.ub_overheat = -1       # 예지안 과열 (-1 = 비활성)
        self.ub_ammo = 0            # 가속탄
        self.ub_counter_round = None
        self.ub_disposal_used = False
        self.ub_refill_next = False
        self.ub_refill_used = False
        self.ma_view = 0            # 마에스트로/H — 조망
        self.ma_view_dec = 0        # 이번 턴에 감소한 조망량 (턴당 최대 4)
        self.ma_closing_used = False
        self.ma_material = 0        # 생체재료
        self.ma_masterpiece = False  # 걸작 — 공격력 +5
        self.ma_melody = False      # 선율 — 속도 +1 · 공격력 +5
        self.rib_turns = 0          # 간이늑골 — 속도 주사위 최대값 절반 감소 (남은 턴)
        self.paint = 0              # 화가 N — 적에게 쌓이는 물감 (최대 5)
        self.fun_turns = 0          # 재미난 장난 — 매턴 체력 10 회복, 이후 1 감소
        self.danger_turns = 0       # 위험한 장난 — 공격력 +15, 턴 종료 시 1 감소
        self.speed_minus = 0        # 블루 — 다음턴 속도 -n (최소 1)
        self.speed_fix = False      # 너희를 위한 게임 — 다음턴 속도 1 고정
        self.orch_aud = 0.0         # Orchestra/D — 관객 (최대 20, 0.5 단위)
        self.orch_amt = 1           # 포르티시모 — 연타로 정한 소모 SP
        self.orch_finale = 0        # 피날레 남은 턴 (0 = 아님)
        self.orch_finale_uses = 0   # 피날레 스킬 사용 횟수
        self.orch_ring = 0          # 악장의 원 (0 없음 / 1 / 2)
        self.orch_break_immune = False   # 이번 전투 격파 면역
        self.ult_gauge = 0          # 환상도 (%)
        self.ult_use_round = None   # 환상을 지정한 라운드 (재사용 대기 계산용)
        self.bloom_turns = 0        # 개화 — 받는 피해 +20%, 턴 종료시 1 감소
        self.burn = 0               # 화상 — 라운드 시작시 수치만큼 피해 후 전부 제거
        self.bs_wrap = 0            # 큰누님/N — 포장
        self.bs_leva = False        # 큰누님/N — 레바테인 상태
        self.bs_fun = 0             # 큰누님/N — 달아오르는 재미
        self.bs_counter_uses = 0    # 큰누님/N — 반격 사용 횟수 (2회마다 재미 -1)
        self.or_unlock = 1          # 신탁 대행자/H — 해금 단계 (1~4)
        self.or_hermes = 0          # 헤르메스 (9 에 도달하면 Furioso-Replica)
        self.or_grace = 0           # 가호 (로그에만 표시)
        self.or_furioso = False     # 스킬 3 → 3-2 변경 여부
        self.or_used = set()        # 사용한 무기 id
        self.or_hermes_turn = 0     # 이번 턴 무기로 얻은 헤르메스 횟수 (턴당 3회)
        self.or_grace_round = None  # 지령 가호를 마지막으로 얻은 라운드 (턴당 1회)
        self.or_block_round = None  # Furioso 를 지정한 라운드 — 지령/헤르메스 획득 없음
        self.or_turn_dmg = 0        # 이번 턴 적에게 입힌 피해
        self.or_dmg_done = False    # 이번 턴 '40 이상 피해' 지령 수행 여부
        self.or_iv_bonus_used = False
        self.focused = None
        self.normal_dmg = normal_dmg
        self.skill_dmg = skill_dmg
        self.skill_cost = skill_cost
        self.speed = 0
        self.plan = None            # dict(type=..., idx=..., target=...)
        self.is_boss = False
        self.aoe_dmg = 0            # 보스 광역기 피해
        self.plans = []             # 보스 전용 — 한 라운드에 실행할 행동 목록

    @property
    def alive(self):
        return self.hp > 0


# ----------------------------------------------------------------------------
# 게임
# ----------------------------------------------------------------------------
class ScaledCanvas(tk.Canvas):
    """1040x830 논리 좌표로 그리면 창 크기에 맞춰 일정 비율로 확대/축소해서 그리는 캔버스."""

    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self.s = 1.0
        self.ox = 0.0
        self.oy = 0.0
        self._fonts = {}

    def set_view(self, w, h):
        self.s = max(0.3, min(w / float(WIN_W), h / float(WIN_H)))
        self.ox = (w - WIN_W * self.s) / 2.0
        self.oy = (h - WIN_H * self.s) / 2.0

    def unscale_event(self, ev):
        ev.x = (ev.x - self.ox) / self.s
        ev.y = (ev.y - self.oy) / self.s

    def _pts(self, args):
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            args = tuple(args[0])
        return [v * self.s + (self.ox if i % 2 == 0 else self.oy) for i, v in enumerate(args)]

    def _sfont(self, font):
        s = self.s
        if isinstance(font, tkfont.Font):
            fam, size, wt = font.cget("family"), int(font.cget("size")), font.cget("weight")
            ns = int(round(size * s)) or (1 if size > 0 else -1)
            key = (fam, ns, wt)
            f = self._fonts.get(key)
            if f is None:
                f = tkfont.Font(family=fam, size=ns, weight=wt)
                self._fonts[key] = f
            return f
        if isinstance(font, (tuple, list)) and len(font) >= 2 and isinstance(font[1], (int, float)):
            size = font[1]
            ns = int(round(size * s)) or (1 if size > 0 else -1)
            return (font[0], ns) + tuple(font[2:])
        return font

    def _kw(self, kw):
        if "width" in kw and isinstance(kw["width"], (int, float)):
            kw["width"] = kw["width"] * self.s
        if "font" in kw:
            kw["font"] = self._sfont(kw["font"])
        return kw

    def create_rectangle(self, *a, **kw):
        # 화면 전체를 덮는 어두운 막은 여백까지 덮는다
        if len(a) == 4 and tuple(a) == (0, 0, WIN_W, WIN_H):
            w, h = self.winfo_width(), self.winfo_height()
            if w > 10 and h > 10:
                return super().create_rectangle(-2, -2, w + 2, h + 2, **self._kw(kw))
        return super().create_rectangle(*self._pts(a), **self._kw(kw))

    def create_line(self, *a, **kw):
        return super().create_line(*self._pts(a), **self._kw(kw))

    def create_oval(self, *a, **kw):
        return super().create_oval(*self._pts(a), **self._kw(kw))

    def create_polygon(self, *a, **kw):
        return super().create_polygon(*self._pts(a), **self._kw(kw))

    def create_text(self, *a, **kw):
        return super().create_text(*self._pts(a), **self._kw(kw))

    def create_image(self, *a, **kw):
        return super().create_image(*self._pts(a), **kw)

    def coords(self, *args):
        item, rest = args[0], args[1:]
        if not rest:
            raw = super().coords(item)
            return [(v - (self.ox if i % 2 == 0 else self.oy)) / self.s
                    for i, v in enumerate(raw)]
        return super().coords(item, *self._pts(rest))

    def move(self, item, dx, dy):
        super().move(item, dx * self.s, dy * self.s)

    def itemconfigure(self, tagOrId, cnf=None, **kw):
        if cnf is None and kw:
            kw = self._kw(kw)
        return super().itemconfigure(tagOrId, cnf, **kw)

    itemconfig = itemconfigure


class NHCBattle(GachaMixin, LibraryMixin, WorkshopMixin, AdminMixin, AdminAspectsMixin):
    title_screen = True      # 켜면 타이틀부터
    _enter = 0.0             # 로비 진입 시각 (페이드인용)
    _t0 = None
    inv_open = False         # 인벤토리(TAB) 열림 여부
    inv_sel = 0
    formation_open = False   # R 키 편성 창
    form_sel = 0             # 편성 창에서 선택된 슬롯
    ALLY_IDS = ["N", "H", "C"]
    ENEMY_IDS = ["E1", "E2", "E3"]

    def __init__(self, root):
        self.root = root
        root.title("PROJECT NHC")
        root.configure(bg=BG)
        root.resizable(True, True)
        root.minsize(640, 512)

        fams = set(tkfont.families(root))
        self.ff = next((f for f in ["Malgun Gothic", "Apple SD Gothic Neo", "NanumGothic",
                                    "Noto Sans CJK KR", "Noto Sans KR", "AppleGothic"]
                        if f in fams), "TkDefaultFont")
        self.fm = next((f for f in ["D2Coding", "Consolas", "Menlo", "DejaVu Sans Mono",
                                    "Courier New"] if f in fams), self.ff)

        self.canvas = ScaledCanvas(root, width=WIN_W, height=WIN_H, bg=BG,
                                   highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<MouseWheel>", self.on_wheel)
        self.canvas.bind("<Button-4>", self.on_wheel)
        self.canvas.bind("<Button-5>", self.on_wheel)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        # 폰트는 '픽셀 단위(음수 size)'로 만든다.
        # 포인트로 주면 윈도우 디스플레이 배율(125%/150%)에서 글자만 커져 좌표와 어긋난다.
        self._font_cache = {}
        self.mouse = (0, 0)
        self.tips = {}

        self.effects = []
        self.shakes = {}
        self.buttons = []
        self.card_rects = {}
        self.gacha_open = False
        self.codex_open = False      # 서재 (F 키)
        self.codex_page = "menu"     # 서재 페이지: menu / effect / aspect
        self.codex_sel = None        # 도감에서 클릭해 고정한 효과 인덱스
        self.hover = None
        self.sound = True
        self.log_lines = []
        self.modal = None
        self.overlay = None         # 주사위/배너 오버레이 상태
        self.busy = False           # 애니메이션 진행 중 입력 차단
        self.active_blink_timer = 0.0
        self.active_blink_on = True

        # 어드민 / 흐름 제어
        self.admin = False
        self.admin_kill_pending = False
        self.admin_tab = "move"
        self.key_buf = ""
        self.boss_warning = False   # 광역기 예고 표시
        self.epoch = 0              # 어드민 개입 시 증가 → 예약된 옛 흐름을 무효화
        self._action_epoch = 0
        self.enemy_ids = list(self.ENEMY_IDS)
        self.boss_mode = False

        self.canvas.configure(takefocus=1)
        self.canvas.focus_set()
        root.bind("<Key>", self.on_key)

        self.lobby = False
        self.new_game(to_lobby=True)
        self.tick()

    # ---------------- 초기화 ----------------
    def new_game(self, to_lobby=False):
        self.roster = {
            "N": Unit("N", "N", "저격/근접 전환형", "ally", 100, 50, N_SKILLS),
            "H": Unit("H", "H", "전위 검사", "ally", 100, 50, H_SKILLS),
            "C": Unit("C", "C", "후방 지원", "ally", 100, 50, C_SKILLS),
            "D": Unit("D", "D", "드리머", "ally", 100, 50, D_SKILLS),
        }
        self.__dict__.setdefault("party", ["N", "H", "C"])   # 로비로 돌아가도 편성 유지
        self.ALLY_IDS = list(self.party)
        self.units = {uid: self.roster[uid] for uid in self.ALLY_IDS}
        self.apply_equipped_all()      # 로비에서 장착한 형상 적용
        self.phase = 1
        self.round = 1
        self.epoch = getattr(self, "epoch", 0) + 1
        self._action_epoch = self.epoch
        self.admin = False
        self.key_buf = ""
        self.enemy_ids = list(self.ENEMY_IDS)
        self.boss_mode = False
        self.spawn_wave()
        self.log_lines = []
        self.modal = None
        self.overlay = None
        self.canvas.delete("fx")
        self.effects.clear()
        self.shakes.clear()
        self.game_over = False
        self.state = "idle"
        self.plan_queue = []
        self.pending = None
        self.acting = None
        self.resolve_order = []
        self.aug_atk_bonus = 0
        self.aug_brk_bonus = 0.0
        self.aug_speed_min = 1
        self.aug_dmg_reduction = 0  # 철벽 방어 — 아군이 받는 피해 고정 감소
        self.aug_undying = False    # 불사의 가호 — 사망 직전 체력 1로 버티는 패시브 보유 여부
        self.aug_taken = []         # 1티어(일반 페이즈) 획득 기록
        self.aug_taken2 = []        # 2티어(보스 전용) 획득 기록
        self.aug_tier = 1           # 현재 열려 있는 증강 선택창의 티어
        self.aug_options = None
        self.boss_warning = False
        if "owned_aspects" not in self.__dict__:     # 로비로 돌아가도 형상·조각·파편·장착은 유지된다
            self.owned_aspects = {"n_base", "h_base", "c_base", "d_base"}
            self.aspect_shards = 0
            self.aspect_pity = 0
            self.pity_tier2_claimed = False
            self.equipped = {"N": "n_base", "H": "h_base", "C": "c_base", "D": "d_base"}
        self.pity_choice_open = False
        self.pity_choice_tier = 0
        self.gacha_banner = self.__dict__.get("gacha_banner", "normal")   # 형상해석 테마 (normal / web)
        self.formation_open = False
        self.gacha_open = False
        self.codex_open = False
        self.codex_page = "menu"
        self.codex_sel = None
        self.gacha_results = []     # [(pool항목, 신규여부), ...]
        self.inv_open = False
        self.__dict__.setdefault("inventory", {})   # 아이템 보유량 — 로비로 돌아가도 유지
        # mirror_hp 패치: 작은 거울 1개당 모든 아군 최대 체력 +50 (새 전투에서도 유지)
        _cb = 50 * self.inventory.get("worn_cloak", 0)      # 낡은 망토: 최대 격파체력 +50
        if _cb:
            for _u in self.allies():
                _u.max_brk += _cb
                _u.brk = _u.max_brk
        _mb = 50 * self.inventory.get("small_mirror", 0)
        if _mb:
            for _u in self.allies():
                _u.max_hp += _mb
                _u.hp = _u.max_hp
        self.gacha_notice = ""
        self.gacha_reveal = None
        self.lobby = bool(to_lobby)
        self.status_msg = "전투 개시..."
        self.log("전투가 시작되었다. N / H / C 대 적병 3기.", TXT)
        self.log("(E 키 → 형상해석 창)", MUT)
        self.log("(F 키 → 서재)", MUT)
        self.log("(TAB 키 → 인벤토리)", MUT)
        self.log("(전투 중 'maki' 입력 → 어드민 패널)", MUT)
        if to_lobby:
            self.status_msg = None
            self.render()
        else:
            self.begin_wave(600)

    def spawn_wave(self):
        for _a in self.allies():
            _a.ult_use_round = None      # 새 웨이브 — 환상 재사용 대기 초기화
            _a.fun_turns = 0
            _a.danger_turns = 0
        self.undying_used = False   # 불사의 가호 — 새 전투(웨이브)마다 1회 충전
        hero = self.units.get("H")
        if hero and hero.aspect_id == "h_hero":
            hero.hero_buff = False
            hero.shield = min(hero.shield, hero.max_hp)
            hero.hero_revive_used = False
            hero.hero_passive_shield_gained = 0
            hero.hero_echo_used = False
            hero.hero_echo_channel = None
        imperial = self.units.get("N")
        if imperial and imperial.aspect_id == "n_imperial":
            imperial.imperial_prayer = 0
            imperial.imperial_princess = False
            imperial.imperial_command_used = False
            imperial.imperial_hope_cooldown = 0
            imperial.imperial_guardian_round = None
            imperial.imperial_guardian_empty_reward_round = None
            imperial.imperial_safety_round = None
            imperial.imperial_safety_used = False
            imperial.imperial_guardian_target = None
            imperial.imperial_n = True
        for _a in self.allies():
            _a.ma_melody = False          # 선율은 그 전투 동안만
        _ma = self.units.get("H")
        if _ma and self.is_maestro(_ma):
            self.ma_reset(_ma)            # 전투 시작시 조망 21 · 생체재료 1
        _bn = self.units.get("N")
        if _bn and self.is_bigsis(_bn):
            self.bs_reset(_bn)            # 전투 시작시 포장 3 · 달아오르는 재미 2
        _ub = self.units.get("C")
        if _ub and self.is_underboss(_ub):
            self.ub_reset(_ub)            # 전투 시작시 예지 30 · 가속탄 10
        _or = self.units.get("H")
        if _or and self.is_oracle(_or):
            self.or_reset(_or)            # 전투 시작시 헤르메스 · 해금 I
        for _a in self.allies():
            if self.is_orch(_a):
                self.orch_reset(_a)           # 전투 시작시 관객 0 · 피날레 초기화
        # 이전 웨이브의 적 유닛을 모두 정리한다 (보스↔일반 전환 대응)
        for uid in [k for k, v in self.units.items() if v.side == "enemy"]:
            del self.units[uid]

        if is_boss_phase(self.phase):
            t = boss_template(self.phase)
            b = Unit("B1", t["name"], "PHASE %d — 심연의 주인" % self.phase, "enemy",
                     t["max_hp"], t["max_brk"],
                     normal_dmg=t["normal_dmg"], skill_dmg=t["skill_dmg"], skill_cost=2)
            b.is_boss = True
            b.aoe_dmg = t["aoe_dmg"]
            b.sp = 2
            self.units["B1"] = b
            self.enemy_ids = ["B1"]
            self.boss_mode = True
            return

        t = enemy_template(self.phase)
        self.enemy_ids = list(self.ENEMY_IDS)
        self.boss_mode = False
        for i, uid in enumerate(self.ENEMY_IDS):
            u = Unit(uid, "%s %d" % (t["tier"], i + 1), "PHASE %d 적 병력" % self.phase,
                     "enemy", t["max_hp"], t["max_brk"],
                     normal_dmg=t["normal_dmg"], skill_dmg=t["skill_dmg"], skill_cost=3)
            self.units[uid] = u

    def allies(self):
        return [self.units[i] for i in self.ALLY_IDS]

    def enemies(self):
        return [self.units[i] for i in self.enemy_ids if i in self.units]

    def is_fate_c(self, unit):
        return unit.side == "ally" and unit.aspect_id == "c_fate_lost"

    def can_pay_fate_hp(self, unit, amount):
        if amount <= 0:          # 체력 소비가 없는 스킬([운명] 등)은 체력과 무관하게 사용 가능
            return True
        return not self.is_fate_c(unit) or unit.hp - amount >= 10

    def pay_fate_hp(self, unit, amount):
        if not self.is_fate_c(unit) or amount <= 0:
            return True
        if not self.can_pay_fate_hp(unit, amount):
            return False
        unit.hp -= amount
        self.fx_number(unit.id, "-%d HP" % amount, CURSE, 18)
        if not unit.fate_ready:
            unit.fate_hp_spent += amount
            self.log("Fate Lost/C 체력 %d 소비 (%d/100)." %
                     (amount, unit.fate_hp_spent), CURSE)
            if unit.fate_hp_spent >= 100:
                unit.fate_hp_spent = 0
                unit.fate_ready = True
                self.fx_flash(unit.id, STAR_COLOR[3], "gray50")
                self.fx_number(unit.id, "필연", STAR_COLOR[3], 22, dy=-28)
                self.log("Fate Lost/C — 운명을 벗어났어도 필연속을 벗어나진 못한다.스킬 3->스킬 3-2로 변경",
                         STAR_COLOR[3])
                beep([(659, 70), (880, 80), (1318, 160)], self.sound)
        return True

    def gain_sp(self, unit, amount):
        if self.is_fate_c(unit) or self.is_imperial_n(unit):
            return 0
        before = unit.sp
        unit.sp = min(unit.max_sp, unit.sp + amount)
        return unit.sp - before

    def is_imperial_n(self, unit):
        return unit.side == "ally" and unit.aspect_id == "n_imperial"

    def skills_for(self, unit):
        if self.is_orch(unit):
            return self.orch_skills(unit)
        if self.is_oracle(unit):
            skills = list(unit.skills)
            if unit.or_furioso:                      # 헤르메스 9 — 스킬 3 → 3-2 Furioso-Replica
                skills[2] = OR_SKILL_FURIOSO
            return skills
        if self.is_bigsis(unit):
            return list(BIGSIS_LEVA_SKILLS) if unit.bs_leva else list(unit.skills)
        if self.is_maestro(unit):
            skills = list(unit.skills)
            if unit.ma_view <= 0 and not unit.ma_closing_used:   # 조망 0 — 스킬 3 → 3-2 폐장
                skills[2] = MA_SKILL_CLOSING
            return skills
        if self.is_underboss(unit):
            skills = list(unit.skills)
            if unit.ub_ammo < 2:                     # 가속탄 부족 — 스킬 2 → 2-2
                skills[1] = UB_SKILL_CERVO
            if unit.ub_overheat >= 0:                # 예지 0 — 스킬 3 → 3-2 처분
                if not unit.ub_disposal_used:      # ub_disposal_swap: 사용 후엔 다시 스킬 3
                    skills[2] = UB_SKILL_DISPOSAL
            return skills
        if self.is_fate_c(unit) and unit.fate_ready:
            skills = list(unit.skills)
            skills[2] = FATE_LOST_C_ULTIMATE
            return skills
        if self.is_hero_h(unit) and unit.hero_buff and not unit.hero_echo_used:
            skills = list(unit.skills)
            skills[2] = HERO_H_ECHO
            return skills
        if (self.is_imperial_n(unit) and unit.imperial_princess
                and not unit.imperial_command_used):
            skills = list(unit.skills)
            skills[2] = IMPERIAL_N_COMMAND
            return skills
        return unit.skills

    def gain_imperial_prayer(self, unit, amount):
        if not self.is_imperial_n(unit) or unit.imperial_princess or amount <= 0:
            return 0
        before = unit.imperial_prayer
        unit.imperial_prayer = min(120, unit.imperial_prayer + amount)
        gained = unit.imperial_prayer - before
        self.fx_number(unit.id, "기도 %d/120" % unit.imperial_prayer, HEAL, 16)
        if unit.imperial_prayer >= 120:
            unit.imperial_prayer = 0
            unit.imperial_princess = True
            unit.sp = unit.max_sp
            unit.imperial_safety_round = self.round
            self.fx_imperial_prayer(unit.id, strong=True)
            self.log("별의 이름으로 이르되, 왕녀로써 저들에게 영원한 안식을 주어라.",
                     STAR_COLOR[3])
            beep([(523, 80), (784, 90), (1046, 120), (1568, 220)], self.sound)
        else:
            self.fx_imperial_prayer(unit.id)
        return gained

    def imperial_servant_restore(self, unit):
        before = unit.sp
        unit.sp = min(unit.max_sp, unit.sp + 2)
        gained = unit.sp - before
        self.fx_number(unit.id, "SP +%d" % gained, SPC, 16)
        return gained

    def is_hero_h(self, unit):
        return unit.side == "ally" and unit.aspect_id == "h_hero"

    def can_use_skill(self, unit, skill):
        if skill["kind"] == "ub_disposal" and unit.ub_disposal_used:
            return False
        if self.is_orch(unit):
            if skill["kind"] == "orch_finale":
                if unit.orch_finale <= 0:
                    return False
            elif unit.orch_finale > 0:              # 피날레 — 피날레 스킬 외 사용 불가
                return False
            need = ORCH_REQ.get(skill["kind"])
            if need and unit.orch_aud < need:
                return False
        if unit.sp < skill["cost"]:
            return False
        if not self.can_pay_fate_hp(unit, skill.get("hp_cost", 0)):
            return False
        if self.is_imperial_n(unit):
            if not unit.imperial_princess:
                return False
            if skill["kind"] == "imperial_command" and unit.imperial_command_used:
                return False
            if skill["kind"] == "imperial_hope" and unit.imperial_hope_cooldown > 0:
                return False
        if skill["kind"] == "hero_echo":
            return self.is_hero_h(unit) and unit.hero_buff and not unit.hero_echo_used
        return True

    def gain_shield(self, unit, amount):
        if amount <= 0:
            return 0
        before = unit.shield
        if self.is_hero_h(unit) and unit.hero_buff:
            unit.shield += amount
        else:
            unit.shield = min(unit.max_hp, unit.shield + amount)
        return unit.shield - before

    def gain_hero_skill_shield(self, unit, damage):
        if not self.is_hero_h(unit) or not unit.hero_buff or damage <= 0:
            return 0
        gained = self.gain_shield(unit, round(damage * 0.1))
        if gained:
            self.fx_number(unit.id, "SHIELD +%d" % gained, SHLD, 16)
            self.log("영웅 버프: 스킬 피해의 10%%만큼 보호막 +%d." % gained, HEAL)
        return gained

    def pay_hero_shield(self, unit, amount):
        if amount <= 0:
            return True
        if unit.shield < amount:
            return False
        unit.shield -= amount
        self.fx_number(unit.id, "SHIELD -%d" % amount, SHLD, 16)
        return True

    def log(self, msg, color=MUT):
        self.log_lines.append((msg, color))
        if len(self.log_lines) > 200:
            self.log_lines = self.log_lines[-200:]

    # ---------------- 흐름 제어 ----------------
    def schedule(self, ms, fn):
        """어드민 개입(epoch 증가) 시 자동으로 무효화되는 지연 호출."""
        ep = self.epoch
        def run():
            if ep != self.epoch:
                return
            fn()
        self.root.after(ms, run)

    def cancel_flow(self):
        """진행 중이던 연출/예약 흐름을 끊는다."""
        self.overlay = None
        self.busy = False
        self.pending = None
        self.acting = None
        self.plan_queue = []
        self.resolve_order = []
        self.res_idx = 0
        self.boss_warning = False
        for e in list(self.effects):
            for it in e["items"]:
                try:
                    self.canvas.delete(it)
                except tk.TclError:
                    pass
        self.effects.clear()
        self.shakes.clear()

    def begin_wave(self, delay=600):
        """웨이브 시작. 보스 페이즈면 경고 배너를 먼저 띄운다."""
        self._action_epoch = self.epoch
        if self.boss_mode:
            self.banner("WARNING", "%s — 심연이 열린다" % self.units[self.enemy_ids[0]].name)
            self.status_msg = "보스 접근 중..."
            beep([(160, 200), (120, 200), (90, 320)], self.sound)
            self.render()
            self.schedule(1800, self._wave_go)
        else:
            self.render()
            self.schedule(delay, self._wave_go)

    def _wave_go(self):
        self.overlay = None
        self.start_round()

    # ================================================================
    # 라운드 흐름
    # ================================================================
    def start_round(self):
        if self.game_over:
            return
        for unit in self.units.values():
            unit.status = None
            unit.plan = None
            unit.plans = []
            unit.speed = 0
        targets = [enemy for enemy in self.enemies() if enemy.alive and enemy.fate_turns > 0]
        if not targets:
            self._start_round_after_fate()
            return

        source = self.units.get("C")

        def apply_next_fate_tick(index):
            if index >= len(targets):
                if not self.check_end():
                    self._start_round_after_fate()
                return
            target = targets[index]
            if not target.alive or target.fate_turns <= 0:
                apply_next_fate_tick(index + 1)
                return

            def after_tick(dealt):
                target.fate_turns = max(0, target.fate_turns - 1)
                self.log("운명 피해: %s에게 5 피해 · 남은 운명 %d." %
                         (target.name, target.fate_turns), STAR_COLOR[3])
                if target.fate_turns == 0:
                    self.log("%s에게 걸린 운명이 사라졌다." % target.name, MUT)
                apply_next_fate_tick(index + 1)

            self.apply_damage(source, target, 5, "fate", after_tick)

        apply_next_fate_tick(0)

    def _start_round_after_fate(self):
        if self.game_over:
            return
        self.state = "roll"
        if self.bs_burn_tick():
            return
        self.pending = None
        self.acting = None
        self.boss_warning = False
        self.log("── 라운드 %d ──  SP 회복 · 속도 판정" % self.round, TXT)

        for u in self.units.values():
            u.status = None
            u.plan = None
            u.plans = []
            u.speed = 0

        for u in self.units.values():
            if not u.alive:
                u.focused = None
                continue
            if self.is_orch(u):
                self.orch_round_start(u)
                if not u.alive:
                    continue
            if self.is_oracle(u):
                self.or_round_start(u)
            if self.is_maestro(u):
                self.ma_round_start(u)       # 턴 시작시 조망 -2
            if self.is_underboss(u):
                self.ub_round_start(u)
            if self.is_imperial_n(u):
                if u.imperial_hope_cooldown > 0:
                    u.imperial_hope_cooldown -= 1
                if u.imperial_safety_round != self.round:
                    u.imperial_safety_round = None
                if u.imperial_princess:
                    healed = min(10, u.max_hp - u.hp)
                    u.hp += healed
                    if healed:
                        self.fx_heal(u.id, "+%d" % healed)
                        self.log("왕녀의 권능으로 체력 %d 회복." % healed, HEAL)
            if u.fun_turns > 0:
                healed = min(10, u.max_hp - u.hp)
                u.hp += healed
                u.fun_turns -= 1
                if healed:
                    self.fx_heal(u.id, "+%d" % healed)
                self.log("%s의 재미난 장난: 체력 +%d (남은 %d)." % (u.name, healed, u.fun_turns), HEAL)
                if u.fun_turns == 0:
                    self.log("%s의 재미난 장난이 사라졌다." % u.name, MUT)
            if u.curse_turns > 0:
                u.curse_turns -= 1
                if u.curse_turns == 0:
                    self.log("%s에게 걸린 저주가 풀렸다." % u.name, CURSE)
            if u.immortal_turns > 0:
                u.immortal_turns -= 1
                if u.immortal_turns == 0:
                    self.log("%s의 불사 상태가 풀렸다." % u.name, HEAL)
            if u.broken:
                if self.is_hero_h(u) and u.hero_echo_channel:
                    u.hero_echo_channel = None
                    self.log("%s의 [잔상보]가 격파로 중단됐다." % u.name, BRKC)
                if u.focused:
                    u.focused = None
                    self.log("%s의 집중이 격파로 끊겼다." % u.name, BRKC)
                if u.broken_skips > 0:
                    u.broken_skips -= 1
                    self.log("%s은(는) 격파 상태 — 이번 라운드 행동 불가." % u.name, BRKC)
                    continue
                u.broken = False
                u.brk = u.max_brk
                self.log("%s의 격파 상태가 해제됐다. 격파체력 최대치 회복." % u.name, BRKC)
            if self.is_imperial_n(u) and u.imperial_princess:
                before_sp = u.sp
                u.sp = min(u.max_sp, u.sp + 4)
                if u.sp > before_sp:
                    self.fx_number(u.id, "SP +%d" % (u.sp - before_sp), SPC, 16)
                    self.log("왕녀의 권능으로 SP +%d." % (u.sp - before_sp), STAR_COLOR[3])
            else:
                self.gain_sp(u, 1)
            if u.side == "enemy":
                max_speed = max(1, 6 - u.speed_penalty)
                rib_active = u.rib_turns > 0
                if rib_active:                           # 간이늑골 — 속도 주사위 최대값 절반 감소
                    max_speed = max(1, max_speed - max_speed // 2)
                u.speed = random.randint(1, max_speed)
                if rib_active:
                    u.rib_turns -= 1
                    self.log("%s의 간이늑골 — 속도 주사위 1~%d (남은 %d턴)." %
                             (u.name, max_speed, u.rib_turns), MA_BONE)
                if u.speed_penalty:
                    self.log("%s의 속도 저하 효과가 적용됐다. (주사위 1~%d)" % (u.name, max_speed), CURSE)
                    u.speed_penalty = 0
                if u.speed_minus > 0:
                    before_speed = u.speed
                    u.speed = max(1, u.speed - u.speed_minus)
                    self.log("%s의 속도가 -%d 감소했다. (%d→%d)" %
                             (u.name, u.speed_minus, before_speed, u.speed), PAINT_BLUE)
                    u.speed_minus = 0
                if u.speed_fix:
                    u.speed = 1
                    u.speed_fix = False
                    self.log("%s의 속도가 1로 고정됐다." % u.name, CURSE)
            else:
                u.speed = random.randint(min(6, self.aug_speed_min + self.or_speed_bonus(u)), 6)
                if u.ma_melody:                          # 선율 — 속도 +1 (최대 6)
                    u.speed = min(6, u.speed + 1)

        actors = [u for u in self.units.values() if u.alive and not u.broken]
        if not actors:
            self.schedule(500, self.end_round)
            return
        self.status_msg = "속도 판정 중..."
        self.render()
        self.roll_dice_overlay(actors, self.begin_planning)

    def begin_planning(self):
        if self.game_over:
            return
        self.state = "plan"
        order = sorted([u for u in self.units.values() if u.alive and not u.broken],
                       key=lambda u: (-u.speed, u.side == "enemy", u.id))
        self.resolve_order = order
        self.log("행동 순서: " + " → ".join(
            "%s(%d)%s" % (u.name, u.speed, "×%d" % BOSS_ACTIONS if u.is_boss else "")
            for u in order), MUT)

        for e in self.enemies():
            if e.alive and not e.broken:
                self.enemy_decide(e)

        self.plan_queue = [u for u in self.allies() if u.alive and not u.broken]
        self.next_ally_plan()

    def next_ally_plan(self):
        self.pending = None
        for _oa in self.allies():
            _oa.orch_amt = 1
        if not self.plan_queue:
            self.acting = None
            self.state = "resolve"
            self.status_msg = "전원 행동 지정 완료 — 속도 순으로 해결."
            self.render()
            self.schedule(500, self.begin_resolution)
            return
        self.acting = self.plan_queue.pop(0)
        if self.acting.focused:
            focused = self.acting.focused
            self.acting.focused = None
            self.acting.plan = dict(type="focus_release", target=focused["target"],
                                    skill=focused["skill"])
            self.log("%s의 [%s] 발동! 지정한 대상을 향해 집중 공격." %
                     (self.acting.name, focused["skill"]["name"]), SPC)
            self.next_ally_plan()
            return
        self.status_msg = None
        self.render()

    # ---------------- 적 AI ----------------
    def enemy_decide(self, e):
        alive_allies = [u for u in self.allies() if u.alive]
        if not alive_allies:
            return
        if e.is_boss:
            self.boss_plan_turn(e)
            return
        w_atk, w_skill, w_gd, w_ev = 50, (22 if e.sp >= e.skill_cost else 0), 14, 14
        hp_r = e.hp / e.max_hp
        brk_r = 1 if e.broken else e.brk / e.max_brk
        if hp_r <= 0.35:
            w_ev += 26
            w_gd += 14
            w_atk -= 22
        if brk_r <= 0.3 and not e.broken:
            w_gd += 26
            w_atk -= 12
        if e.sp >= MAX_SP - 1:
            w_skill += 18
        w_atk = max(5, w_atk)

        opts = [("normal", w_atk), ("guard", w_gd), ("evade", w_ev)]
        if w_skill > 0:
            opts.append(("skill", w_skill))
        total = sum(w for _, w in opts)
        r = random.random() * total
        choice = "normal"
        for name, w in opts:
            if r < w:
                choice = name
                break
            r -= w

        target = random.choice(alive_allies)
        if choice == "guard":
            self.apply_guard(e)
            e.plan = dict(type="guard")
        elif choice == "evade":
            self.apply_evade(e)
            e.plan = dict(type="evade")
        elif choice == "skill":
            e.sp -= e.skill_cost
            e.plan = dict(type="eskill", target=target.id)
        else:
            e.sp = min(MAX_SP, e.sp + 1)
            e.plan = dict(type="normal", target=target.id)

    def boss_plan_turn(self, e):
        """코즈믹:혼돈의 이번 라운드 행동을 계획한다.

        SP가 가득 차면 광역기 [차원 붕괴] 단 하나만 행동하고(다른 공격과 함께 하지 않음),
        그렇지 않으면 BOSS_ACTIONS 회에 걸쳐 기본 공격/강타/방어 중에서 고른다.
        """
        alive_allies = [u for u in self.allies() if u.alive]
        if not alive_allies:
            e.plans = []
            e.plan = None
            return

        if e.sp >= BOSS_AOE_COST:
            e.sp -= BOSS_AOE_COST
            self.boss_warning = True
            self.log("⚠ 혼돈이 느껴진다 —— %s이(가) [차원 붕괴]를 준비한다! (아군 전원 %d 피해)"
                     % (e.name, e.aoe_dmg), COSMIC)
            beep([(90, 180), (70, 220)], self.sound)
            e.plans = [dict(type="eaoe")]
        else:
            e.plans = []
            for _ in range(BOSS_ACTIONS):
                alive_allies = [u for u in self.allies() if u.alive]
                if not alive_allies:
                    break
                e.plans.append(self.boss_decide(e, alive_allies))

        e.plan = e.plans[0] if e.plans else None

    def boss_decide(self, e, alive_allies):
        """광역기를 준비 중이 아닐 때 행동 하나를 결정해 반환한다."""
        opts = [("normal", 46)]
        if e.sp >= 2:
            opts.append(("skill", 34))
        if not e.broken and e.brk / e.max_brk <= 0.4:
            opts.append(("guard", 20))

        total = sum(w for _, w in opts)
        r = random.random() * total
        choice = "normal"
        for name, w in opts:
            if r < w:
                choice = name
                break
            r -= w

        if choice == "guard":
            self.apply_guard(e)
            return dict(type="guard")
        if choice == "skill":
            e.sp -= 2
            return dict(type="eskill", target=random.choice(alive_allies).id)
        e.sp = min(MAX_SP, e.sp + 1)
        return dict(type="normal", target=random.choice(alive_allies).id)

    # ---------------- 플레이어 입력 ----------------
    def choose_normal(self):
        if self.state != "plan" or self.busy or not self.acting:
            return
        unit = self.acting
        if self.is_imperial_n(unit) and not unit.imperial_princess:
            unit.plan = dict(type="imperial_servant")
            unit.imperial_guardian_round = self.round
            gained = self.imperial_servant_restore(unit)
            allies = [ally for ally in self.allies() if ally.alive and ally is not unit]
            if allies:
                recipient = random.choice(allies)
                unit.imperial_guardian_target = recipient
                self.log("%s의 [수호령] 명에 따라 왕녀를 지켜라 (%s). SP +%d" %
                         (unit.name, recipient.name, gained), STAR_COLOR[3])
                self.fx_imperial_guardian(unit.id, recipient.id)
                self.gain_imperial_prayer(unit, 20)   # 수호령 사용 즉시 기도 +20
                self.log("[수호령] 사용 즉시 기도 +20.", HEAL)
            else:
                self.log("%s의 [수호령]! 전이할 아군이 없다. SP +%d" %
                         (unit.name, gained), STAR_COLOR[3])
                self.gain_imperial_prayer(unit, 20)
                unit.imperial_guardian_empty_reward_round = self.round
            self.next_ally_plan()
            return
        self.pending = dict(type="normal", side="enemy")
        self.status_msg = "공격할 적을 선택하세요."
        self.render()

    def choose_skill(self, idx):
        if self.state != "plan" or self.busy or not self.acting:
            return
        sk = self.skills_for(self.acting)[idx]
        if not self.can_use_skill(self.acting, sk):
            return
        if self.is_orch(self.acting):
            if sk["kind"] != "orch_s3":
                self.acting.orch_amt = 1
            if sk["kind"] == "orch_s3":                  # 포르티시모 — 버튼 연타로 소모 SP 증가
                self.orch_mash(idx)
                return
            if sk["kind"] in ("orch_s3b", "orch_finale"):   # 대상을 지정하지 않는 스킬
                self.acting.sp -= sk["cost"]
                self.acting.plan = dict(type="skill", idx=idx, skill=sk, target=None)
                self.log("%s: [%s] 발동 지정%s" % (
                    self.acting.name, sk["name"], (" (SP -%d)" % sk["cost"]) if sk["cost"] else ""),
                    ORCH_GOLD)
                self.next_ally_plan()
                return
        if sk["kind"] == "fate_ultimate":
            self.acting.plan = dict(type="skill", idx=idx, skill=sk, target=None)
            self.acting.fate_ready = False
            self.log("%s: [운명] 발동 지정 — 필연을 소비했다." % self.acting.name,
                     STAR_COLOR[3])
            self.next_ally_plan()
            return
        if sk["kind"] == "imperial_command":
            self.acting.plan = dict(type="skill", idx=idx, skill=sk, target=None)
            self.acting.imperial_command_used = True
            self.acting.sp -= sk["cost"]
            self.log("%s: [(관측불가) 섬멸 명령] 지정 (SP -%d)" %
                     (self.acting.name, sk["cost"]), STAR_COLOR[3])
            self.next_ally_plan()
            return
        if sk["kind"] == "ma_closing":                 # 대상을 지정하지 않는 스킬
            self.acting.plan = dict(type="skill", idx=idx, skill=sk, target=None)
            self.log("%s: [폐장] 발동 지정" % self.acting.name, MA_BONE)
            self.next_ally_plan()
            return
        target_side = sk.get("target", "ally" if sk["kind"] == "heal" else "enemy")
        if target_side == "self":
            if not self.pay_fate_hp(self.acting, sk.get("hp_cost", 0)):
                return
            self.acting.sp -= sk["cost"]
            self.ult_charge(self.acting, sk["cost"])
            self.acting.plan = dict(type="skill", idx=idx, skill=sk,
                                    target=self.acting.id)
            self.log("%s: [%s] 발동 지정 (SP -%d)" %
                     (self.acting.name, sk["name"], sk["cost"]), MUT)
            self.next_ally_plan()
            return
        self.pending = dict(type="skill", idx=idx, skill=sk, side=target_side)
        if target_side == "ally":
            self.status_msg = "회복할 아군을 선택하세요."
        elif target_side == "any":
            self.status_msg = "대상으로 지정할 아군 또는 적을 선택하세요."
        elif sk["kind"] == "curse":
            self.status_msg = "저주를 걸 적을 선택하세요."
        elif sk["kind"] == "speed_debuff":
            self.status_msg = "속도를 낮출 적을 선택하세요."
        else:
            self.status_msg = "대상을 선택하세요."
        self.render()

    def choose_guard(self):
        if self.state != "plan" or self.busy or not self.acting:
            return
        self.apply_guard(self.acting)
        self.acting.plan = dict(type="guard")
        self.fx_stance(self.acting.id, HEAL)
        self.next_ally_plan()

    def choose_evade(self):
        if self.state != "plan" or self.busy or not self.acting:
            return
        self.apply_evade(self.acting)
        self.acting.plan = dict(type="evade")
        self.fx_stance(self.acting.id, SPC)
        self.next_ally_plan()

    def cancel_pending(self):
        self.pending = None
        if self.acting:
            self.acting.orch_amt = 1
        self.status_msg = None
        self.render()

    def apply_guard(self, u):
        if self.is_bigsis(u):                      # 봉인된 검 — 방어 행동이 반격으로 변경
            u.status = "counter"
            gained = self.gain_sp(u, 2)
            self.log("%s이(가) 반격 태세. 즉시 발동 · SP +%d" % (u.name, gained), BS_FIRE)
            return
        u.status = "guard"
        gained = self.gain_sp(u, 2)
        self.log("%s이(가) 방어 태세. 즉시 발동 · SP +%d" % (u.name, gained), HEAL)

    def apply_evade(self, u):
        u.status = "evade"
        gained = self.gain_sp(u, 2)
        self.log("%s이(가) 회피 태세. 즉시 발동 · SP +%d" % (u.name, gained), SPC)

    def on_card_click(self, uid):
        if self.admin_kill_pending:
            target = self.units.get(uid)
            if not target or target.side != "ally" or not target.alive:
                self.status_msg = "처치할 살아 있는 아군을 선택하세요."
                self.render()
                return
            self.admin_kill_pending = False
            self.status_msg = None
            self.admin_kill_ally(target)
            return
        # 증강 '전술 재정비' 대상 지정
        if self.state == "augment_target":
            self.apply_sp_full_target(uid)
            return
        if not self.pending or self.busy:
            return
        t = self.units[uid]
        if self.pending["side"] != "any" and t.side != self.pending["side"]:
            return
        u = self.acting
        if self.pending["type"] == "skill":
            sk = self.pending["skill"]
            if not t.alive:
                return
            if not self.pay_fate_hp(u, sk.get("hp_cost", 0)):
                return
            u.sp -= sk["cost"]
            self.ult_charge(u, sk["cost"])
            u.orch_amt = 1
            if sk["kind"] == "hero_echo" and self.is_hero_h(u):
                u.hero_echo_used = True
            if sk["kind"] == "or_furioso" and self.is_oracle(u):
                u.or_furioso = False                  # 3-2 는 1회용 — 헤르메스 9 로 다시 열린다
                u.or_block_round = self.round         # 이 턴은 지령 수행 · 헤르메스 획득 없음
                self.log("%s: [Furioso-Replica] — 이 턴은 지령을 수행하지 않는다." % u.name, OR_GOLD)
            u.plan = dict(type="skill", idx=self.pending["idx"], skill=sk, target=uid)
            self.log("%s: [%s] 지정 (SP -%d)" % (u.name, sk["name"], sk["cost"]), MUT)
        elif self.pending["type"] == "ultimate":
            ult = self.pending["ult"]
            if not t.alive:
                return
            ok, _why = self.ult_ready(u)
            if not ok:
                return
            u.ult_gauge -= ult["cost"]
            u.ult_use_round = self.round
            u.plan = dict(type="ultimate", target=uid, ult=ult)
            self.log("%s: 환상 [%s] 지정 (환상도 -%d%% · 남은 %d%%)" %
                     (u.name, ult["name"], ult["cost"], u.ult_gauge), ult["color"])
        else:
            if not t.alive:
                return
            gained = self.gain_sp(u, 1)
            u.plan = dict(type="normal", target=uid)
            self.log("%s: 기본 공격 지정 (SP +%d)" % (u.name, gained), MUT)
        self.next_ally_plan()

    # ================================================================
    # 해결 단계
    # ================================================================
    def begin_resolution(self):
        if self.game_over:
            return
        self.state = "resolve"
        self.acting = None
        self.pending = None
        self.res_idx = 0
        self.resolve_next()

    def resolve_next(self):
        if self.game_over:
            return
        if self.res_idx >= len(self.resolve_order):
            self.end_round()
            return
        u = self.resolve_order[self.res_idx]
        self.res_idx += 1
        if self.is_hero_h(u) and u.hero_echo_channel and not u.alive:
            u.hero_echo_channel = None
        if not u.alive or not u.plan:
            self.resolve_next()
            return
        if u.broken and u.broken_skips > 0:
            if self.is_hero_h(u):
                u.hero_echo_channel = None
            u.broken_skips -= 1
            self.log("%s은 격파되어 행동이 무너졌다!" % u.name, BRKC)
            self.status_msg = "%s 행동 불가 (격파)" % u.name
            self.render()
            self.schedule(700, self.resolve_next)
            return
        if u.stun_turns > 0:
            if self.is_hero_h(u):
                u.hero_echo_channel = None
            u.stun_turns -= 1
            self.log("%s은 [카즈나]의 여파로 행동할 수 없다." % u.name, CURSE)
            self.status_msg = "%s 행동 불가 (카즈나)" % u.name
            self.render()
            self.schedule(700, self.resolve_next)
            return

        self.acting = u
        self.status_msg = "SPD %d — %s의 행동" % (u.speed, u.name)
        self.busy = True
        self._action_epoch = self.epoch
        self.render()
        self.execute(u, self.after_action)

    def after_action(self):
        self.busy = False
        self.acting = None
        if self.check_end():
            return
        self.render()
        self.schedule(260, self.resolve_next)

    def valid_target(self, u, plan, need):
        t = self.units.get(plan.get("target"))
        if t and t.alive:
            return t
        pool = self.enemies() if u.side == "ally" else self.allies()
        cands = [x for x in pool if x.alive]
        return random.choice(cands) if cands else None

    def execute(self, u, done):
        # 보스 — 한 라운드에 여러 번 행동한다 (광역기 라운드는 1회만)
        if u.is_boss and u.plans:
            seq = list(u.plans)

            def step(i):
                if i >= len(seq) or not u.alive or not any(a.alive for a in self.allies()):
                    done()
                    return
                u.plan = seq[i]
                self.status_msg = "SPD %d — %s의 행동 (%d/%d)" % (
                    u.speed, u.name, i + 1, len(seq))
                self.render()
                self.execute_one(u, lambda: self.schedule(340, lambda: step(i + 1)))

            step(0)
            return
        self.execute_one(u, done)

    def execute_one(self, u, done):
        plan = u.plan
        ptype = plan["type"]
        if u.side == "ally" and ptype not in ("guard", "evade", "imperial_servant"):
            for _m in self.allies():                   # 아군의 수비 외 행동 — 조망 -1
                if _m.alive and self.is_maestro(_m):
                    self.ma_view_drop(_m, 1)

        if ptype == "guard" and self.is_bigsis(u) and u.alive:
            self.bs_counter_upkeep(u, done)
            return

        if ptype in ("guard", "evade"):
            self.log("%s은 %s 태세를 유지한다." % (u.name, "방어" if ptype == "guard" else "회피"),
                     HEAL if ptype == "guard" else SPC)
            self.schedule(320, done)
            return

        if ptype == "imperial_servant":
            self.schedule(280, done)
            return

        if ptype == "ultimate":
            self.execute_ultimate(u, plan, done)
            return

        if ptype == "normal":
            t = self.valid_target(u, plan, "enemy")
            if not t:
                self.log("%s의 공격은 목표를 잃었다." % u.name, MUT)
                self.schedule(300, done)
                return
            dmg = u.normal_dmg if u.side == "enemy" else (10 + self.aug_atk_bonus)
            self.fx_hit(t.id)
            self.apply_damage(u, t, dmg, "hit",
                              lambda d: (self.log("%s의 기본 공격! %s에게 %d 피해." % (u.name, t.name, d), DMG),
                                         done()))
            return

        if ptype == "eaoe":
            targets = [a for a in self.allies() if a.alive]
            if not targets:
                self.schedule(300, done)
                return
            self.boss_warning = False
            self.log("%s이(가) 공간을 뒤튼다 — [차원 붕괴]! (아군 전원 %d 피해)"
                     % (u.name, u.aoe_dmg), COSMIC)
            self.fx_cosmic()
            beep([(120, 150), (90, 130), (60, 220)], self.sound)

            def step(i):
                if i >= len(targets):
                    self.schedule(280, done)
                    return
                t = targets[i]
                self.fx_heavy(t.id)
                self.apply_damage(u, t, u.aoe_dmg, "heavy",
                                  lambda d, t=t: (self.log("   └ %s에게 %d 피해." % (t.name, d), DMG),
                                                  step(i + 1)))

            self.schedule(560, lambda: step(0))
            return

        if ptype == "focus_release":
            t = plan["target"]
            sk = plan["skill"]
            if not t.alive or t.side != "enemy" or t not in self.enemies():
                self.log("%s의 [%s]은 대상이 사라져 빗나갔다." % (u.name, sk["name"]), MUT)
                self.schedule(300, done)
                return
            self.fx_slash(t.id, 3, color=SPC)
            self.schedule(260, lambda: self.apply_damage(
                u, t, sk["dmg"], "heavy",
                lambda dealt: (self.log("%s의 [%s]! %s에게 %d 피해." %
                                        (u.name, sk["name"], t.name, dealt), DMG), done())))
            return

        if ptype == "eskill":
            t = self.valid_target(u, plan, "ally")
            if not t:
                self.schedule(300, done)
                return
            self.fx_heavy(t.id)
            self.apply_damage(u, t, u.skill_dmg, "heavy",
                              lambda d: (self.log("%s의 [강타]! %s에게 %d 피해." % (u.name, t.name, d), DMG),
                                         done()))
            return

        # 아군 스킬
        sk = plan["skill"] if "skill" in plan else u.skills[plan["idx"]]
        if sk["kind"].startswith("ub_"):
            self.execute_underboss(u, sk, plan, done)
            return
        if sk["kind"].startswith("ma_"):
            self.execute_maestro(u, sk, plan, done)
            return
        if sk["kind"].startswith("or_"):
            self.execute_oracle(u, sk, plan, done)
            return
        if sk["kind"].startswith("bs_"):
            self.execute_bigsis(u, sk, plan, done)
            return
        if sk["kind"].startswith("dream_"):
            self.execute_dreamer(u, sk, plan, done)
            return
        if sk["kind"].startswith("orch_"):
            self.execute_orchestra(u, sk, plan, done)
            return
        if sk["kind"].startswith(("painter_", "cook_", "dist_")):
            self.execute_new_aspect(u, sk, plan, done)
            return

        if sk["kind"] == "imperial_star":
            target = self.valid_target(u, plan, "enemy")
            if not target or target.side != "enemy":
                self.schedule(300, done)
                return

            def after_star(dealt):
                self.log("%s의 [별책]! %s에게 %d 피해." %
                         (u.name, target.name, dealt), STAR_COLOR[3])
                done()

            self.fx_imperial_star(target.id)
            self.schedule(220, lambda: self.apply_damage(
                u, target, sk["dmg"], "heavy", after_star))
            return

        if sk["kind"] == "imperial_devotion":
            target = self.valid_target(u, plan, "ally")
            if not target or target.side != "ally":
                self.schedule(300, done)
                return
            hp_gained = min(sk["hp"], target.max_hp - target.hp)
            target.hp += hp_gained
            if target.broken:
                brk_gained = 0
            else:
                brk_gained = min(sk["brk"], target.max_brk - target.brk)
                target.brk += brk_gained
            self.fx_heal(target.id, "HEAL +%d" % hp_gained)
            self.log("[%s] %s의 체력 +%d, 격파체력 +%d." %
                     (sk["name"], target.name, hp_gained, brk_gained), HEAL)
            self.schedule(450, done)
            return

        if sk["kind"] == "imperial_hope":
            target = self.units.get(plan.get("target"))
            if not target or not target.alive:
                self.log("[희망] 대상이 사라져 불발됐다.", MUT)
                self.schedule(300, done)
                return
            u.imperial_hope_cooldown = sk["cooldown"] + 1
            if target.side == "ally":
                shield_gained = self.gain_shield(target, 40)
                hp_gained = min(30, u.max_hp - u.hp)
                u.hp += hp_gained
                self.fx_imperial_hope(target.id, self.center_of(u.id))
                self.fx_number(target.id, "SHIELD +%d" % shield_gained, SHLD, 17)
                self.fx_heal(u.id, "+%d" % hp_gained)
                self.log("[희망] %s에게 보호막 %d, N의 체력 +%d." %
                         (target.name, shield_gained, hp_gained), HEAL)
                self.schedule(600, done)
                return

            def after_hope(dealt):
                brk_dealt = 0
                if target.alive and not target.broken:
                    before = target.brk
                    target.brk = max(0, target.brk - 50)
                    brk_dealt = before - target.brk
                    if target.brk == 0:
                        target.broken = True
                        target.broken_skips = 1
                        self.fx_break(target.id)
                self.log("[희망] %s에게 고정피해 %d, 격파피해 %d." %
                         (target.name, dealt, brk_dealt), STAR_COLOR[3])
                done()

            self.fx_imperial_hope(target.id)
            self.apply_damage(u, target, 50, "imperial_fixed", after_hope, fixed=True)
            return

        if sk["kind"] == "imperial_command":
            targets = [enemy for enemy in self.enemies() if enemy.alive]
            if not targets:
                self.schedule(300, done)
                return

            def bombard(index):
                if index >= len(targets):
                    done()
                    return
                target = targets[index]
                self.apply_damage(u, target, sk["dmg"], "imperial_command",
                                  lambda dealt, target=target, index=index:
                                  (self.log("[섬멸 명령] %s에게 %d 피해." %
                                            (target.name, dealt), STAR_COLOR[3]),
                                   bombard(index + 1)),
                                  skip_defense=True, no_break=True)

            self.log("왕녀의 뜻대로, 모든걸 섬멸하라.",
                     STAR_COLOR[3])
            self.fx_imperial_barrage(targets)
            self.schedule(1500, lambda: bombard(0))
            return

        if sk["kind"] == "hero_attack":
            t = self.valid_target(u, plan, "enemy")
            if not t or t.side != "enemy":
                self.schedule(300, done)
                return

            def after_hero_slash(dealt):
                self.gain_hero_skill_shield(u, dealt)
                self.log("%s의 [횡베기]! %s에게 %d 피해." % (u.name, t.name, dealt), DMG)
                done()

            self.fx_slash(t.id, 1, color=STAR_COLOR[3])
            self.schedule(160, lambda: self.apply_damage(u, t, sk["dmg"], "heavy", after_hero_slash))
            return

        if sk["kind"] == "hero_memory":
            t = self.valid_target(u, plan, "enemy")
            if not t or t.side != "enemy":
                self.schedule(300, done)
                return
            enhanced = u.shield >= sk["shield_cost"]
            if enhanced:
                self.pay_hero_shield(u, sk["shield_cost"])
                shield_gained = self.gain_shield(u, sk["shield_gain"])
                self.fx_number(u.id, "SHIELD +%d" % shield_gained, SHLD, 16)
            self.fx_slash(t.id, 1, color=STAR_COLOR[3])

            def after_memory(dealt):
                self.gain_hero_skill_shield(u, dealt)
                if not enhanced:
                    self.log("%s의 머리속 기억들이 스친다 %s에게 %d 피해." %
                             (u.name, t.name, dealt), DMG)
                    done()
                    return

                def after_bonus(extra_dealt):
                    self.gain_hero_skill_shield(u, extra_dealt)
                    self.log("%s의 기억들이 더욱 스쳐 칼날이 되었다! %s에게 %d + 추가 %d 피해." %
                             (u.name, t.name, dealt, extra_dealt), DMG)
                    done()

                self.fx_slash(t.id, 1, color=SPC)
                self.schedule(140, lambda: self.apply_damage(
                    u, t, sk["bonus_dmg"], "heavy", after_bonus))

            self.schedule(160, lambda: self.apply_damage(u, t, sk["dmg"], "heavy", after_memory))
            return

        if sk["kind"] == "hero_afterimage":
            t = self.valid_target(u, plan, "enemy")
            if not t or t.side != "enemy":
                self.schedule(300, done)
                return
            enhanced = u.shield >= sk["shield_cost"]
            if enhanced:
                self.pay_hero_shield(u, sk["shield_cost"])
            self.fx_hero_impact(t.id)

            def after_first_image(dealt):
                self.gain_hero_skill_shield(u, dealt)
                if not enhanced:
                    self.log("%s의 잔상이 적을 엄습한다! %s에게 %d 피해." % (u.name, t.name, dealt), DMG)
                    done()
                    return
                living_enemies = [enemy for enemy in self.enemies() if enemy.alive]
                if not living_enemies:
                    self.log("%s의 잔상은 나아간다 %s에게 %d 피해. 재사용할 적이 없다." %
                             (u.name, t.name, dealt), DMG)
                    done()
                    return
                extra = random.choice(living_enemies)
                self.fx_hero_impact(extra.id)

                def after_second_image(extra_dealt):
                    self.gain_hero_skill_shield(u, extra_dealt)
                    self.log("%s의 잔상은 더욱 나아간다! %s에게 %d, %s에게 %d 피해." %
                             (u.name, t.name, dealt, extra.name, extra_dealt), DMG)
                    done()

                self.apply_damage(u, extra, sk["dmg"], "heavy", after_second_image)

            self.schedule(180, lambda: self.apply_damage(u, t, sk["dmg"], "heavy", after_first_image))
            return

        if sk["kind"] == "hero_echo":
            t = self.valid_target(u, plan, "enemy")
            if not t or t.side != "enemy":
                self.schedule(300, done)
                return
            u.hero_echo_channel = {"target": t.id, "remaining": sk["repeats"]}
            self.log("%s의 모든 시간과 기억이 검이 되어 돌아온다.." %
                     (u.name, t.name), STAR_COLOR[3])
            self.execute_hero_echo_repeat(u, t, done, 0, sk["repeats"] + 1)
            return

        if sk["kind"] == "fate_attack":
            t = self.valid_target(u, plan, "enemy")
            if not t:
                self.schedule(300, done)
                return

            def after_main(dealt):
                self.apply_damage(u, t, sk["fixed_dmg"], "fixed", lambda fixed: (
                    self.log("[%s] 방어 무시 고정피해 %d." % (sk["name"], fixed), STAR_COLOR[3]),
                    done()), fixed=True)

            self.fx_fate_upslash(t.id)
            self.schedule(153, lambda: self.apply_damage(u, t, sk["dmg"], "heavy", after_main))
            return

        if sk["kind"] == "fate_splash":
            t = self.valid_target(u, plan, "enemy")
            enemies = self.enemies()
            if not t or t not in enemies:
                self.schedule(300, done)
                return
            index = enemies.index(t)
            hits = [(t, sk["dmg"])]
            for neighbor_index in (index - 1, index + 1):
                if 0 <= neighbor_index < len(enemies) and enemies[neighbor_index].alive:
                    hits.append((enemies[neighbor_index], sk["splash"]))
            self.resolve_fate_hits(u, sk, hits, done)
            return

        if sk["kind"] == "fate_stun":
            t = self.valid_target(u, plan, "enemy")
            if not t or t.side != "enemy":
                self.log("[카즈나] 대상이 유효한 적이 아니어서 발동이 취소됐다.", MUT)
                self.schedule(300, done)
                return

            def after_kazuna(dealt):
                if t.side == "enemy" and t.alive:
                    t.stun_turns = max(t.stun_turns, sk["stun_turns"])
                    self.fx_curse(t.id)
                    self.log("[%s] %s에게 운명 속박 — 다음 행동 불가." %
                             (sk["name"], t.name), STAR_COLOR[3])
                done()

            self.fx_fate_explosion(t.id)
            self.schedule(220, lambda: self.apply_damage(u, t, sk["dmg"], "heavy", after_kazuna))
            return

        if sk["kind"] == "fate_ultimate":
            targets = [enemy for enemy in self.enemies() if enemy.alive]
            if not targets:
                done()
                return

            def hit_enemy(index):
                if index >= len(targets):
                    done()
                    return
                target = targets[index]

                def after_fate_hit(dealt):
                    if target.alive:
                        target.fate_turns = max(target.fate_turns, sk["fate_turns"])
                        self.fx_curse(target.id)
                        self.log("%s에게 운명 %d 부여." %
                                 (target.name, target.fate_turns), STAR_COLOR[3])
                    hit_enemy(index + 1)

                self.fx_fate_explosion(target.id)
                self.apply_damage(u, target, sk["dmg"], "heavy", after_fate_hit)

            self.log("%s의 운명이 흐름을 잡고,모든 적들은 자신의 운명을 마주한다!" % u.name, STAR_COLOR[3])
            self.fx_fate_memories(u.id, [target.id for target in targets])
            self.schedule(1900, lambda: hit_enemy(0))
            return

        if sk["kind"] == "attack":
            t = self.valid_target(u, plan, "enemy")
            if not t:
                self.log("%s의 [%s]은 목표를 잃었다." % (u.name, sk["name"]), MUT)
                self.schedule(300, done)
                return

            def hit():
                def after_hit(dealt):
                    extra_brk = sk.get("extra_brk", 0)
                    if extra_brk and t.alive and t.side == "enemy" and not t.broken:
                        t.brk = max(0, t.brk - extra_brk)
                        self.log("[%s] 추가 격파피해 %d." % (sk["name"], extra_brk), BRKC)
                        if t.brk == 0:
                            t.broken = True
                            t.broken_skips = 1
                            self.log("💥 %s의 격파체력이 소진됐다 — 격파!" % t.name, BRKC)
                            self.fx_break(t.id)
                    self.log("%s의 [%s]! %s에게 %d 피해." % (u.name, sk["name"], t.name, dealt), DMG)
                    self.render()
                    done()

                fx_kind = sk.get("fx", "slash")
                self.apply_damage(u, t, sk["dmg"],
                                  "heavy" if fx_kind in ("snipe", "frenzy") else fx_kind,
                                  after_hit)

            fx = sk.get("fx", "slash")
            accent = sk.get("accent", DMG)
            if fx == "snipe":
                self.log("%s이 조준경을 든다 — %s 사격!" % (u.name, t.name), accent)
                self.fx_snipe(t.id, hit, color=accent)
            elif fx == "frenzy":
                self.log("%s의 걸착!" % u.name, accent)
                self.fx_frenzy(t.id, hit, color=accent)
            elif fx == "slash2":
                self.fx_slash(t.id, 2, color=accent)
                self.schedule(220, hit)
            elif fx == "slash":
                self.fx_slash(t.id, 1, color=accent)
                self.schedule(160, hit)
            else:
                if fx in ("slash", "slash2"):
                    self.fx_slash(t.id, 2 if fx == "slash2" else 1, color=accent)
                else:
                    self.fx_bullet(t.id)
                self.schedule(140, hit)
            return

        if sk["kind"] == "attack_splash":
            t = self.valid_target(u, plan, "enemy")
            if not t:
                self.schedule(300, done)
                return
            hits = [(t, sk["dmg"])]
            hits.extend((enemy, sk["splash"]) for enemy in self.enemies()
                        if enemy is not t and enemy.alive)

            guarded_hits = [(target, amount) for target, amount in hits
                            if target.status in ("guard", "evade")]
            direct_hits = [(target, amount) for target, amount in hits
                           if target.status not in ("guard", "evade")]
            remaining = [len(hits)]

            def hit_done(target, dealt):
                self.log("[%s] %s에게 %d 피해." % (sk["name"], target.name, dealt), DMG)
                remaining[0] -= 1
                if remaining[0] == 0:
                    done()

            def resolve_guarded(index):
                if index >= len(guarded_hits):
                    return
                target, amount = guarded_hits[index]
                self.apply_damage(u, target, amount, "heavy",
                                  lambda dealt, target=target, index=index:
                                  (hit_done(target, dealt), resolve_guarded(index + 1)))

            def begin_simultaneous_hits():
                for target, amount in direct_hits:
                    self.apply_damage(u, target, amount, "heavy",
                                      lambda dealt, target=target: hit_done(target, dealt))
                resolve_guarded(0)

            for target, _ in hits:
                self.fx_slash(target.id, 1, color=ROSE)
            self.schedule(160, begin_simultaneous_hits)
            return

        if sk["kind"] == "focus":
            t = self.valid_target(u, plan, "enemy")
            if not t:
                self.schedule(300, done)
                return
            u.focused = dict(target=t, skill=sk)
            self.fx_stance(u.id, SPC)
            self.fx_number(u.id, "집중", SPC, 17)
            self.log("%s이(가) [%s]에 집중한다. 다음 라운드에 %s를 공격한다." %
                     (u.name, sk["name"], t.name), SPC)
            self.render()
            self.schedule(500, done)
            return

        if sk["kind"] in ("shield_self", "shield_ally"):
            t = u if sk["kind"] == "shield_self" else self.valid_target(u, plan, "ally")
            if not t:
                self.schedule(300, done)
                return
            gained = self.gain_shield(t, sk["amt"])
            if sk["kind"] == "shield_self":
                self.fx_flag(t.id, SHLD)
            else:
                self.fx_stance(t.id, SHLD)
            self.fx_number(t.id, "SHIELD +%d" % gained, SHLD, 17)
            self.log("%s의 [%s]! %s에게 보호막 %d 생성 (%d 보유)." %
                     (u.name, sk["name"], t.name, gained, t.shield), SHLD)
            self.render()
            self.schedule(500, done)
            return

        if sk["kind"] == "speed_debuff":
            t = self.valid_target(u, plan, "enemy")
            if not t:
                self.schedule(300, done)
                return
            t.speed_penalty = max(t.speed_penalty, sk["amt"])
            self.fx_curse(t.id)
            self.log("%s의 [%s]! %s의 다음 속도 주사위 최대값이 %d 감소한다." %
                     (u.name, sk["name"], t.name, t.speed_penalty), CURSE)
            self.render()
            self.schedule(500, done)
            return

        if sk["kind"] == "sp_gain":
            t = self.valid_target(u, plan, "ally")
            if not t:
                self.schedule(300, done)
                return
            gained = self.gain_sp(t, sk["amt"])
            self.fx_number(t.id, "SP +%d" % gained, SPC, 17)
            self.log("%s의 [%s]! %s의 SP가 %d 회복됐다 (%d/%d)." %
                     (u.name, sk["name"], t.name, gained, t.sp, MAX_SP), SPC)
            self.render()
            self.schedule(500, done)
            return

        if sk["kind"] == "curse":
            t = self.valid_target(u, plan, "enemy")
            if not t:
                self.log("%s의 [%s]은 목표를 잃었다." % (u.name, sk["name"]), MUT)
                self.schedule(300, done)
                return
            t.curse_turns = max(t.curse_turns, sk.get("curse_turns", 3))
            self.fx_curse(t.id)
            beep([(200, 90), (140, 110), (90, 160)], self.sound)
            self.log("%s의 [%s]! %s에게 예언을 내린다 (3턴간 받는 피해 1.5배, 격파 상태와 중첩)"
                     % (u.name, sk["name"], t.name), CURSE)
            self.render()
            self.schedule(700, done)
            return

        # heal
        t = self.valid_target(u, plan, "ally")
        if not t:
            self.schedule(300, done)
            return
        gained = []
        hp_restore = sk.get("hp", 0)
        brk_restore = sk.get("brk", 0)
        if hp_restore:
            before = t.hp
            t.hp = min(t.max_hp, t.hp + hp_restore)
            gained.append("체력 +%d" % (t.hp - before))
        if brk_restore:
            if t.broken:
                gained.append("격파 상태라 격파체력 회복 무효")
            else:
                before = t.brk
                t.brk = min(t.max_brk, t.brk + brk_restore)
                gained.append("격파체력 +%d" % (t.brk - before))
        self.fx_heal(t.id, "+%d" % (hp_restore or brk_restore))
        beep([(660, 60), (880, 90)], self.sound)
        self.log("%s의 [%s]! %s — %s" % (u.name, sk["name"], t.name, ", ".join(gained)), HEAL)
        self.render()
        self.schedule(700, done)

    # ---------------- 신규 ★★ 형상: 화가 N / 요리사 H / 분배자 C ----------------
    # ================================================================
    # D / 드리머 — 꿈가루 이펙트 (연노랑 / 연보라)
    # ================================================================
    def execute_dreamer(self, u, sk, plan, done):
        t = self.valid_target(u, plan, "enemy")
        if not t or t.side != "enemy":
            self.log("%s의 [%s]은 목표를 잃었다." % (u.name, sk["name"]), MUT)
            self.schedule(300, done)
            return
        kind = sk["kind"]
        sides = []
        if kind == "dream_eternal":                      # 양 옆 대상
            en = self.enemies()
            if t in en:
                i = en.index(t)
                sides = [en[j] for j in (i - 1, i + 1) if 0 <= j < len(en) and en[j].alive]

        def after_main(dealt):
            self.log("%s의 [%s]! %s에게 %d 피해." % (u.name, sk["name"], t.name, dealt), DREAM_PUR)
            if not sides:
                done()
                return
            self.fx_dream_sides([s.id for s in sides])

            def step(i):
                if i >= len(sides):
                    done()
                    return
                s = sides[i]
                if not s.alive:
                    step(i + 1)
                    return
                self.apply_damage(u, s, sk["splash"], "heavy",
                                  lambda d, s=s, i=i: (
                                      self.log("   └ [%s] %s에게 %d 피해." % (sk["name"], s.name, d),
                                               DREAM_PUR),
                                      step(i + 1)))

            self.schedule(300, lambda: step(0))

        if kind == "dream_push":
            ms = self.fx_dream_push(u.id, t.id)
        elif kind == "dream_star":
            ms = self.fx_dream_star(u.id, t.id)
        else:
            ms = self.fx_dream_eternal(t.id)
        self.schedule(ms, lambda: self.apply_damage(u, t, sk["dmg"], "heavy", after_main))

    def fx_dream_dust(self, uid, n=14, spread=110, dur=0.85):
        """꿈가루 — 연노랑/연보라/흰 알갱이가 퍼지며 떠오르다 사라진다."""
        cv = self.canvas
        cx, cy = self.center_of(uid)
        items, data = [], []
        for _ in range(n):
            col = random.choice((DREAM_YEL, DREAM_PUR, DREAM_WHITE))
            it = cv.create_oval(cx, cy, cx, cy, fill=col, outline="", tags="fx")
            a = random.random() * math.tau
            d = random.uniform(0.3, 1.0) * spread
            items.append(it)
            data.append((it, cx + math.cos(a) * d, cy + math.sin(a) * d * 0.7,
                         random.uniform(2, 4.5), random.uniform(20, 60), col))

        def up(p, e):
            q = 1 - (1 - p) ** 3
            for it, px, py, r, rise, col in data:
                x = cx + (px - cx) * q
                y = cy + (py - cy) * q - rise * p
                rr = r * (1 - 0.5 * p)
                cv.coords(it, x - rr, y - rr, x + rr, y + rr)
                cv.itemconfig(it, fill=lerp_color(col, BG, p * p))

        self.add_fx(items, dur, up)

    def _dream_burst(self, uid, big=False):
        cx, cy = self.center_of(uid)
        self.fx_flash(uid, DREAM_YEL, "gray50")
        self.fx_dream_dust(uid, n=26 if big else 14, spread=150 if big else 105)
        self._bsx_ring(cx, cy, DREAM_PUR, 12, 140 if big else 90, 0.45, 4)
        self._bsx_ring(cx, cy, DREAM_YEL, 8, 100 if big else 60, 0.35, 3)
        self._ub_sparkle(cx, cy, n=7 if big else 4, spread=90, size=(7, 14), dur=0.6,
                         cols=(DREAM_YEL, DREAM_PUR, DREAM_WHITE))
        self.shakes[uid] = 0.4 if big else 0.22
        beep([(880, 30), (1175, 40)], self.sound)

    def fx_dream_push(self, src, tgt):
        """밀치기 — 부드러운 꿈빛 파동이 밀어낸다."""
        sx, sy = self.center_of(src)
        tx, ty = self.center_of(tgt)
        self._ub_stroke([(sx, sy), ((sx + tx) / 2, (sy + ty) / 2 - 24), (tx, ty)],
                        DREAM_YEL, DREAM_PUR, 0.3, 1.3)
        self.root.after(160, lambda: self._dream_burst(tgt, False))
        return 220

    def fx_dream_star(self, src, tgt):
        """별점 사격 — 별이 포물선으로 날아가 꿈가루를 흩뿌리며 터진다."""
        cv = self.canvas
        sx, sy = self.center_of(src)
        tx, ty = self.center_of(tgt)
        star = cv.create_polygon(*([sx, sy] * 10), fill=DREAM_YEL, outline=DREAM_WHITE,
                                 width=2, tags="fx")
        trail = cv.create_line(sx, sy, sx, sy, fill=DREAM_PUR, width=6, capstyle="round", tags="fx")
        dur = 0.5

        def pos(q):
            return (sx + (tx - sx) * q, sy + (ty - sy) * q - math.sin(q * math.pi) * 60)

        def up(p, e):
            q = min(1.0, p / 0.8)
            q = q * q * (3 - 2 * q)
            x, y = pos(q)
            r = 18 * (1 - max(0.0, (p - 0.85) / 0.15))
            pts = []
            for k in range(10):
                a = -math.pi / 2 + math.pi * k / 5 + p * 7
                rr = r if k % 2 == 0 else r * 0.42
                pts += [x + math.cos(a) * rr, y + math.sin(a) * rr]
            cv.coords(star, *pts)
            x0, y0 = pos(max(0.0, q - 0.28))
            cv.coords(trail, x0, y0, x, y)
            cv.itemconfig(trail, fill=lerp_color(DREAM_PUR, BG, max(0.0, (p - 0.7) / 0.3)))

        self.add_fx([star, trail], dur, up)
        self.root.after(int(dur * 800), lambda: self._dream_burst(tgt, True))
        return int(dur * 880)

    def fx_dream_eternal(self, tgt):
        """이터널 드림 — 꿈의 장막이 내리고 초승달 궤적이 감싸며 만개한다."""
        cx, cy = self.center_of(tgt)
        ra = math.radians
        self._bsx_veil(DREAM_PUR_D, 0.7, "gray12")
        self._ub_crescent(cx, cy, 160, 96, ra(200), ra(250), -0.35, DREAM_YEL, DREAM_PUR, 0.5, 1.7)
        self.root.after(130, lambda: self._ub_crescent(
            cx, cy, 120, 72, ra(20), ra(240), 0.3, DREAM_PUR, DREAM_WHITE, 0.45, 1.3))
        self.root.after(300, lambda: self._bsx_sunburst(
            cx, cy, (DREAM_YEL, DREAM_PUR, DREAM_WHITE), 16, 26, 170, 0.55))
        self.root.after(420, lambda: self._dream_burst(tgt, True))
        return 560

    def fx_dream_sides(self, ids):
        for k, uid in enumerate(ids):
            self.root.after(60 + k * 90, lambda uid=uid: self._dream_burst(uid, False))

    def is_painter(self, unit):
        return unit.side == "ally" and unit.aspect_id == "n_painter"

    def execute_new_aspect(self, u, sk, plan, done):
        kind = sk["kind"]
        if kind.startswith("painter_"):
            self.execute_painter(u, sk, plan, done)
        elif kind.startswith("cook_"):
            self.execute_cook(u, sk, plan, done)
        else:
            self.execute_distributor(u, sk, plan, done)

    def execute_painter(self, u, sk, plan, done):
        kind = sk["kind"]
        t = self.valid_target(u, plan, "enemy")
        if not t or t.side != "enemy":
            self.schedule(300, done)
            return

        if kind == "painter_overcoat":
            bonus = 5 * (t.paint // 3)
            dmg = min(sk["max_dmg"], sk["dmg"] + bonus)
            if bonus > 0:
                t.paint -= 2
                self.fx_number(t.id, "물감 -2", PAINT_RED, 15, dy=-32)
            self.fx_brush(t.id, PAINT_RED, strokes=2 if bonus else 1)

            def after(dealt):
                self.log("%s의 [덧칠]! %s에게 %d 피해%s." %
                         (u.name, t.name, dealt, " (물감 효과 +%d)" % bonus if bonus else ""), DMG)
                done()

            self.schedule(300, lambda: self.apply_damage(u, t, dmg, "heavy", after))
            return

        if kind == "painter_brush":
            reuse = t.paint >= 3
            if reuse:
                t.paint -= 2
                self.fx_number(t.id, "물감 -2", PAINT_RED, 15, dy=-32)
            self.fx_brush(t.id, PAINT_BLUE, strokes=1)

            def after_first(dealt):
                self.log("%s의 [붓 털기]! %s에게 %d 피해." % (u.name, t.name, dealt), DMG)
                pool = [e for e in self.enemies() if e.alive]
                if not reuse or not pool:
                    done()
                    return
                extra = random.choice(pool)
                self.fx_paint_splash(extra.id, PAINT_RED, src=t.id, small=True)

                def after_second(d2):
                    self.log("[붓 털기] 물감이 튀어 %s에게 재사용! %d 피해." % (extra.name, d2), DMG)
                    done()

                self.schedule(520, lambda: self.apply_damage(u, extra, sk["dmg"], "heavy", after_second))

            self.schedule(300, lambda: self.apply_damage(u, t, sk["dmg"], "heavy", after_first))
            return

        # 트리플 아틀리에
        all_three = t.paint >= 5
        if all_three:
            t.paint = 0
            self.log("물감이 가득 찼다 — 트리플 아틀리에의 세 가지 색이 전부 터진다!", PAINT_RED)
            self.fx_paint_burst3(t.id)
            effects = ["blue", "red", "green"]
        else:
            effects = [random.choice(["blue", "red", "green"])]

        fx_started = set()

        def run(i):
            if i >= len(effects):
                done()
                return
            if not t.alive:
                self.log("[트리플 아틀리에] 대상이 쓰러져 남은 색이 흩어졌다.", MUT)
                done()
                return
            eff = effects[i]
            if i not in fx_started:
                fx_started.add(i)
                fx_col = {"blue": PAINT_BLUE, "red": PAINT_RED, "green": PAINT_GREEN}[eff]
                if all_three:           # 강화 — 이미 3색이 터졌으니 짧게 튀기고 바로 판정
                    self.fx_paint_splash(t.id, fx_col, src=None, small=True)
                else:                   # 팔레트에서 물감을 던져 퍼지게 뿌린 뒤 판정
                    self.fx_paint_splash(t.id, fx_col, src=u.id)
                    self.schedule(470, lambda: run(i))
                    return

            def nxt(*_):
                self.schedule(180, lambda: run(i + 1))

            if eff == "blue":
                self.shakes[t.id] = 0.25

                def after_blue(dealt):
                    if t.alive:
                        t.speed_minus = max(t.speed_minus, 1)
                        self.fx_number(t.id, "속도 -1", PAINT_BLUE, 16)
                    self.log("[블루] %s에게 %d 피해 · 다음턴 속도 -1." % (t.name, dealt), PAINT_BLUE)
                    nxt()

                self.schedule(160, lambda: self.apply_damage(u, t, 45, "heavy", after_blue))
            elif eff == "red":
                self.shakes[t.id] = 0.25

                def after_red(dealt):
                    self.log("[레드] %s에게 %d 피해." % (t.name, dealt), PAINT_RED)
                    nxt()

                self.schedule(160, lambda: self.apply_damage(u, t, 55, "heavy", after_red))
            else:
                self.shakes[t.id] = 0.25
                self.fx_flash(t.id, PAINT_GREEN, "gray50")
                amount = 30
                if self.aug_brk_bonus:
                    amount = round(amount * (1 + self.aug_brk_bonus))
                if t.broken:
                    self.log("[그린] %s는 이미 격파 상태다." % t.name, PAINT_GREEN)
                else:
                    t.brk = max(0, t.brk - amount)
                    self.log("[그린] %s에게 격파피해 %d." % (t.name, amount), PAINT_GREEN)
                    if t.brk == 0:
                        t.broken = True
                        t.broken_skips = 1
                        self.log("💥 %s의 격파체력이 소진됐다 — 격파!" % t.name, BRKC)
                        self.fx_break(t.id)
                self.render()
                self.schedule(420, nxt)

        self.log("%s의 [트리플 아틀리에]! 캔버스에 색이 번진다." % u.name, PAINT_RED)
        self.schedule(950 if all_three else 200, lambda: run(0))

    def execute_cook(self, u, sk, plan, done):
        t = self.valid_target(u, plan, "enemy")
        if not t or t.side != "enemy":
            self.schedule(300, done)
            return
        self.fx_slash(t.id, 1, color=SPC)

        def after(dealt):
            stunned = False
            if dealt > 0 and t.alive and random.random() < sk["stun_chance"]:
                t.stun_turns = max(t.stun_turns, 1)
                stunned = True
                self.fx_number(t.id, "기절!", SPC, 22, dy=-30)
                self.fx_particles(t.id, SPC, n=14, spread=80, dur=0.5, size=4)
            self.log("%s의 [%s]! %s에게 %d 피해%s." %
                     (u.name, sk["name"], t.name, dealt, " · 기절!" if stunned else ""), DMG)
            done()

        self.schedule(160, lambda: self.apply_damage(u, t, sk["dmg"], "heavy", after))

    def dist_hit(self, u, t, dmg, ignore_shield, cb):
        """분배자 — 대상이 적이면 일반 피해, 아군이면 격파피해 없음 · 체력 1 미만 불가."""
        sk = (u.plan or {}).get("skill") or {}
        self.fx_hourglass(t.id, big=(sk.get("kind") == "dist_game"))
        if t.side == "ally":
            self.schedule(640, lambda: self.apply_damage(
                u, t, dmg, "heavy", cb, fixed=ignore_shield, skip_defense=True,
                no_break=True, hp_floor=1))
        else:
            self.schedule(640, lambda: self.apply_damage(u, t, dmg, "heavy", cb))

    def give_fun(self, t, turns):
        if t.alive and turns > 0:
            t.fun_turns = max(t.fun_turns, turns)
            self.fx_number(t.id, "재미난 장난 %d" % t.fun_turns, HEAL, 15, dy=-32)

    def give_danger(self, t, turns):
        if t.alive and turns > 0:
            t.danger_turns = max(t.danger_turns, turns)
            self.fx_number(t.id, "위험한 장난 %d" % t.danger_turns, CURSE, 15, dy=-12)

    def execute_distributor(self, u, sk, plan, done):
        t = self.units.get(plan.get("target"))
        if not t or not t.alive:
            self.log("[%s] 대상이 사라져 불발됐다." % sk["name"], MUT)
            self.schedule(300, done)
            return
        ally = t.side == "ally"
        kind = sk["kind"]

        if kind == "dist_share":
            dmg = sk["ally_dmg"] if ally else sk["enemy_dmg"]

            def after(dealt):
                if ally:
                    others = [a for a in self.allies() if a.alive and a is not t]
                    names = []
                    for a in others:
                        gained = min(sk["heal"], a.max_hp - a.hp)
                        a.hp += gained
                        self.fx_heal(a.id, "+%d" % gained)
                        names.append("%s +%d" % (a.name, gained))
                    self.log("[%s] %s에게 %d 피해 → 나머지 아군 회복 (%s)." %
                             (sk["name"], t.name, dealt, ", ".join(names) or "없음"), CURSE)
                else:
                    self.log("[%s] %s에게 %d 피해." % (sk["name"], t.name, dealt), CURSE)
                self.schedule(350 if ally else 50, done)

            self.dist_hit(u, t, dmg, True, after)
            return

        if kind == "dist_fun":
            dmg = sk["ally_dmg"] if ally else sk["enemy_dmg"]
            fun = sk["ally_fun"] if ally else sk["enemy_fun"]

            def after(dealt):
                self.give_fun(t, fun)
                self.log("[%s] %s에게 %d 피해 · 재미난 장난 %d 부여." %
                         (sk["name"], t.name, dealt, fun), CURSE)
                self.schedule(350, done)

            self.dist_hit(u, t, dmg, False, after)
            return

        # dist_game
        dmg = sk["ally_dmg"] if ally else sk["enemy_dmg"]

        def after(dealt):
            if ally:
                self.give_fun(t, sk["ally_fun"])
                self.give_danger(t, sk["ally_danger"])
                self.log("[%s] %s에게 %d 피해 · 재미난 장난 %d, 위험한 장난 %d 부여." %
                         (sk["name"], t.name, dealt, sk["ally_fun"], sk["ally_danger"]), CURSE)
            else:
                if t.alive:
                    t.speed_fix = True
                    self.fx_number(t.id, "속도 1 고정", CURSE, 15, dy=-32)
                self.log("[%s] %s에게 %d 피해 · 다음턴 속도 1로 고정." %
                         (sk["name"], t.name, dealt), CURSE)
            self.schedule(350, done)

        self.dist_hit(u, t, dmg, False, after)

    def execute_hero_echo_repeat(self, unit, first_target, done, hit_index, total_hits):
        channel = unit.hero_echo_channel
        targets = [enemy for enemy in self.enemies() if enemy.alive]
        if not channel or not targets:
            unit.hero_echo_channel = None
            done()
            return
        if not unit.alive or unit.broken or unit.stun_turns > 0:
            unit.hero_echo_channel = None
            self.log("%s의 [잔상보]가 행동 불가 상태로 중단됐다." % unit.name, BRKC)
            done()
            return
        if hit_index == 0 and first_target.alive and first_target.side == "enemy":
            target = first_target
        else:
            target = random.choice(targets)
            if hit_index == 0:
                self.log("잔상보의 지정 대상이 사라져 %s에게 첫 타격을 전환했다." %
                         target.name, STAR_COLOR[3])
        channel["target"] = target.id
        channel["remaining"] = total_hits - hit_index - 1
        self.fx_hero_dash(unit.id, target.id)

        def after_repeat(dealt):
            self.gain_hero_skill_shield(unit, dealt)
            self.log("[잔상보 %d/%d] %s에게 %d 피해." %
                     (hit_index + 1, total_hits, target.name, dealt), STAR_COLOR[3])
            if hit_index + 1 >= total_hits:
                unit.hero_echo_channel = None
                self.log("%s의 [잔상보]가 끝났다." % unit.name, MUT)
                done()
                return
            self.schedule(90, lambda: self.execute_hero_echo_repeat(
                unit, first_target, done, hit_index + 1, total_hits))

        self.schedule(90, lambda: self.apply_damage(
            unit, target, HERO_H_ECHO["dmg"], "heavy", after_repeat))

    def resolve_fate_hits(self, attacker, skill, hits, done):
        guarded = [(target, amount) for target, amount in hits
                   if target.status in ("guard", "evade")]
        direct = [(target, amount) for target, amount in hits
                  if target.status not in ("guard", "evade")]
        remaining = [len(hits)]

        def hit_done(target, dealt):
            self.log("[%s] %s에게 %d 피해." % (skill["name"], target.name, dealt), DMG)
            remaining[0] -= 1
            if remaining[0] == 0:
                done()

        def guarded_next(index):
            if index >= len(guarded):
                return
            target, amount = guarded[index]
            self.apply_damage(attacker, target, amount, "heavy",
                              lambda dealt, target=target, index=index:
                              (hit_done(target, dealt), guarded_next(index + 1)))

        def begin_hits():
            for target, amount in direct:
                self.apply_damage(attacker, target, amount, "heavy",
                                  lambda dealt, target=target: hit_done(target, dealt))
            guarded_next(0)

        self.fx_fate_sweep(hits[0][0].id, [target.id for target, _ in hits])
        self.schedule(267, begin_hits)

    # ---------------- 피해 처리 ----------------
    def apply_damage(self, attacker, target, raw, fx, cb, fixed=False,
                     skip_defense=False, no_break=False, hp_floor=None, transfer=False):
        if self._action_epoch != self.epoch:   # 어드민 개입으로 무효화된 행동
            return
        # 위험한 장난 — 공격력 +15 (전이 피해에는 중복 적용하지 않는다)
        if (not fixed and not transfer and attacker is not None and attacker.danger_turns > 0
                and raw > 0 and fx not in ("fate", "admin")):
            raw += 15
        if (not fixed and not transfer and attacker is not None and attacker.side == "ally"
                and target.side == "enemy" and raw > 0 and fx not in ("fate", "admin")
                and self.__dict__.get("inventory", {}).get("torn_umbrella", 0) > 0):
            raw += 5            # 헤진 우산 — 공격력 +5
        if (not fixed and not transfer and attacker is not None and attacker.side == "ally"
                and target.side == "enemy" and raw > 0 and fx not in ("fate", "admin")):
            if self.is_bigsis(attacker) and attacker.bs_leva:
                raw += 5        # 레바테인 — 공격력 +5
            if attacker.ma_masterpiece:
                raw += 5        # 걸작 — 공격력 +5
            if self.is_oracle(attacker):
                raw += self.or_atk_bonus(attacker)   # 해금 III 이상 — 공격력 +5
            if attacker.ma_melody:
                raw += 5        # 선율 — 공격력 +5
        if (not fixed and not skip_defense and raw > 0 and self.is_underboss(target)
                and target.status not in ("guard", "evade") and target.ub_overheat < 0):     # 불완전한 예지안 — 공격당하면 자동 회피
            self.ub_passive_evade(attacker, target, raw, fx, cb, no_break, hp_floor)
            return
        if not fixed and not skip_defense and target.status == "counter":   # 반격 — 받는 피해 40% 감소
            reduced = max(1, round(raw * 0.6)) if raw > 0 else 0
            if raw > 0:
                self.log("%s 반격 태세! 받는 피해 40%% 감소 (%d→%d)" % (target.name, raw, reduced), BS_FIRE)
            self.finalize(attacker, target, reduced, fx,
                          lambda d: self.bs_counter_hit(target, attacker, cb, d),
                          no_break=no_break, hp_floor=hp_floor)
            return

        if not fixed and not skip_defense and target.status == "guard":
            roll = d6()
            target.status = None

            def after():
                red = 0.8 if roll == 6 else roll * 0.1
                dmg = max(1, round(raw * (1 - red)))
                self.log("%s 방어! 주사위 %d → 피해 %d%% 감소 (%d→%d)" %
                         (target.name, roll, round(red * 100), raw, dmg), BRKC)
                self.finalize(attacker, target, dmg, fx, cb, no_break=no_break, hp_floor=hp_floor)

            self.dice_judge_overlay([("방어 판정", roll)], after)
            return

        if not fixed and not skip_defense and target.status == "evade":
            a, b = d6(), d6()
            target.status = None

            def after():
                dodged = a >= b                      # 동점이어도 회피 성공 (6 은 어떤 값과 겨뤄도 성공)
                if dodged and self.is_oracle(target):
                    self.or_mission(target, "공격 회피")
                self.log("%s 회피 판정 %d vs %d → %s" %
                         (target.name, a, b, "완전 회피!" if dodged else "회피 실패"), BRKC)
                self.finalize(attacker, target, 0 if dodged else raw, "dodge" if dodged else fx, cb,
                              no_break=no_break, hp_floor=hp_floor)

            self.dice_judge_overlay([("회피측", a), ("공격측", b)], after)
            return

        self.finalize(attacker, target, raw, fx, cb, fixed=fixed, no_break=no_break,
                      hp_floor=hp_floor)

    def finalize(self, attacker, target, dmg, fx, cb, fixed=False, no_break=False, hp_floor=None):
        if self._action_epoch != self.epoch:
            return
        if (dmg > 0 and self.is_imperial_n(target)
                and target.imperial_guardian_round == self.round):
            candidates = [ally for ally in self.allies() if ally.alive and ally is not target]
            if candidates:
                recipient = (target.imperial_guardian_target
                             if target.imperial_guardian_target in candidates
                             else random.choice(candidates))
                transferred = max(1, round(dmg * 0.5))
                self.log("수호령이 %s에게 피해 %d를 전이한다 (절반 적용)." %
                         (recipient.name, transferred), STAR_COLOR[3])

                def after_transfer(dealt):
                    prayer = self.gain_imperial_prayer(target, dealt)
                    self.log("%s가 전이 피해 %d만큼 기도를 얻었다." %
                             (target.name, prayer), HEAL)
                    cb(dealt)

                self.apply_damage(attacker, recipient, transferred, fx,
                                  after_transfer, fixed=fixed, no_break=no_break,
                                  hp_floor=hp_floor, transfer=True)
                return
            if target.imperial_guardian_empty_reward_round != self.round:
                target.imperial_guardian_empty_reward_round = self.round
                self.gain_imperial_prayer(target, 20)
                self.log("기도가 공허하게 울려퍼졌다..", HEAL)
        blocked_to_zero = False
        imperial_safety = (self.is_imperial_n(target)
                   and target.imperial_safety_round == self.round)
        if dmg > 0 and not fixed:
            mult = 1.0
            tags = []
            if target.broken:
                mult *= 1.5
                tags.append("격파")
            if target.curse_turns > 0:
                mult *= 1.5
                tags.append("저주")
            if target.bloom_turns > 0:
                mult *= ULT_BLOOM_MULT
                tags.append("개화")
            if mult > 1.0:
                before = dmg
                dmg = round(dmg * mult)
                self.log("%s은 %s 효과로 받는 피해 증가! (%d→%d)" %
                         (target.name, "+".join(tags), before, dmg), CURSE if "저주" in tags else BRKC)
                self.fx_heavy(target.id)

            if target.side == "ally" and self.aug_dmg_reduction > 0:
                before_r = dmg
                dmg = max(0, dmg - self.aug_dmg_reduction)
                if dmg == 0:
                    blocked_to_zero = True
                elif dmg != before_r:
                    self.log("%s의 철벽 방어로 피해 %d → %d." % (target.name, before_r, dmg), SPC)

            if target.shield > 0 and dmg > 0:
                absorbed = min(target.shield, dmg)
                target.shield -= absorbed
                dmg -= absorbed
                blocked_to_zero = blocked_to_zero or dmg == 0
                self.log("%s의 보호막이 피해 %d 흡수 (잔여 보호막 %d)." %
                         (target.name, absorbed, target.shield), SHLD)

        if hp_floor is not None and target.side == "ally" and dmg > 0:
            cap = max(0, target.hp - hp_floor)      # 분배자 — 아군은 체력 1 미만으로 내려가지 않는다
            if dmg > cap:
                dmg = cap
                if dmg == 0:
                    blocked_to_zero = True
        was_alive = target.alive
        hp_before = target.hp
        undying_proc = False
        if dmg > 0 and target.side == "ally":
            projected = target.hp - dmg
            if imperial_safety:
                target.hp = max(1, projected)
                if projected <= 1:
                    target.imperial_safety_used = True
            elif self.is_orch(target) and target.orch_finale > 0:
                target.hp = max(1, projected)                 # 피날레 — 전투불능 되지 않는다
            elif (self.is_orch(target) and projected <= 0 and target.alive
                  and target.orch_aud >= ORCH_AUD_MAX):
                target.hp = 1                                 # 관객 20 — 피날레 진입
                self.orch_enter_finale(target)
            elif target.immortal_turns > 0:
                target.hp = max(1, projected)
            elif self.aug_undying and not self.undying_used and projected <= 0:
                target.hp = 1
                target.immortal_turns = 2
                self.undying_used = True
                undying_proc = True
            else:
                target.hp = max(0, projected)
        else:
            target.hp = max(0, target.hp - dmg)

        hp_damage = max(0, hp_before - target.hp)
        if (attacker is not None and target.side == "enemy" and hp_damage > 0
                and self.is_oracle(attacker)):
            self.or_on_damage(attacker, hp_damage)
        # 화가 N — 공격으로 피해를 입히면 물감 +1 (최대 5)
        if (dmg > 0 and attacker is not None and self.is_painter(attacker)
                and target.side == "enemy" and target.alive and fx != "admin"
                and target.paint < 5):
            target.paint += 1
            self.fx_number(target.id, "물감 %d" % target.paint, PAINT_RED, 15, dy=-32)
        hero_revived = False
        revive_shield_gained = 0
        revived_broken = target.broken
        if (was_alive and target.hp == 0 and self.is_hero_h(target)
                and not target.hero_revive_used):
            target.hp = target.max_hp
            target.broken = False
            target.broken_skips = 0
            target.brk = target.max_brk
            target.hero_revive_used = True
            target.hero_buff = True
            target.hero_echo_channel = None
            revive_shield_gained = self.gain_shield(target, 100)
            hero_revived = True
            self.fx_revive(target.id)
            self.fx_flash(target.id, STAR_COLOR[3], "gray50")
            self.fx_number(target.id, "SHIELD +%d" % revive_shield_gained, SHLD, 18)
            beep([(392, 80), (659, 100), (1046, 180)], self.sound)

        hero_damage_shield = 0
        if self.is_hero_h(target) and target.alive and hp_damage > 0:
            remaining_passive = max(0, 50 - target.hero_passive_shield_gained)
            passive_amount = min(remaining_passive, round(hp_damage * 0.1))
            hero_damage_shield = self.gain_shield(target, passive_amount)
            target.hero_passive_shield_gained += hero_damage_shield

        if undying_proc:
            self.log("✨ %s, 불사의 가호로 목숨을 건졌다! (2턴간 체력 1로 버틴다 · 이번 전투에서는 더 발동하지 않는다)"
                     % target.name, HEAL)
            self.fx_heal(target.id, "UNDYING", dy=-34)
            beep([(1046, 60), (1318, 90)], self.sound)

        if dmg > 0:
            self.fx_number(target.id, "-%d" % dmg, DMG, 26 if dmg >= 30 else 21)
            self.shakes[target.id] = 0.32
            beep([(140, 45), (95, 40)], self.sound)
        elif blocked_to_zero:
            self.fx_number(target.id, "BLOCKED", SPC, 17)
        else:
            self.fx_number(target.id, "MISS", MUT, 17)

        # 격파/전투불능 로그는 공격 로그(cb) 뒤에 찍히도록 지연시킨다
        queued = []
        if hero_revived:
            revive_message = "영웅이 돌아왔다."
            revive_message += " 보호막 +%d." % revive_shield_gained
            if revived_broken:
                revive_message += " 격파 상태 해제."
            queued.append((revive_message,
                           STAR_COLOR[3]))
        if hero_damage_shield:
            queued.append(("HERO/H 피해 패시브: 보호막 +%d (%d/50)." %
                           (hero_damage_shield, target.hero_passive_shield_gained), HEAL))
        if (dmg > 0 and not target.broken and not fixed and not hero_revived and not no_break
                and not target.orch_break_immune):
            bd = dmg // 2
            if attacker.side == "ally" and target.side == "enemy" and self.aug_brk_bonus:
                bd = round(bd * (1 + self.aug_brk_bonus))
            if bd > 0:
                projected_brk = target.brk - bd
                if imperial_safety and target.side == "ally":
                    target.brk = max(1, projected_brk)
                    if projected_brk <= 1:
                        target.imperial_safety_used = True
                else:
                    target.brk = max(0, projected_brk)
                if target.brk <= 0:
                    target.broken = True
                    target.broken_skips = 1
                    queued.append(("💥 %s의 격파체력이 소진됐다 — 격파!" % target.name, BRKC))
                    if not (target.side == "ally" and target.immortal_turns > 0):
                        self.fx_break(target.id)
                        beep([(70, 120), (52, 160)], self.sound)

        if not target.alive:
            queued.append(("%s이(가) 전투불능 상태가 됐다." % target.name, TXT))
            if was_alive and target.side == "enemy" and target.hp == 0:
                self.aspect_shards += 10
                queued.append(("적 처치 보상: 조각 +10 (보유 %d개)" % self.aspect_shards, SPC))
                self.fx_number(target.id, "+10 조각", SPC, 18, dy=-24)
                self.drop_loot(target, queued)
                if attacker is not None and self.is_oracle(attacker):
                    self.or_mission(attacker, "적 처치")
                if self.is_fate_c(attacker) and attacker.alive:
                    before_hp = attacker.hp
                    attacker.hp = min(attacker.max_hp, attacker.hp + 30)
                    healed = attacker.hp - before_hp
                    if healed:
                        queued.append(("Fate Lost/C 패시브: 체력 +%d 회복." % healed,
                                       HEAL))
                        self.fx_heal(attacker.id, "+%d" % healed)

        self.render()

        def finish():
            cb(dmg)
            for msg, color in queued:
                self.log(msg, color)
            if queued:
                self.render()

        self.schedule(540, finish)

    # ---------------- 라운드 종료 / 페이즈 ----------------
    def end_round(self):
        if self.game_over:
            return
        if self.check_end():
            return
        for u in self.units.values():
            if u.alive and u.danger_turns > 0:
                u.danger_turns -= 1
                if u.danger_turns == 0:
                    self.log("%s은 장난을 모두 받아줬다." % u.name, MUT)
        for _u in self.units.values():
            if _u.alive and _u.bloom_turns > 0:
                _u.bloom_turns -= 1
                if _u.bloom_turns == 0:
                    self.log("%s의 개화가 시들었다." % _u.name, ROSE)
        for _u in self.allies():
            if _u.alive and self.is_underboss(_u):
                self.ub_shift(_u, -2)         # 턴 종료시 예지 -2
        self.round += 1
        self.status_msg = "라운드 종료."
        self.render()
        self.schedule(420, self.start_round)

    def check_end(self):
        if all(not u.alive for u in self.allies()):
            self.finish(False)
            return True
        if all(not u.alive for u in self.enemies()):
            self.next_phase()
            return True
        return False

    def next_phase(self):
        cleared_boss = self.boss_mode
        self.phase += 1
        if (self.phase - 1) in DIM_LOOT_PHASES:
            _n = DIM_CLEAR_AMOUNT
            _tot = self.add_item("dim_wish", _n)
            self.log("PHASE %d 클리어 보상: 희미한 소망 +%d (보유 %d개)" % (self.phase - 1, _n, _tot),
                     ITEM_TIER_COLOR[2])
        if (self.phase - 1) in LOOT_PHASES:
            _n = LOOT_CLEAR_AMOUNT
            _tot = self.add_item("faded_wish", _n)
            self.log("PHASE %d 클리어 보상: 빛바랜 소망 +%d (보유 %d개)" % (self.phase - 1, _n, _tot),
                     ITEM_TIER_COLOR[1])
        self.busy = True
        if cleared_boss:
            self.aspect_shards += 100
            self.log("스테이지 클리어 보상: 조각 +100 (보유 %d개)" % self.aspect_shards, SPC)
        for u in self.allies():
            hp_amt = round(u.max_hp * 0.5)
            brk_amt = round(u.max_brk * 0.5)
            if not u.alive:
                u.hp, u.brk = hp_amt, brk_amt
                u.broken = False
                u.broken_skips = 0
                u.immortal_turns = 0
                self.log("%s이(가) 전열 재정비 중 부활했다. (체력 %d)" % (u.name, u.hp), TXT)
                self.fx_revive(u.id)
            else:
                u.hp = min(u.max_hp, u.hp + hp_amt)
                if not u.broken:
                    u.brk = min(u.max_brk, u.brk + brk_amt)
                self.log("%s 체력 +%d, 격파체력 +%d 회복." % (u.name, hp_amt, brk_amt), HEAL)
            u.status = None
            u.plan = None

        if cleared_boss:
            theme = theme_of(self.phase)
            self.log("— STAGE %d 진입 — %s" % (stage_of(self.phase), theme["label"]), TXT)
            self.banner("STAGE %d" % stage_of(self.phase), theme["label"])
        else:
            self.log("— PHASE %d — 새로운 적 병력이 접근한다." % self.phase, TXT)
            self.banner("PHASE %d" % self.phase, "적 전멸")
        beep([(523, 90), (659, 90), (784, 90), (1046, 160)], self.sound)
        self.render()
        self.schedule(1900, lambda: self.offer_augment(2 if cleared_boss else 1))

    # ---------------- 페이즈 클리어 증강 ----------------
    def offer_augment(self, tier=1):
        self.busy = False
        self.overlay = None
        self.pending = None
        self.acting = None
        self.status_msg = None
        self.aug_tier = tier
        self.finish_augment()       # 증강 시스템 제거 — 선택창 없이 바로 다음 웨이브
        return

        pool_all = AUGMENTS if tier == 1 else AUGMENTS2
        taken = self.aug_taken if tier == 1 else self.aug_taken2
        pool = [a for a in pool_all if a["id"] not in taken]
        if not pool:
            self.log("%s 증강은 이미 모두 획득했다." % ("1티어" if tier == 1 else "보스 보상(2티어)"), MUT)
            self.finish_augment()
            return

        self.aug_options = random.sample(pool, min(3, len(pool)))
        self.state = "augment_pick"
        self.log("증강 선택(%s) — %s 중 하나를 고른다."
                 % ("보스 보상" if tier == 2 else "일반",
                    " / ".join(a["title"] for a in self.aug_options)), SPC)
        self.render()

    def choose_augment(self, idx):
        if self.state != "augment_pick" or not self.aug_options:
            return
        if idx >= len(self.aug_options):
            return
        aug = self.aug_options[idx]
        if self.aug_tier == 1 and aug["id"] == "sp_full":
            self.aug_pick = aug
            self.state = "augment_target"
            self.status_msg = "SP를 가득 채울 아군을 선택하세요."
            self.render()
            return
        self.apply_augment(aug, self.aug_tier)
        self.finish_augment()

    def apply_augment(self, aug, tier=1):
        if tier == 1:
            self.aug_taken.append(aug["id"])
        else:
            self.aug_taken2.append(aug["id"])

        if aug["id"] == "hp":
            for u in self.allies():
                u.max_hp += 50
                if u.alive:
                    u.hp = min(u.max_hp, u.hp + 50)
            self.log("증강 [%s] 획득! 아군 최대 체력 +50 (즉시 회복)." % aug["title"], HEAL)
        elif aug["id"] == "atk":
            self.aug_atk_bonus += 5
            self.log("증강 [%s] 획득! 기본 공격 피해 %d → %d."
                     % (aug["title"], 10 + self.aug_atk_bonus - 5, 10 + self.aug_atk_bonus), DMG)
        elif aug["id"] == "brk":
            self.aug_brk_bonus += 0.15
            self.log("증강 [%s] 획득! 적에게 입히는 격파피해 +%d%%."
                     % (aug["title"], round(self.aug_brk_bonus * 100)), BRKC)
        elif aug["id"] == "dice":
            self.aug_speed_min = 2
            self.log("증강 [%s] 획득! 아군 속도 주사위가 2~6이 된다." % aug["title"], SPC)
        elif aug["id"] == "s2_hp":
            for u in self.allies():
                u.max_hp += 50
                if u.alive:
                    u.hp = min(u.max_hp, u.hp + 50)
            self.log("증강 [%s] 획득! 아군 최대 체력 +50 (즉시 회복)." % aug["title"], HEAL)
        elif aug["id"] == "s2_atk":
            self.aug_atk_bonus += 5
            self.log("증강 [%s] 획득! 기본 공격 피해 %d → %d."
                     % (aug["title"], 10 + self.aug_atk_bonus - 5, 10 + self.aug_atk_bonus), DMG)
        elif aug["id"] == "s2_brk":
            for u in self.allies():
                u.max_brk += 50
                if u.alive and not u.broken:
                    u.brk = min(u.max_brk, u.brk + 50)
            self.log("증강 [%s] 획득! 아군 최대 격파체력 +50 (즉시 회복)." % aug["title"], BRKC)
        elif aug["id"] == "s2_reduce":
            self.aug_dmg_reduction += 10
            self.log("증강 [%s] 획득! 아군이 받는 모든 피해 -%d." % (aug["title"], self.aug_dmg_reduction), SPC)
        elif aug["id"] == "s2_undying":
            self.aug_undying = True
            self.log("증강 [%s] 획득! 전투당 1회, 아군이 죽기 직전 체력 1로 버티는 불사 상태에 진입한다." % aug["title"], HEAL)
        self.render()

    def apply_sp_full_target(self, uid):
        if self.state != "augment_target":
            return
        u = self.units.get(uid)
        if not u or u.side != "ally" or not u.alive:
            return
        if self.is_fate_c(u) or self.is_imperial_n(u):
            self.status_msg = "%s는 외부 효과로 SP를 회복할 수 없다. 다른 아군을 선택하세요." % u.name
            self.render()
            return
        u.sp = u.max_sp
        self.aug_taken.append("sp_full")
        self.log("증강 [전술 재정비] 획득! %s의 SP가 가득 찼다." % u.name, SPC)
        self.fx_heal(u.id, "SP MAX")
        beep([(880, 70), (1046, 70), (1318, 110)], self.sound)
        self.finish_augment()

    def finish_augment(self):
        self.state = "idle"
        self.aug_options = None
        self.status_msg = "전열 재정비 완료 — 다음 병력이 접근한다."
        self.render()
        self.spawn_wave()
        self.round = 1
        self.begin_wave(700)

    def finish(self, win):
        self.game_over = True
        self.busy = False
        self.state = "over"
        self.acting = None
        self.pending = None
        self.aug_options = None
        beep([(392, 120), (349, 120), (294, 160), (220, 260)], self.sound)
        self.modal = dict(title="패배" if not win else "승리",
                          desc="PHASE %d에서 아군이 전부 전투불능이 됐다." % self.phase,
                          color=DMG if not win else HEAL)
        self.render()

    def quit_battle(self):
        self.game_over = True
        self.busy = False
        self.state = "over"
        self.acting = None
        self.pending = None
        self.aug_options = None
        self.modal = dict(title="전투 종료",
                          desc="PHASE %d, 라운드 %d까지 진행했다." % (self.phase, self.round),
                          color=TXT)
        self.render()

    # ================================================================
    # 오버레이 (속도 주사위 / 판정 주사위 / 배너)
    # ================================================================
    def draw_die(self, cx, cy, size, value, face=WHITE, pip="#101318", tag="fx"):
        h = size / 2
        items = [self.canvas.create_rectangle(cx - h, cy - h, cx + h, cy + h,
                                              fill=face, outline=BRD, width=2, tags=tag)]
        for px, py in DICE_PIPS[value]:
            r = size * 0.075
            x, y = cx - h + size * px, cy - h + size * py
            items.append(self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                                 fill=pip, outline="", tags=tag))
        return items

    def roll_dice_overlay(self, actors, done):
        self.busy = True
        self.overlay = dict(kind="speed", actors=actors, vals={u.id: d6() for u in actors})
        ticks = [0]

        def step():
            if ticks[0] >= 11:
                for u in actors:
                    self.overlay["vals"][u.id] = u.speed
                self.render()
                self.schedule(750, finish)
                return
            for u in actors:
                lo = self.aug_speed_min if u.side == "ally" else 1
                self.overlay["vals"][u.id] = random.randint(lo, 6)
            beep([(340, 18)], self.sound)
            ticks[0] += 1
            self.render()
            self.schedule(75, step)

        def finish():
            self.overlay = None
            self.busy = False
            self.render()
            done()

        step()

    def dice_judge_overlay(self, pairs, done):
        self.overlay = dict(kind="judge", pairs=[[lab, d6()] for lab, _ in pairs])
        ticks = [0]

        def step():
            if ticks[0] >= 9:
                for i, (lab, v) in enumerate(pairs):
                    self.overlay["pairs"][i][1] = v
                self.render()
                self.schedule(620, finish)
                return
            for p in self.overlay["pairs"]:
                p[1] = d6()
            beep([(340, 15)], self.sound)
            ticks[0] += 1
            self.render()
            self.schedule(70, step)

        def finish():
            self.overlay = None
            self.render()
            done()

        step()

    def banner(self, text, sub):
        self.overlay = dict(kind="banner", text=text, sub=sub)

    # ================================================================
    # 이펙트
    # ================================================================
    def add_fx(self, items, dur, update=None):
        self.effects.append(dict(items=items, dur=dur, t=0.0, update=update))
        self.canvas.tag_raise("fx")

    def rect_of(self, uid):
        return self.card_rects.get(uid, (MARGIN, ENEMY_Y, CARD_W, CARD_H))

    def center_of(self, uid):
        x, y, w, h = self.rect_of(uid)
        return x + w / 2, y + h / 2

    def fx_number(self, uid, text, color, size=21, dy=0):
        x, y = self.center_of(uid)
        y += dy
        item = self.canvas.create_text(x, y, text=text, fill=color,
                                       font=(self.fm, size, "bold"), tags="fx")

        def up(p, e):
            self.canvas.coords(item, x, y - 42 * p)
            self.canvas.itemconfig(item, fill=lerp_color(color, BG, max(0, (p - 0.55) / 0.45)))

        self.add_fx([item], 0.9, up)

    def fx_flash(self, uid, color, alpha="gray25"):
        x, y, w, h = self.rect_of(uid)
        item = self.canvas.create_rectangle(x, y, x + w, y + h, fill=color, outline="",
                                            stipple=alpha, tags="fx")
        self.add_fx([item], 0.22)

    def fx_particles(self, uid, color, n=22, spread=120, dur=0.6, size=4):
        cx, cy = self.center_of(uid)
        items, vel = [], []
        for _ in range(n):
            a = random.random() * math.tau
            sp = spread * (0.35 + random.random())
            items.append(self.canvas.create_oval(cx - size, cy - size, cx + size, cy + size,
                                                 fill=color, outline="", tags="fx"))
            vel.append((math.cos(a) * sp, math.sin(a) * sp))

        def up(p, e):
            for it, (vx, vy) in zip(items, vel):
                x = cx + vx * p
                y = cy + vy * p + 90 * p * p
                s = size * (1 - p * 0.7)
                self.canvas.coords(it, x - s, y - s, x + s, y + s)
                self.canvas.itemconfig(it, fill=lerp_color(color, BG, p))

        self.add_fx(items, dur, up)

    def fx_hit(self, uid):
        self.fx_particles(uid, DMG, n=10, spread=70, dur=0.4, size=3)
        self.fx_flash(uid, DMG)

    def fx_bullet(self, uid):
        x, y, w, h = self.rect_of(uid)
        cy = y + h * 0.45
        line = self.canvas.create_line(x - 40, cy, x - 40, cy, fill=WHITE, width=3, tags="fx")

        def up(p, e):
            head = x - 40 + (w + 80) * min(1.0, p * 1.6)
            tail = max(x - 40, head - 150)
            self.canvas.coords(line, tail, cy, head, cy)
            self.canvas.itemconfig(line, fill=lerp_color(WHITE, DMG, p))

        self.add_fx([line], 0.22, up)
        self.root.after(120, lambda: self.fx_particles(uid, DMG, n=12, spread=80, dur=0.45, size=3))

    def fx_slash(self, uid, count=1, color=DMG):
        x, y, w, h = self.rect_of(uid)
        for i in range(count):
            self.root.after(int(i * 130), lambda: self._one_slash(x, y, w, h,
                                                                 random.uniform(-40, -14), color))
        self.fx_flash(uid, color)

    def _one_slash(self, x, y, w, h, ang, color=DMG):
        cx, cy = x + w / 2, y + h / 2
        rad = math.radians(ang)
        L = max(w, h) * 1.15
        dx, dy = math.cos(rad) * L / 2, math.sin(rad) * L / 2
        core = self.canvas.create_line(cx, cy, cx, cy, fill=WHITE, width=5, tags="fx")
        glow = self.canvas.create_line(cx, cy, cx, cy, fill=color, width=11, tags="fx")

        def up(p, e):
            t = min(1.0, p * 1.5)
            x1, y1 = cx - dx, cy - dy
            x2 = x1 + dx * 2 * t
            y2 = y1 + dy * 2 * t
            for it in (glow, core):
                self.canvas.coords(it, x1, y1, x2, y2)
            self.canvas.itemconfig(core, fill=lerp_color(WHITE, BG, max(0, (p - 0.5) * 2)))
            self.canvas.itemconfig(glow, fill=lerp_color(color, BG, p))

        self.add_fx([glow, core], 0.32, up)

    def fx_heavy(self, uid):
        cx, cy = self.center_of(uid)
        ring = self.canvas.create_oval(cx, cy, cx, cy, outline=SPC, width=4, tags="fx")

        def up(p, e):
            r = 10 + 80 * p
            self.canvas.coords(ring, cx - r, cy - r * 0.8, cx + r, cy + r * 0.8)
            self.canvas.itemconfig(ring, outline=lerp_color(SPC, BG, p), width=max(1, 5 - 4 * p))

        self.add_fx([ring], 0.45, up)
        self.fx_particles(uid, DMG, n=26, spread=150, dur=0.65, size=5)
        self.fx_flash(uid, SPC, "gray50")

    def fx_hero_impact(self, uid):
        x, y, w, h = self.rect_of(uid)
        cx, cy = x + w / 2, y + h / 2
        rings = [self.canvas.create_oval(cx, cy, cx, cy, outline=color, width=width, tags="fx")
                 for color, width in ((WHITE, 6), (STAR_COLOR[3], 4), (SPC, 2))]
        flash = self.canvas.create_rectangle(x, y, x + w, y + h, fill=WHITE, outline="",
                                             stipple="gray50", tags="fx")

        def up(p, effect):
            for i, ring in enumerate(rings):
                progress = min(1.0, max(0.0, p * 1.4 - i * 0.12))
                radius = 12 + (150 + i * 24) * progress
                self.canvas.coords(ring, cx - radius, cy - radius * 0.72,
                                   cx + radius, cy + radius * 0.72)
                self.canvas.itemconfig(ring, outline=lerp_color(
                    (WHITE, STAR_COLOR[3], SPC)[i], BG, progress))
            self.canvas.itemconfig(flash, stipple="gray50" if p < 0.18 else "gray25")

        self.add_fx(rings + [flash], 0.48, up)
        self.fx_particles(uid, WHITE, n=28, spread=220, dur=0.6, size=5)
        self.fx_particles(uid, STAR_COLOR[3], n=18, spread=150, dur=0.7, size=4)
        self.shakes[uid] = 0.5

    def fx_hero_dash(self, source_uid, target_uid):
        sx, sy = self.center_of(source_uid)
        tx, ty = self.center_of(target_uid)
        trail = self.canvas.create_line(sx, sy, sx, sy, fill=STAR_COLOR[3], width=16,
                                        capstyle="round", tags="fx")
        core = self.canvas.create_line(sx, sy, sx, sy, fill=WHITE, width=5,
                                       capstyle="round", tags="fx")
        ring = self.canvas.create_oval(tx, ty, tx, ty, outline=WHITE, width=4, tags="fx")

        def up(p, effect):
            progress = min(1.0, p * 1.7)
            hx = sx + (tx - sx) * progress
            hy = sy + (ty - sy) * progress
            self.canvas.coords(trail, sx, sy, hx, hy)
            self.canvas.coords(core, sx, sy, hx, hy)
            radius = 8 + 74 * min(1.0, max(0.0, (p - 0.42) * 2.2))
            self.canvas.coords(ring, tx - radius, ty - radius * 0.7,
                               tx + radius, ty + radius * 0.7)
            self.canvas.itemconfig(trail, fill=lerp_color(STAR_COLOR[3], BG, p))
            self.canvas.itemconfig(core, fill=lerp_color(WHITE, BG, p))
            self.canvas.itemconfig(ring, outline=lerp_color(WHITE, STAR_COLOR[3], p))

        self.add_fx([trail, core, ring], 0.34, up)
        self.fx_flash(target_uid, STAR_COLOR[3], "gray50")
        self.shakes[target_uid] = 0.35

    def fx_fate_explosion(self, uid):
        x, y, w, h = self.rect_of(uid)
        cx, cy = x + w / 2, y + h / 2
        rings = [self.canvas.create_oval(cx, cy, cx, cy, outline=color, width=width, tags="fx")
                 for color, width in ((WHITE, 5), (CURSE, 7), (STAR_COLOR[3], 3))]
        core = self.canvas.create_oval(cx, cy, cx, cy, fill=WHITE, outline=CURSE, width=2, tags="fx")

        def up(p, effect):
            for i, ring in enumerate(rings):
                progress = min(1.0, max(0.0, p * 1.45 - i * 0.15))
                radius = 10 + (100 + 30 * i) * progress
                self.canvas.coords(ring, cx - radius, cy - radius * 0.8,
                                   cx + radius, cy + radius * 0.8)
                self.canvas.itemconfig(ring, outline=lerp_color(
                    (WHITE, CURSE, STAR_COLOR[3])[i], BG, progress))
            core_radius = max(0, 26 * (1 - p * 2.4))
            self.canvas.coords(core, cx - core_radius, cy - core_radius,
                               cx + core_radius, cy + core_radius)
            self.canvas.itemconfig(core, fill=lerp_color(WHITE, CURSE, min(1.0, p * 2)))

        self.add_fx(rings + [core], 0.5, up)
        self.fx_particles(uid, CURSE, n=32, spread=210, dur=0.65, size=5)
        self.fx_flash(uid, WHITE, "gray50")
        self.shakes[uid] = 0.45

    def fx_fate_chains(self, source_uid, target_ids):
        sx, sy = self.center_of(source_uid)
        chains, bursts = [], []
        for target_uid in target_ids:
            tx, ty = self.center_of(target_uid)
            chains.append((self.canvas.create_line(sx, sy, sx, sy, fill=CURSE, width=4,
                                                   capstyle="round", tags="fx"),
                           tx, ty, target_uid))
            bursts.append(self.canvas.create_oval(tx, ty, tx, ty, outline=STAR_COLOR[3],
                                                  width=3, tags="fx"))

        def up(p, effect):
            chain_progress = min(1.0, p * 1.45)
            for line, tx, ty, target_uid in chains:
                dx, dy = tx - sx, ty - sy
                length = max(1.0, math.hypot(dx, dy))
                px, py = -dy / length, dx / length
                coords = []
                for step in range(9):
                    t = min(chain_progress, step / 8.0)
                    offset = math.sin(t * math.pi * 12) * 9 * min(1.0, p * 3)
                    coords.extend((sx + dx * t + px * offset, sy + dy * t + py * offset))
                self.canvas.coords(line, *coords)
                self.canvas.itemconfig(line, fill=lerp_color(CURSE, WHITE, 0.3 if p > 0.65 else 0))
            for ring in bursts:
                radius = 6 + 58 * min(1.0, max(0.0, (p - 0.55) * 2.5))
                coords = self.canvas.coords(ring)
                tx, ty = (coords[0] + coords[2]) / 2, (coords[1] + coords[3]) / 2
                self.canvas.coords(ring, tx - radius, ty - radius, tx + radius, ty + radius)
                self.canvas.itemconfig(ring, outline=lerp_color(STAR_COLOR[3], WHITE, p))

        self.add_fx([line for line, _, _, _ in chains] + bursts, 0.72, up)

    def fx_imperial_star(self, uid):
        cx, cy = self.center_of(uid)
        rays = []
        for index in range(8):
            angle = math.tau * index / 8
            rays.append(self.canvas.create_line(cx, cy, cx, cy, fill=SPC, width=4,
                                                capstyle="round", tags="fx"))
        star = self.canvas.create_polygon(cx, cy, cx, cy, cx, cy, cx, cy, cx, cy,
                                          fill=WHITE, outline=STAR_COLOR[3], width=2, tags="fx")

        def up(p, effect):
            radius = 18 + 105 * min(1.0, p * 1.5)
            points = []
            for index in range(10):
                angle = -math.pi / 2 + math.pi * index / 5
                r = radius if index % 2 == 0 else radius * 0.34
                points.extend((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
            self.canvas.coords(star, *points)
            for index, ray in enumerate(rays):
                angle = math.tau * index / len(rays)
                inner = radius * 0.55
                outer = radius + 24
                self.canvas.coords(ray, cx + math.cos(angle) * inner,
                                   cy + math.sin(angle) * inner,
                                   cx + math.cos(angle) * outer,
                                   cy + math.sin(angle) * outer)
                self.canvas.itemconfig(ray, fill=lerp_color(SPC, BG, p))
            self.canvas.itemconfig(star, fill=lerp_color(WHITE, STAR_COLOR[3], p))

        self.add_fx(rays + [star], 0.48, up)
        self.fx_particles(uid, SPC, n=18, spread=160, dur=0.5, size=4)
        self.fx_flash(uid, WHITE, "gray50")

    def fx_imperial_prayer(self, uid, strong=False, source_center=None):
        cx, cy = self.center_of(uid)
        color = SPC if strong else HEAL
        halo = self.canvas.create_oval(cx, cy, cx, cy, outline=color, width=4, tags="fx")
        rays = [self.canvas.create_line(cx, cy, cx, cy, fill=WHITE, width=2, tags="fx")
                for _ in range(12 if strong else 8)]
        beam = None
        if source_center:
            beam = self.canvas.create_line(source_center[0], source_center[1], cx, cy,
                                           fill=WHITE, width=5, capstyle="round", tags="fx")

        def up(p, effect):
            radius = (12 + 116 * p) if strong else (8 + 70 * p)
            self.canvas.coords(halo, cx - radius, cy - radius * 0.55,
                               cx + radius, cy + radius * 0.55)
            self.canvas.itemconfig(halo, outline=lerp_color(color, BG, p),
                                   width=max(1, 5 - 4 * p))
            for index, ray in enumerate(rays):
                angle = math.tau * index / len(rays) - math.pi / 2
                inner, outer = radius * 0.75, radius + (28 if strong else 16)
                self.canvas.coords(ray, cx + math.cos(angle) * inner,
                                   cy + math.sin(angle) * inner * 0.55,
                                   cx + math.cos(angle) * outer,
                                   cy + math.sin(angle) * outer * 0.55)
                self.canvas.itemconfig(ray, fill=lerp_color(WHITE, BG, p))
            if beam:
                self.canvas.itemconfig(beam, fill=lerp_color(WHITE, color, p),
                                       width=max(1, 6 - 5 * p))

        self.add_fx([halo] + rays + ([beam] if beam else []), 0.85 if strong else 0.65, up)
        self.fx_particles(uid, color, n=30 if strong else 18, spread=100 if strong else 70,
                          dur=0.9 if strong else 0.65, size=4)

    def fx_imperial_hope(self, target_uid, source_center=None):
        self.fx_imperial_prayer(target_uid, strong=True, source_center=source_center)

    def fx_imperial_guardian(self, source_uid, ally_uid):
        sx, sy = self.center_of(source_uid)
        tx, ty = self.center_of(ally_uid)
        line = self.canvas.create_line(sx, sy, sx, sy, fill=HEAL, width=5,
                                       dash=(3, 5), tags="fx")
        glow = self.canvas.create_oval(tx, ty, tx, ty, outline=HEAL, width=3, tags="fx")

        def up(p, effect):
            progress = min(1.0, p * 1.5)
            self.canvas.coords(line, sx, sy, sx + (tx - sx) * progress,
                               sy + (ty - sy) * progress)
            radius = 8 + 48 * min(1.0, max(0.0, (p - 0.25) * 2.0))
            self.canvas.coords(glow, tx - radius, ty - radius * 0.65,
                               tx + radius, ty + radius * 0.65)
            self.canvas.itemconfig(line, fill=lerp_color(HEAL, BG, p))
            self.canvas.itemconfig(glow, outline=lerp_color(HEAL, WHITE, p))

        self.add_fx([line, glow], 0.55, up)

    def fx_imperial_barrage(self, targets):
        """섬멸 명령 — 화면 아래에서 미사일이 솟아올라 적진 곳곳에 떨어지며 핑크빛으로 폭발한다."""
        if not targets:
            return
        PINK = ROSE
        LIGHT = "#FFC2E2"
        shells = []
        for _ in range(34):
            target = random.choice(targets)
            rx, ry, rw, rh = self.rect_of(target.id)
            tx = rx + random.uniform(8, max(9, rw - 8))      # 카드 안의 무작위 지점
            ty = ry + random.uniform(8, max(9, rh - 8))
            sx = max(10, min(WIN_W - 10, tx + random.uniform(-260, 260)))   # 화면 아래에서 발사
            sy = WIN_H + random.uniform(10, 70)
            delay = random.random() * 0.5
            flight = random.uniform(0.2, 0.3)
            sway = random.uniform(-40, 40)                    # 살짝 휘어 날아가는 궤적
            trail = self.canvas.create_line(sx, sy, sx, sy, fill=LIGHT, width=3,
                                            capstyle="round", tags="fx")
            head = self.canvas.create_oval(sx, sy, sx, sy, fill=WHITE, outline=PINK,
                                           width=2, tags="fx")
            blast = self.canvas.create_oval(tx, ty, tx, ty, outline=PINK, width=4, tags="fx")
            core = self.canvas.create_oval(tx, ty, tx, ty, fill=LIGHT, outline="", tags="fx")
            shells.append(dict(trail=trail, head=head, blast=blast, core=core,
                               sx=sx, sy=sy, tx=tx, ty=ty, delay=delay, flight=flight,
                               sway=sway, uid=target.id, boom=False,
                               size=random.uniform(26, 46)))

        items = []
        for sh in shells:
            items += [sh["trail"], sh["head"], sh["blast"], sh["core"]]
        total = 2.0

        def path(sh, q):
            q = min(1.0, max(0.0, q))
            x = sh["sx"] + (sh["tx"] - sh["sx"]) * q + math.sin(q * math.pi) * sh["sway"]
            y = sh["sy"] + (sh["ty"] - sh["sy"]) * q
            return x, y

        def up(p, effect):
            for sh in shells:
                t0 = sh["delay"]
                t1 = t0 + sh["flight"]
                if p < t0:
                    continue
                if p < t1:                                   # 비행 중
                    q = (p - t0) / sh["flight"]
                    hx, hy = path(sh, q)
                    tx_, ty_ = path(sh, q - 0.22)
                    self.canvas.coords(sh["trail"], tx_, ty_, hx, hy)
                    self.canvas.coords(sh["head"], hx - 4, hy - 4, hx + 4, hy + 4)
                    continue
                # 착탄 — 한 번만 카드 흔들림/효과음
                if not sh["boom"]:
                    sh["boom"] = True
                    self.canvas.coords(sh["trail"], 0, 0, 0, 0)
                    self.canvas.coords(sh["head"], 0, 0, 0, 0)
                    self.shakes[sh["uid"]] = 0.25
                    if random.random() < 0.25:
                        beep([(random.randint(70, 130), 40)], self.sound)
                b = min(1.0, (p - t1) / 0.2)                 # 폭발 진행도
                r = sh["size"] * (0.25 + 0.75 * b)
                tx, ty = sh["tx"], sh["ty"]
                self.canvas.coords(sh["blast"], tx - r, ty - r * 0.8, tx + r, ty + r * 0.8)
                self.canvas.itemconfig(sh["blast"], outline=lerp_color(PINK, BG, b),
                                       width=max(1, 5 - 4 * b))
                cr = r * 0.55 * (1 - b)
                self.canvas.coords(sh["core"], tx - cr, ty - cr, tx + cr, ty + cr)
                self.canvas.itemconfig(sh["core"], fill=lerp_color(LIGHT, PINK, b))

        self.add_fx(items, total, up)
        # 착탄 지점마다 핑크 파편이 튀도록 일정 간격으로 파티클을 터뜨린다
        for sh in shells:
            ms = int((sh["delay"] + sh["flight"]) * total * 1000)
            self.root.after(ms, lambda s=sh: self._barrage_burst(s["uid"], s["tx"], s["ty"]))
        for target in targets:
            self.root.after(700, lambda uid=target.id: self.fx_flash(uid, ROSE, "gray25"))
            self.root.after(1300, lambda uid=target.id: self.fx_flash(uid, ROSE, "gray25"))

    def _barrage_burst(self, uid, x, y):
        items, vel = [], []
        for _ in range(7):
            a = random.random() * math.tau
            sp = random.uniform(40, 120)
            items.append(self.canvas.create_oval(x - 3, y - 3, x + 3, y + 3,
                                                 fill=ROSE, outline="", tags="fx"))
            vel.append((math.cos(a) * sp, math.sin(a) * sp))

        def up(p, e):
            for it, (vx, vy) in zip(items, vel):
                px, py = x + vx * p, y + vy * p + 40 * p * p
                s = 3 * (1 - p * 0.8)
                self.canvas.coords(it, px - s, py - s, px + s, py + s)
                self.canvas.itemconfig(it, fill=lerp_color("#FFC2E2", BG, p))

        self.add_fx(items, 0.45, up)


    def fx_break(self, uid):
        cx, cy = self.center_of(uid)
        shards = []
        vel = []
        for _ in range(18):
            a = random.random() * math.tau
            sp = 170 * (0.4 + random.random())
            shards.append(self.canvas.create_polygon(cx, cy, cx + 8, cy + 3, cx + 2, cy + 10,
                                                     fill=BRKC, outline="", tags="fx"))
            vel.append((math.cos(a) * sp, math.sin(a) * sp))

        def up(p, e):
            for it, (vx, vy) in zip(shards, vel):
                self.canvas.move(it, vx * 0.016, vy * 0.016 + 3 * p)
                self.canvas.itemconfig(it, fill=lerp_color(BRKC, BG, p))

        self.add_fx(shards, 0.7, up)
        self.fx_flash(uid, BRKC, "gray50")
        self.fx_number(uid, "BREAK", BRKC, 20)
        self.shakes[uid] = 0.5

    def fx_heal(self, uid, label="+", dy=0):
        x, y, w, h = self.rect_of(uid)
        items, base = [], []
        for _ in range(16):
            px = x + random.uniform(10, w - 10)
            py = y + h - random.uniform(0, 20)
            items.append(self.canvas.create_oval(px - 3, py - 3, px + 3, py + 3,
                                                 fill=HEAL, outline="", tags="fx"))
            base.append((px, py, random.uniform(0.7, 1.3)))

        def up(p, e):
            for it, (px, py, sp) in zip(items, base):
                ny = py - h * p * sp
                nx = px + math.sin(p * 8 + px) * 4
                self.canvas.coords(it, nx - 3, ny - 3, nx + 3, ny + 3)
                self.canvas.itemconfig(it, fill=lerp_color(HEAL, BG, p * 0.9))

        self.add_fx(items, 0.75, up)
        self.fx_flash(uid, HEAL)
        self.fx_number(uid, label, HEAL, 22, dy)

    def fx_revive(self, uid):
        x, y, w, h = self.rect_of(uid)
        cx = x + w / 2
        pillar = self.canvas.create_rectangle(cx - 6, y, cx + 6, y + h, fill=HEAL,
                                              outline="", stipple="gray50", tags="fx")
        glow = self.canvas.create_oval(cx - 20, y + h - 20, cx + 20, y + h + 10,
                                       fill=HEAL, outline="", stipple="gray25", tags="fx")

        def up(p, e):
            wdt = 6 + 60 * math.sin(math.pi * min(1.0, p * 1.2))
            self.canvas.coords(pillar, cx - wdt, y - 20 * p, cx + wdt, y + h)
            self.canvas.itemconfig(pillar, fill=lerp_color(WHITE, HEAL, min(1, p * 2)))
            r = 20 + 50 * p
            self.canvas.coords(glow, cx - r, y + h - r * 0.4, cx + r, y + h + r * 0.3)

        self.add_fx([pillar, glow], 0.9, up)
        self.fx_heal(uid, "REVIVE")

    def fx_stance(self, uid, color):
        x, y, w, h = self.rect_of(uid)
        box = self.canvas.create_rectangle(x - 6, y - 6, x + w + 6, y + h + 6,
                                           outline=color, width=3, tags="fx")

        def up(p, e):
            o = 6 - 6 * p
            self.canvas.coords(box, x - o, y - o, x + w + o, y + h + o)
            self.canvas.itemconfig(box, outline=lerp_color(color, BG, p))

        self.add_fx([box], 0.5, up)

    def fx_flag(self, uid, color):
        x, y, w, h = self.rect_of(uid)
        pole_x = x + w * 0.72
        base_y = y + h - 16
        pole = self.canvas.create_line(pole_x, base_y, pole_x, base_y,
                                      fill=WHITE, width=4, tags="fx")
        cloth = self.canvas.create_polygon(pole_x, base_y, pole_x, base_y,
                                           pole_x, base_y, pole_x, base_y,
                                           fill=color, outline=WHITE, width=1, tags="fx")
        ground = self.canvas.create_oval(pole_x, base_y, pole_x, base_y,
                                         outline=color, width=3, tags="fx")

        def up(p, e):
            rise = min(1.0, p * 1.25)
            top_y = base_y - (h + 30) * rise
            self.canvas.coords(pole, pole_x, base_y, pole_x, top_y)
            spread = max(0.0, min(1.0, (p - 0.12) * 2.0))
            cloth_w = w * 0.34 * spread
            flutter = math.sin(p * math.tau * 2) * 3 * spread
            self.canvas.coords(cloth, pole_x, top_y + 3,
                               pole_x + cloth_w, top_y + 7 + flutter,
                               pole_x + cloth_w * 0.82, top_y + 24 + flutter,
                               pole_x, top_y + 20)
            radius = 6 + 34 * min(1.0, p * 2.5)
            self.canvas.coords(ground, pole_x - radius, base_y - 4,
                               pole_x + radius, base_y + 4)
            self.canvas.itemconfig(ground, outline=lerp_color(color, BG, p))

        self.add_fx([pole, cloth, ground], 0.9, up)

    # ================================================================
    # 형상 스킬 이펙트 (fx 패치) — 분배자 모래시계 / 화가 붓·팔레트
    # ================================================================
    def _fx_vis(self, items, on):
        st = "normal" if on else "hidden"
        for it in items:
            self.canvas.itemconfig(it, state=st)

    def fx_hourglass(self, uid, big=False):
        """분배자 — 모래시계가 뒤집혀 돌아가고 모래가 흘러내린다."""
        cv = self.canvas
        cx, cy = self.center_of(uid)
        k = 1.35 if big else 1.0
        w, h = 30 * k, 46 * k
        dur = 1.15 if big else 0.95
        GLASS = lerp_color(CURSE, WHITE, 0.55)
        CAP = lerp_color(CURSE, BG, 0.35)

        back = cv.create_oval(cx - 66 * k, cy - 66 * k, cx + 66 * k, cy + 66 * k,
                              fill=lerp_color(BG, CURSE, 0.35), outline="",
                              stipple="gray50", tags="fx")
        ticks = [cv.create_line(cx, cy, cx, cy, fill=CURSE, width=2, tags="fx")
                 for _ in range(12)]
        rings = [cv.create_oval(cx, cy, cx, cy, outline=CURSE, width=3, tags="fx")
                 for _ in range(2)]

        def mk(**kw):
            return cv.create_polygon(cx, cy, cx, cy, cx, cy, tags="fx", **kw)

        sand_a = mk(fill=SPC, outline="")
        sand_b = mk(fill=SPC, outline="")
        glass_u = mk(fill="", outline=GLASS, width=3)
        glass_l = mk(fill="", outline=GLASS, width=3)
        cap_t = mk(fill=CAP, outline=GLASS, width=2)
        cap_b = mk(fill=CAP, outline=GLASS, width=2)
        stream = cv.create_line(cx, cy, cx, cy, fill=SPC, width=2, tags="fx")
        items = [back] + ticks + rings + [sand_a, sand_b, glass_u, glass_l, cap_t, cap_b, stream]

        def rot(x, y, th):
            c, s = math.cos(th), math.sin(th)
            return cx + x * c - y * s, cy + x * s + y * c

        def flat(pts, th=0.0):
            out = []
            for px, py in pts:
                out.extend(rot(px, py, th))
            return out

        def up(p, e):
            fade = max(0.0, (p - 0.8) / 0.2)
            appear = min(1.0, p / 0.12)
            ww, hh = w * (0.6 + 0.4 * appear), h * (0.6 + 0.4 * appear)
            fp = min(1.0, p / 0.4)
            th = math.pi * fp * fp * (3 - 2 * fp)        # 0 -> 180도 뒤집기
            gcol = lerp_color(GLASS, BG, fade)
            ccol = lerp_color(CAP, BG, fade)

            cv.coords(glass_u, *flat([(-ww, -hh), (ww, -hh), (0, 0)], th))
            cv.coords(glass_l, *flat([(-ww, hh), (ww, hh), (0, 0)], th))
            cv.coords(cap_t, *flat([(-ww - 8, -hh - 8), (ww + 8, -hh - 8),
                                    (ww + 8, -hh), (-ww - 8, -hh)], th))
            cv.coords(cap_b, *flat([(-ww - 8, hh), (ww + 8, hh),
                                    (ww + 8, hh + 8), (-ww - 8, hh + 8)], th))
            cv.itemconfig(glass_u, outline=gcol)
            cv.itemconfig(glass_l, outline=gcol)
            cv.itemconfig(cap_t, fill=ccol, outline=gcol)
            cv.itemconfig(cap_b, fill=ccol, outline=gcol)

            iw, ih = ww * 0.86, hh * 0.9
            scol = lerp_color(SPC, BG, fade)
            if p < 0.4:                                   # 뒤집는 동안: 모래는 유리와 함께 돈다
                cv.coords(sand_a, *flat([(-iw, ih), (iw, ih), (0, hh * 0.05)], th))
                cv.itemconfig(sand_a, fill=scol, state="normal")
                self._fx_vis([sand_b, stream], False)
            else:                                         # 뒤집힌 뒤: 위 모래가 아래로 흘러내림
                q = min(1.0, (p - 0.4) / 0.48)
                f, g = 1.0 - q, q
                if f > 0.03:
                    cv.coords(sand_a, *flat([(0, -hh * 0.05), (-iw * f, -ih * f), (iw * f, -ih * f)]))
                    cv.itemconfig(sand_a, fill=scol, state="normal")
                else:
                    cv.itemconfig(sand_a, state="hidden")
                if g > 0.03:
                    cv.coords(sand_b, *flat([(-iw, ih), (iw, ih),
                                             (iw * (1 - g), ih * (1 - g)),
                                             (-iw * (1 - g), ih * (1 - g))]))
                    cv.itemconfig(sand_b, fill=scol, state="normal")
                else:
                    cv.itemconfig(sand_b, state="hidden")
                if 0.0 < q < 1.0:
                    sx, sy1 = rot(0, 0, 0.0)
                    sx2, sy2 = rot(0, ih * (1 - g), 0.0)
                    cv.coords(stream, sx, sy1, sx2, sy2)
                    cv.itemconfig(stream, fill=scol, state="normal")
                else:
                    cv.itemconfig(stream, state="hidden")

            for i, ring in enumerate(rings):              # 시간이 번져나가는 파문
                q2 = min(1.0, max(0.0, p * 1.3 - i * 0.25))
                rad = 24 + 120 * k * q2
                cv.coords(ring, cx - rad, cy - rad, cx + rad, cy + rad)
                cv.itemconfig(ring, outline=lerp_color(CURSE, BG, max(q2, fade)),
                              width=max(1, 4 - 3 * q2))
            for i, tick in enumerate(ticks):              # 시계 눈금이 천천히 돈다
                a_ = i * math.tau / 12 + p * 2.4
                r0, r1 = 58 * k, 70 * k
                cv.coords(tick, cx + math.cos(a_) * r0, cy + math.sin(a_) * r0,
                          cx + math.cos(a_) * r1, cy + math.sin(a_) * r1)
                cv.itemconfig(tick, fill=lerp_color(CURSE, BG, max(fade, 1.0 - appear)))
            cv.itemconfig(back, fill=lerp_color(BG, CURSE, 0.35 * (1.0 - fade)))

        self.add_fx(items, dur, up)
        beep([(660, 40), (880, 50), (440, 90)], self.sound)
        self.root.after(int(dur * 400), lambda: self.fx_flash(uid, CURSE, "gray25"))

    def fx_brush(self, uid, color, strokes=1):
        """화가 N — 붓으로 쓸어 칠하는 스트로크 (털이 갈라진 5겹 선 + 붓 + 흘러내리는 물감)."""
        cv = self.canvas
        x, y, w, h = self.rect_of(uid)
        cx0, cy0 = x + w / 2, y + h / 2
        dur = 0.55 + 0.26 * (strokes - 1)
        light = lerp_color(color, WHITE, 0.45)
        dark = lerp_color(color, BG, 0.35)
        shades = (dark, color, light, color, dark)
        offs = (-14, -7, 0, 7, 14)
        items, data = [], []
        for s in range(strokes):
            sgn = -1 if s % 2 else 1
            xa, xb = (x - 12, x + w + 12) if sgn == 1 else (x + w + 12, x - 12)
            ya = y + h * random.uniform(0.2, 0.5) + s * 26
            yb = ya + random.uniform(-20, 44)
            amp, ph = random.uniform(8, 16), random.uniform(0, 6.28)
            n = 24
            path = [(xa + (xb - xa) * i / n,
                     ya + (yb - ya) * i / n + math.sin(i / n * 5 + ph) * amp)
                    for i in range(n + 1)]
            hid = "hidden" if s else "normal"
            lines = []
            for kk, off in enumerate(offs):
                ln = cv.create_line(cx0, cy0, cx0, cy0, fill=shades[kk],
                                    width=10 - abs(off) * 0.3, capstyle="round",
                                    smooth=True, state=hid, tags="fx")
                lines.append((ln, off, shades[kk]))
                items.append(ln)
            drips = []
            for fq in (0.3, 0.55, 0.8):
                dl = cv.create_line(cx0, cy0, cx0, cy0, fill=color, width=5,
                                    capstyle="round", state="hidden", tags="fx")
                drips.append((dl, fq))
                items.append(dl)
            handle = cv.create_line(cx0, cy0, cx0, cy0, fill="#8B5E34", width=7,
                                    capstyle="round", state=hid, tags="fx")
            tip = cv.create_oval(cx0, cy0, cx0, cy0, fill=color, outline=WHITE, width=1,
                                 state=hid, tags="fx")
            items += [handle, tip]
            data.append(dict(path=path, lines=lines, handle=handle, tip=tip, drips=drips,
                             delay=0.26 * s, sgn=sgn, n=n, shown=(s == 0)))

        def up(p, e):
            now = p * dur
            fade = max(0.0, (p - 0.78) / 0.22)
            for d in data:
                prog = max(0.0, min(1.0, (now - d["delay"]) / 0.36))
                if prog <= 0:
                    continue
                if not d["shown"]:
                    d["shown"] = True
                    for ln, _o, _c in d["lines"]:
                        cv.itemconfig(ln, state="normal")
                    cv.itemconfig(d["handle"], state="normal")
                    cv.itemconfig(d["tip"], state="normal")
                n, path = d["n"], d["path"]
                upto = prog * n
                m = int(upto)
                pts = list(path[:m + 1])
                if m < n:
                    ax, ay = path[m]
                    bx, by = path[m + 1]
                    fr = upto - m
                    pts.append((ax + (bx - ax) * fr, ay + (by - ay) * fr))
                if len(pts) < 2:
                    pts = [pts[0], pts[0]]
                for ln, off, col in d["lines"]:
                    flat = []
                    for i, (px, py) in enumerate(pts):
                        q = min(1.0, i / float(n))
                        flat.extend((px, py + off * (0.4 + 0.6 * math.sin(math.pi * q))))
                    cv.coords(ln, *flat)
                    cv.itemconfig(ln, fill=lerp_color(col, BG, fade))
                hx, hy = pts[-1]
                if prog < 1.0:
                    cv.coords(d["handle"], hx, hy, hx - 46 * d["sgn"], hy - 64)
                    cv.coords(d["tip"], hx - 9, hy - 9, hx + 9, hy + 9)
                else:
                    cv.itemconfig(d["handle"], state="hidden")
                    cv.itemconfig(d["tip"], state="hidden")
                for dl, fq in d["drips"]:
                    gl = max(0.0, min(1.0, (now - d["delay"] - 0.36 * fq - 0.05) / 0.45)) * 30
                    if gl > 1 and prog >= fq:
                        px, py = path[min(n, int(fq * n))]
                        cv.coords(dl, px, py + 8, px, py + 8 + gl)
                        cv.itemconfig(dl, state="normal", fill=lerp_color(color, BG, fade))

        self.add_fx(items, dur, up)

        def impact():
            self.fx_flash(uid, color, "gray25")
            self.fx_particles(uid, color, n=12, spread=90, dur=0.45, size=4)
            self.shakes[uid] = 0.22

        self.root.after(220, impact)
        beep([(300, 30), (240, 50)], self.sound)

    def fx_paint_splash(self, uid, color, src=None, small=False):
        """화가 N — 팔레트에서 물감을 던져 대상 위로 퍼져나가듯 뿌린다.
        src 가 있으면 그 카드에서 팔레트가 나타나 물감이 포물선으로 날아온다."""
        cv = self.canvas
        tx, ty = self.center_of(uid)
        lead = 0.46 if src is not None else 0.0
        post = 0.8 if small else 1.05
        dur = lead + post
        sc = 0.72 if small else 1.0
        light = lerp_color(color, WHITE, 0.42)
        dark = lerp_color(color, BG, 0.4)
        items = []

        def oval(fill="", outline="", **kw):
            it = cv.create_oval(tx, ty, tx, ty, fill=fill, outline=outline, tags="fx", **kw)
            items.append(it)
            return it

        def line(col, width):
            it = cv.create_line(tx, ty, tx, ty, fill=col, width=width, capstyle="round", tags="fx")
            items.append(it)
            return it

        # 팔레트 + 날아가는 물감
        pal, drops = [], []
        pcx = pcy = 0.0
        if src is not None:
            pcx, pcy = self.center_of(src)
            pcy -= 4
            if not small:
                body = oval("#C8A06E", "#6B4A2B", width=2)
                hole = oval(BG, "#6B4A2B")
                dabs = [oval(c) for c in (PAINT_BLUE, PAINT_RED, PAINT_GREEN)]
                pal = [body, hole] + dabs
            for j in range(10):
                it = oval(color)
                cv.itemconfig(it, state="hidden")
                s0 = 0.06 + j * 0.03
                s1 = lead - (9 - j) * 0.018
                drops.append((it, s0, s1, tx + random.uniform(-34, 34) * sc,
                              ty + random.uniform(-22, 22) * sc, random.uniform(4, 8) * sc))
        used = {PAINT_BLUE: 0, PAINT_RED: 1, PAINT_GREEN: 2}.get(color, -1)
        dab_off = [(8, -11), (20, 2), (6, 11)]

        # 착탄 후 퍼지는 물감
        blobs = []
        for idx in range(6):
            base = dark if idx < 2 else (color if idx < 5 else light)
            rad = random.uniform(40, 62) * sc * (0.55 if idx == 5 else 1.0)
            blobs.append((oval(base), base, rad, random.uniform(-22, 22) * sc,
                          random.uniform(-16, 16) * sc))
        arms = []
        n_arm = 8 if small else 12
        for idx in range(n_arm):
            ang = idx * math.tau / n_arm + random.uniform(-0.2, 0.2)
            ln = line(color, 7 * sc)
            arms.append((ln, oval(color), ang, random.uniform(80, 150) * sc,
                         random.uniform(6, 14) * sc))
        drips = []
        for idx in range(4):
            drips.append((line(color, 5 * sc), oval(color), random.uniform(-48, 48) * sc,
                          random.uniform(28, 60) * sc, random.uniform(0.2, 0.4)))
        spray = []
        for idx in range(10 if small else 18):
            a = random.random() * math.tau
            spd = random.uniform(80, 220) * sc
            spray.append((oval(light if idx % 3 == 0 else color), math.cos(a) * spd,
                          math.sin(a) * spd, random.uniform(2.5, 5) * sc))
        splash_items = ([b[0] for b in blobs] + [i for a_ in arms for i in a_[:2]]
                        + [i for d_ in drips for i in d_[:2]] + [s_[0] for s_ in spray])
        self._fx_vis(splash_items, False)
        state = dict(shown=False)

        def ease(v):
            v = max(0.0, min(1.0, v))
            return 1 - (1 - v) ** 3

        def up(p, e):
            tt = p * dur
            s = max(0.0, (tt - lead) / post)
            fade = max(0.0, (s - 0.7) / 0.3)

            def fc(c):
                return lerp_color(c, BG, fade)

            if pal:                                           # 팔레트 등장 + 던지는 손짓
                appear = min(1.0, tt / 0.1)
                vis = tt < lead + 0.08
                jx = math.sin(tt * 40) * 3 if 0.05 < tt < lead else 0.0
                cv.coords(pal[0], pcx + jx - 36 * appear, pcy - 23 * appear,
                          pcx + jx + 36 * appear, pcy + 23 * appear)
                cv.coords(pal[1], pcx + jx - 15 - 4 * appear, pcy + 5 - 4 * appear,
                          pcx + jx - 15 + 4 * appear, pcy + 5 + 4 * appear)
                for di, dab in enumerate(pal[2:]):
                    ox, oy = dab_off[di]
                    r = (9 if di == used else 6) * appear
                    cv.coords(dab, pcx + jx + ox - r, pcy + oy - r, pcx + jx + ox + r, pcy + oy + r)
                self._fx_vis(pal, vis)
            for it, s0, s1, lx, ly, r in drops:                # 포물선으로 날아가는 물감
                u = (tt - s0) / max(0.05, s1 - s0)
                if 0.0 < u < 1.0:
                    mx, my = (pcx + lx) / 2, min(pcy, ly) - 130
                    bx = (1 - u) ** 2 * pcx + 2 * (1 - u) * u * mx + u * u * lx
                    by = (1 - u) ** 2 * pcy + 2 * (1 - u) * u * my + u * u * ly
                    cv.coords(it, bx - r, by - r, bx + r, by + r)
                    cv.itemconfig(it, state="normal")
                else:
                    cv.itemconfig(it, state="hidden")
            if s <= 0:
                return
            if not state["shown"]:
                state["shown"] = True
                self._fx_vis(splash_items, True)
            e1 = ease(s * 2.4)
            for it, base, rad, ox, oy in blobs:
                r = rad * e1
                bx, by = tx + ox * e1, ty + oy * e1
                cv.coords(it, bx - r, by - r * 0.82, bx + r, by + r * 0.82)
                cv.itemconfig(it, fill=fc(base))
            e2 = ease(s * 2.0)
            for ln, end, ang, reach, rr in arms:
                ex, ey = tx + math.cos(ang) * reach * e2, ty + math.sin(ang) * reach * e2 * 0.85
                r = rr * (0.6 + 0.4 * e2) * (1 - 0.3 * s)
                cv.coords(ln, tx, ty, ex, ey)
                cv.coords(end, ex - r, ey - r, ex + r, ey + r)
                cv.itemconfig(ln, fill=fc(color), width=max(1, 7 * sc * (1 - 0.5 * e2)))
                cv.itemconfig(end, fill=fc(color))
            for ln, end, dx, dlen, d0 in drips:
                length = dlen * max(0.0, min(1.0, (s - d0) / 0.5))
                if length > 1:
                    y0 = ty + 14 * sc
                    cv.coords(ln, tx + dx, y0, tx + dx, y0 + length)
                    cv.coords(end, tx + dx - 5 * sc, y0 + length - 3, tx + dx + 5 * sc, y0 + length + 7)
                    cv.itemconfig(ln, state="normal", fill=fc(color))
                    cv.itemconfig(end, state="normal", fill=fc(color))
                else:
                    cv.itemconfig(ln, state="hidden")
                    cv.itemconfig(end, state="hidden")
            for it, vx, vy, r in spray:
                px, py = tx + vx * s * 0.7, ty + vy * s * 0.7 + 120 * s * s
                rr = r * (1 - 0.6 * s)
                cv.coords(it, px - rr, py - rr, px + rr, py + rr)
                cv.itemconfig(it, fill=fc(color))

        self.add_fx(items, dur, up)

        def impact():
            self.fx_flash(uid, color, "gray25")
            self.shakes[uid] = 0.25
            beep([(220, 40), (160, 70)], self.sound)

        if lead > 0:
            self.root.after(int(lead * 1000), impact)
        else:
            impact()

    def fx_paint_burst3(self, uid):
        """화가 N — 강화된 트리플 아틀리에: 3색 오브가 소용돌이치다 한꺼번에 터진다."""
        cv = self.canvas
        tx, ty = self.center_of(uid)
        dur = 1.3
        t_boom = 0.58
        cols = [PAINT_BLUE, PAINT_RED, PAINT_GREEN]
        angs = [math.radians(a) for a in (200, 340, 90)]
        items = []

        def oval(fill="", outline="", **kw):
            it = cv.create_oval(tx, ty, tx, ty, fill=fill, outline=outline, tags="fx", **kw)
            items.append(it)
            return it

        def line(col, width):
            it = cv.create_line(tx, ty, tx, ty, fill=col, width=width, capstyle="round", tags="fx")
            items.append(it)
            return it

        charge = oval("", WHITE, width=2)
        orbs = []
        for i, c in enumerate(cols):
            ghosts = [oval(lerp_color(c, BG, 0.62)), oval(lerp_color(c, BG, 0.35))]
            orbs.append((oval(c, WHITE, width=2), ghosts, c, i))
        sectors = []
        boom_items = []
        for i, c in enumerate(cols):
            blob = oval(c, "", stipple="gray50")
            ring = oval("", c, width=6)
            rays = []
            for j in range(8):
                a = angs[i] + (j - 3.5) * math.radians(13) + random.uniform(-0.05, 0.05)
                rays.append((line(c, 6), oval(c), a, random.uniform(150, 260)))
            parts = []
            for j in range(8):
                a = angs[i] + random.uniform(-0.9, 0.9)
                spd = random.uniform(120, 260)
                parts.append((oval(c), math.cos(a) * spd, math.sin(a) * spd, random.uniform(3, 6)))
            sectors.append((c, angs[i], blob, ring, rays, parts))
            boom_items += [blob, ring] + [r_[0] for r_ in rays] + [r_[1] for r_ in rays] \
                + [p_[0] for p_ in parts]
        self._fx_vis(boom_items, False)
        state = dict(boom=False)

        def up(p, e):
            tt = p * dur
            fade = max(0.0, (p - 0.82) / 0.18)
            if tt < t_boom:                                   # 충전: 3색 오브가 소용돌이치며 모인다
                s1 = tt / t_boom
                R = 150 * (1 - s1 ** 1.6) + 6
                spin = tt * 11
                for main, ghosts, c, i in orbs:
                    a = i * math.tau / 3 + spin
                    for gh, dlt in zip(ghosts, (0.5, 0.25)):
                        gx, gy = tx + math.cos(a - dlt) * R, ty + math.sin(a - dlt) * R * 0.8
                        cv.coords(gh, gx - 8, gy - 8, gx + 8, gy + 8)
                    mx, my = tx + math.cos(a) * R, ty + math.sin(a) * R * 0.8
                    cv.coords(main, mx - 13, my - 13, mx + 13, my + 13)
                cr = 160 * (1 - s1) + 8
                cv.coords(charge, tx - cr, ty - cr * 0.8, tx + cr, ty + cr * 0.8)
                cv.itemconfig(charge, outline=lerp_color(BG, WHITE, s1))
                return
            if not state["boom"]:
                state["boom"] = True
                self._fx_vis([charge] + [o[0] for o in orbs]
                             + [g for o in orbs for g in o[1]], False)
                self._fx_vis(boom_items, True)
            s = (tt - t_boom) / (dur - t_boom)
            eb = 1 - (1 - min(1.0, s * 2.2)) ** 3
            for c, a0, blob, ring, rays, parts in sectors:
                fc = lerp_color(c, BG, fade)
                bx, by = tx + math.cos(a0) * 50 * eb, ty + math.sin(a0) * 40 * eb
                rb = 120 * eb
                cv.coords(blob, bx - rb, by - rb * 0.8, bx + rb, by + rb * 0.8)
                cv.itemconfig(blob, fill=fc)
                rr = 40 + 230 * eb
                cv.coords(ring, tx - rr, ty - rr * 0.8, tx + rr, ty + rr * 0.8)
                cv.itemconfig(ring, outline=fc, width=max(1, 6 - 5 * s))
                for ln, end, a, reach in rays:
                    r0, r1 = 30 * eb, reach * eb
                    ex, ey = tx + math.cos(a) * r1, ty + math.sin(a) * r1 * 0.85
                    cv.coords(ln, tx + math.cos(a) * r0, ty + math.sin(a) * r0 * 0.85, ex, ey)
                    er = 8 * (1 - 0.5 * s)
                    cv.coords(end, ex - er, ey - er, ex + er, ey + er)
                    cv.itemconfig(ln, fill=fc)
                    cv.itemconfig(end, fill=fc)
                for it, vx, vy, r in parts:
                    px, py = tx + vx * s * 0.8, ty + vy * s * 0.8 + 130 * s * s
                    rp = r * (1 - 0.6 * s)
                    cv.coords(it, px - rp, py - rp, px + rp, py + rp)
                    cv.itemconfig(it, fill=fc)

        self.add_fx(items, dur, up)

        def boom():
            self.fx_flash(uid, WHITE, "gray50")
            for c in cols:
                self.fx_flash(uid, c, "gray25")
            self.shakes[uid] = 0.6
            beep([(300, 60), (520, 70), (880, 120)], self.sound)

        self.root.after(int(t_boom * 1000), boom)
        beep([(330, 40), (440, 40), (550, 50)], self.sound)

    # ================================================================
    # Fate Lost/C 이펙트 (fate fx 패치)
    # ================================================================
    def _fx_poly_slice(self, pts, a, b):
        """꺾은선 pts 의 비율 구간 [a, b] 를 평면 좌표 리스트로 돌려준다. 너무 짧으면 None."""
        n = len(pts) - 1
        a, b = max(0.0, a), min(1.0, b)
        if b - a < 0.01:
            return None

        def at(q):
            f = q * n
            i = min(n - 1, int(f))
            r = f - i
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            return x0 + (x1 - x0) * r, y0 + (y1 - y0) * r

        out = [at(a)]
        for i in range(int(a * n) + 1, int(b * n) + 1):
            if a * n < i < b * n:
                out.append(pts[i])
        out.append(at(b))
        flat = []
        for px, py in out:
            flat.extend((px, py))
        return flat

    def _fx_poly_point(self, pts, q):
        n = len(pts) - 1
        f = max(0.0, min(1.0, q)) * n
        i = min(n - 1, int(f))
        r = f - i
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        return x0 + (x1 - x0) * r, y0 + (y1 - y0) * r

    def fx_fate_upslash(self, uid):
        """그려내기 — 아래에서 위로 베어 올리는 올려베기. 핑크/하양 잔향과 떠오르는 빛 조각."""
        cv = self.canvas
        cx, cy = self.center_of(uid)
        PINK = STAR_COLOR[3]
        LIGHT = lerp_color(PINK, WHITE, 0.6)
        P0, P1, P2 = (cx - 62, cy + 98), (cx + 78, cy + 34), (cx + 36, cy - 108)
        N = 20
        path = []
        for i in range(N + 1):
            q = i / float(N)
            path.append(((1 - q) ** 2 * P0[0] + 2 * (1 - q) * q * P1[0] + q * q * P2[0],
                         (1 - q) ** 2 * P0[1] + 2 * (1 - q) * q * P1[1] + q * q * P2[1]))
        dur, t_sweep = 0.95, 0.3

        def mk_line(col, width):
            return cv.create_line(cx, cy, cx, cy, fill=col, width=width, capstyle="round",
                                  smooth=True, state="hidden", tags="fx")

        layers = [(mk_line(c, wd), ln, wd, c) for ln, wd, c in
                  ((0.75, 24, lerp_color(PINK, BG, 0.45)), (0.55, 13, PINK),
                   (0.42, 7, LIGHT), (0.3, 3, WHITE))]
        ghosts = []
        for dx, dy, wd, col, d0 in ((-14, 14, 6, LIGHT, 0.0), (-30, 28, 4, PINK, 0.06),
                                    (-48, 42, 3, lerp_color(PINK, BG, 0.4), 0.12)):
            ghosts.append((mk_line(col, wd), [(px + dx, py + dy) for px, py in path], col, d0))
        sparks = []
        for j in range(16):
            idx = random.randint(3, N)
            px, py = path[idx]
            poly = cv.create_polygon(cx, cy, cx, cy, cx, cy, cx, cy,
                                     fill=WHITE if j % 2 else LIGHT, outline="",
                                     state="hidden", tags="fx")
            sparks.append((poly, idx / float(N) * t_sweep, px, py, random.uniform(-26, 26),
                           random.uniform(70, 120), random.uniform(3.5, 6.5), WHITE if j % 2 else LIGHT))
        head = cv.create_oval(cx, cy, cx, cy, fill=WHITE, outline=PINK, width=2,
                              state="hidden", tags="fx")
        ring = cv.create_oval(cx, cy, cx, cy, outline=WHITE, width=3, state="hidden", tags="fx")
        items = ([l[0] for l in layers] + [g[0] for g in ghosts] + [s[0] for s in sparks]
                 + [head, ring])

        def up(p, e):
            tt = p * dur
            hq = min(1.0, tt / t_sweep)
            for ln, L, wd, col in layers:
                if tt <= t_sweep:
                    tail = max(0.0, hq - L)
                else:
                    tail = (1 - L) + L * min(1.0, (tt - t_sweep) / 0.22)
                seg = self._fx_poly_slice(path, tail, hq)
                if seg:
                    cv.coords(ln, *seg)
                    cv.itemconfig(ln, state="normal")
                else:
                    cv.itemconfig(ln, state="hidden")
            for ln, gpath, col, d0 in ghosts:           # 잔향 — 천천히 사라지는 핑크/하양 호
                a = tt - 0.1 - d0
                seg = self._fx_poly_slice(gpath, 0.0, min(1.0, hq)) if a > 0 else None
                if seg:
                    cv.coords(ln, *seg)
                    cv.itemconfig(ln, state="normal", fill=lerp_color(col, BG, min(1.0, a / 0.6)))
                else:
                    cv.itemconfig(ln, state="hidden")
            for poly, ts, px, py, sway, rise, size, col in sparks:   # 떠오르는 빛 조각
                s = (tt - ts) / 0.6
                if 0.0 < s < 1.0:
                    sx, sy = px + sway * s, py - rise * s
                    r = size * (1 - 0.6 * s)
                    cv.coords(poly, sx, sy - r, sx + r * 0.6, sy, sx, sy + r, sx - r * 0.6, sy)
                    cv.itemconfig(poly, state="normal", fill=lerp_color(col, BG, s * s))
                else:
                    cv.itemconfig(poly, state="hidden")
            if tt < t_sweep + 0.04:
                hx, hy = self._fx_poly_point(path, hq)
                cv.coords(head, hx - 9, hy - 9, hx + 9, hy + 9)
                cv.itemconfig(head, state="normal")
            else:
                cv.itemconfig(head, state="hidden")
            rs = (tt - t_sweep) / 0.35
            if 0.0 < rs < 1.0:
                r = 12 + 70 * rs
                cv.coords(ring, P2[0] - r, P2[1] - r, P2[0] + r, P2[1] + r)
                cv.itemconfig(ring, state="normal", outline=lerp_color(WHITE, BG, rs), width=max(1, 4 - 3 * rs))
            else:
                cv.itemconfig(ring, state="hidden")

        self.add_fx(items, dur / 1.5, up)   # 속도패치
        self.root.after(int(t_sweep * 700 / 1.5), lambda: (self.fx_flash(uid, PINK, "gray50"),
                                                    self.fx_particles(uid, LIGHT, n=14, spread=110,
                                                                      dur=0.5, size=4)))
        self.shakes[uid] = 0.3
        beep([(520, 30), (880, 40), (1320, 60)], self.sound)

    def fx_fate_sweep(self, uid, all_ids):
        """휩쓸기 — 지정 대상을 중심으로 좌우 넓은 범위를 휩쓸어 지나가는 대형 참격."""
        cv = self.canvas
        tx, ty = self.center_of(uid)
        PINK = STAR_COLOR[3]
        LIGHT = lerp_color(PINK, WHITE, 0.6)
        xL, xR = max(30.0, tx - 400), min(WIN_W - 30.0, tx + 400)
        N = 30
        path = []
        for i in range(N + 1):
            q = i / float(N)
            path.append((xL + (xR - xL) * q,
                         ty + 28 - 66 * math.sin(math.pi * q) + (q - 0.5) * 26))
        dur, t_sweep = 0.85, 0.38

        def mk_line(col, width):
            return cv.create_line(tx, ty, tx, ty, fill=col, width=width, capstyle="round",
                                  smooth=True, state="hidden", tags="fx")

        layers = [(mk_line(c, wd), ln, c) for ln, wd, c in
                  ((0.8, 30, lerp_color(PINK, BG, 0.5)), (0.6, 17, PINK),
                   (0.45, 9, LIGHT), (0.3, 4, WHITE))]
        ghosts = [(mk_line(col, 3), [(px, py + dy) for px, py in path], col)
                  for dy, col in ((-24, LIGHT), (24, PINK))]
        wind = []
        for j in range(12):
            xs = random.uniform(xL, xR)
            wind.append((cv.create_line(tx, ty, tx, ty, fill=LIGHT, width=2, state="hidden", tags="fx"),
                         xs, ty + random.uniform(-95, 95), random.uniform(60, 160),
                         (xs - xL) / max(1.0, xR - xL) * t_sweep))
        glow = cv.create_oval(tx, ty, tx, ty, fill=lerp_color(PINK, BG, 0.4), outline="",
                              stipple="gray50", state="hidden", tags="fx")
        head = cv.create_oval(tx, ty, tx, ty, fill=WHITE, outline="", state="hidden", tags="fx")
        items = [l[0] for l in layers] + [g[0] for g in ghosts] + [w_[0] for w_ in wind] + [glow, head]

        def up(p, e):
            tt = p * dur
            hq = min(1.0, tt / t_sweep)
            for ln, L, col in layers:
                if tt <= t_sweep:
                    tail = max(0.0, hq - L)
                else:
                    tail = (1 - L) + L * min(1.0, (tt - t_sweep) / 0.32)
                seg = self._fx_poly_slice(path, tail, hq)
                if seg:
                    cv.coords(ln, *seg)
                    cv.itemconfig(ln, state="normal")
                else:
                    cv.itemconfig(ln, state="hidden")
            for ln, gpath, col in ghosts:                   # 휩쓸고 지나간 자리의 잔상
                a = tt - 0.12
                seg = self._fx_poly_slice(gpath, 0.0, hq) if a > 0 else None
                if seg:
                    cv.coords(ln, *seg)
                    cv.itemconfig(ln, state="normal", fill=lerp_color(col, BG, min(1.0, a / 0.6)))
                else:
                    cv.itemconfig(ln, state="hidden")
            for ln, xs, wy, wl, ts in wind:                 # 바람줄
                pr = (tt - ts) / 0.3
                if 0.0 < pr < 1.0:
                    x1 = xs + 120 * pr
                    cv.coords(ln, x1, wy, x1 + wl * (1 - 0.5 * pr), wy)
                    cv.itemconfig(ln, state="normal", fill=lerp_color(LIGHT, BG, pr))
                else:
                    cv.itemconfig(ln, state="hidden")
            if tt < t_sweep + 0.05:
                hx, hy = self._fx_poly_point(path, hq)
                cv.coords(glow, hx - 26, hy - 26, hx + 26, hy + 26)
                cv.coords(head, hx - 9, hy - 9, hx + 9, hy + 9)
                cv.itemconfig(glow, state="normal")
                cv.itemconfig(head, state="normal")
            else:
                cv.itemconfig(glow, state="hidden")
                cv.itemconfig(head, state="hidden")

        self.add_fx(items, dur / 1.5, up)   # 속도패치
        for tid in all_ids:                                 # 검기가 지나가는 순간 각 적이 반응한다
            cxi = self.center_of(tid)[0]
            frac = max(0.0, min(1.0, (cxi - xL) / max(1.0, xR - xL)))

            def hit(tid=tid):
                self.fx_flash(tid, PINK, "gray50")
                self.fx_particles(tid, LIGHT, n=14, spread=110, dur=0.5, size=4)
                self.shakes[tid] = 0.35

            self.root.after(int(t_sweep * frac * 1000 / 1.5), hit)
        beep([(300, 40), (500, 50), (800, 80)], self.sound)

    def fx_fate_memories(self, src_uid, target_ids):
        """운명 — C 주위로 기억의 조각이 스치다 사라지고, 근처를 무작위로 베어낸다."""
        cv = self.canvas
        x, y, w, h = self.rect_of(src_uid)
        cx, cy = x + w / 2, y + h / 2
        PINK = STAR_COLOR[3]
        PALE = lerp_color(PINK, WHITE, 0.65)
        DEEP = "#3A1A3F"
        dur, t_vanish = 1.3, 0.95
        items = []

        frames = []
        for i in range(6):
            poly = cv.create_polygon(cx, cy, cx, cy, cx, cy, cx, cy, fill=BG, outline=BG,
                                     width=2, stipple="gray25", tags="fx")
            l1 = cv.create_line(cx, cy, cx, cy, fill=BG, width=2, tags="fx")
            l2 = cv.create_line(cx, cy, cx, cy, fill=BG, width=2, tags="fx")
            items += [poly, l1, l2]
            rxx = random.uniform(95, 165)
            frames.append(dict(poly=poly, l1=l1, l2=l2, ang=i * math.tau / 6 + random.uniform(-0.3, 0.3),
                               rx=rxx, ry=rxx * 0.62, fw=random.uniform(30, 48), fh=random.uniform(40, 62),
                               rot=random.uniform(-0.6, 0.6), ph=random.uniform(0, 6.28),
                               dr=random.choice((-1, 1)), i=i))
        ghosts = []
        for sgn in (-1, 1):
            it = cv.create_rectangle(cx, cy, cx, cy, outline=BG, width=2, tags="fx")
            items.append(it)
            ghosts.append((it, sgn))
        motes = []
        for j in range(22):
            it = cv.create_oval(cx, cy, cx, cy, fill=BG, outline="", tags="fx")
            items.append(it)
            motes.append((it, random.uniform(0, 6.28), random.uniform(60, 170),
                          random.uniform(0.5, 1.4) * random.choice((-1, 1)), random.uniform(2, 4.2),
                          random.uniform(0, 6.28)))
        rings = []
        for j in range(2):
            it = cv.create_oval(cx, cy, cx, cy, outline=BG, width=2, tags="fx")
            items.append(it)
            rings.append(it)

        def up(p, e):
            tt = p * dur
            if tt > t_vanish:
                v = max(0.0, 1.0 - (tt - t_vanish) / (dur - t_vanish))
                pull = 0.35 + 0.65 * v
            else:
                v, pull = 1.0, 1.0
            for f in frames:
                ap = min(1.0, max(0.0, (tt - 0.08 * f["i"]) / 0.3))
                flick = 0.55 + 0.45 * abs(math.sin(tt * 3.2 + f["ph"]))
                a = ap * flick * v
                ang = f["ang"] + tt * 0.5 * f["dr"]
                px = cx + math.cos(ang) * f["rx"] * pull
                py = cy + math.sin(ang) * f["ry"] * pull + math.sin(tt * 2 + f["ph"]) * 8
                th = f["rot"] + math.sin(tt * 1.7 + f["ph"]) * 0.35
                c_, s_ = math.cos(th), math.sin(th)
                fw, fh = f["fw"], f["fh"]

                def tr(lx, ly):
                    return px + lx * c_ - ly * s_, py + lx * s_ + ly * c_

                pts = []
                for lx, ly in ((-fw, -fh), (fw, -fh), (fw, fh), (-fw, fh)):
                    pts.extend(tr(lx, ly))
                cv.coords(f["poly"], *pts)
                cv.itemconfig(f["poly"], outline=lerp_color(BG, PALE, a), fill=lerp_color(BG, DEEP, a * 0.9))
                cv.coords(f["l1"], *(tr(-fw * 0.5, -fh * 0.35) + tr(fw * 0.5, -fh * 0.35)))
                cv.coords(f["l2"], *(tr(-fw * 0.5, fh * 0.05) + tr(fw * 0.1, fh * 0.05)))
                cv.itemconfig(f["l1"], fill=lerp_color(BG, PINK, a))
                cv.itemconfig(f["l2"], fill=lerp_color(BG, PINK, a))
            for it, sgn in ghosts:                          # C 의 잔상
                a = (0.35 + 0.65 * abs(math.sin(tt * 4 + sgn))) * min(1.0, tt / 0.3) * v * 0.7
                off = sgn * (12 + 6 * math.sin(tt * 3))
                cv.coords(it, x + off, y + 6 * sgn, x + w + off, y + h + 6 * sgn)
                cv.itemconfig(it, outline=lerp_color(BG, PALE if sgn > 0 else PINK, a))
            for it, a0, r0, spd, size, ph in motes:         # 떠도는 기억 입자
                ang = a0 + tt * spd
                rad = r0 * pull + 10 * math.sin(tt * 2 + ph)
                mx, my = cx + math.cos(ang) * rad * 1.2, cy + math.sin(ang) * rad * 0.75
                a = min(1.0, tt / 0.3) * v * (0.5 + 0.5 * math.sin(tt * 5 + ph))
                cv.coords(it, mx - size, my - size, mx + size, my + size)
                cv.itemconfig(it, fill=lerp_color(BG, WHITE if size > 3 else PINK, a))
            for j, it in enumerate(rings):
                q = (tt * 0.8 + j * 0.5) % 1.0
                r = 30 + 130 * q
                cv.coords(it, cx - r, cy - r * 0.6, cx + r, cy + r * 0.6)
                cv.itemconfig(it, outline=lerp_color(BG, PINK, (1 - q) * 0.5 * v))

        self.add_fx(items, dur, up)
        beep([(700, 40), (880, 50), (1046, 70)], self.sound)
        self.root.after(int(t_vanish * 1000), lambda: self.fx_flash(src_uid, WHITE, "gray25"))

        # 기억이 사라진 뒤 — 근처를 무작위로 베어낸다
        t0 = 1250
        for i in range(18):
            if target_ids and i % 2 == 0:
                tid = target_ids[(i // 2) % len(target_ids)]
                rx, ry, rw, rh = self.rect_of(tid)
                px = rx + random.uniform(0.12, 0.88) * rw
                py = ry + random.uniform(0.1, 0.9) * rh
            else:
                tid = None
                a = random.random() * math.tau
                rad = random.uniform(30, 170)
                px, py = cx + math.cos(a) * rad * 1.3, cy + math.sin(a) * rad * 0.8
            half = random.uniform(80, 130)
            ang = random.uniform(-75, 75)
            col = PINK if i % 3 else lerp_color(PINK, WHITE, 0.6)

            def slash(px=px, py=py, half=half, ang=ang, col=col, tid=tid, i=i):
                self._one_slash(px - half, py - half, half * 2, half * 2, ang, col)
                if tid is not None:
                    self.fx_flash(tid, PINK, "gray25")
                    self.shakes[tid] = 0.2
                if i % 3 == 0:
                    beep([(random.randint(500, 900), 22)], self.sound)

            self.root.after(t0 + i * 38, slash)

    # 보스 광역기 — 차원 붕괴
    def fx_cosmic(self):
        cx, cy = WIN_W / 2, ENEMY_Y + CARD_H
        rings = [self.canvas.create_oval(cx, cy, cx, cy, outline=COSMIC, width=4, tags="fx")
                 for _ in range(3)]
        veil = self.canvas.create_rectangle(0, 0, WIN_W, WIN_H, fill=COSMIC, outline="",
                                            stipple="gray25", tags="fx")

        def up(p, e):
            for i, it in enumerate(rings):
                q = max(0.0, min(1.0, p * 1.5 - i * 0.2))
                r = 30 + 980 * q
                self.canvas.coords(it, cx - r, cy - r * 0.55, cx + r, cy + r * 0.55)
                self.canvas.itemconfig(it, outline=lerp_color(COSMIC, BG, q),
                                       width=max(1, 5 - 4 * q))
            self.canvas.itemconfig(veil, stipple="gray25" if p < 0.25 else "gray12")

        self.add_fx(rings + [veil], 0.9, up)
        for a in self.allies():
            if a.alive:
                self.fx_flash(a.id, COSMIC, "gray50")
                self.shakes[a.id] = 0.4

    # C 3스킬 — 파멸의 예연 (저주)
    def fx_curse(self, uid):
        cx, cy = self.center_of(uid)
        ring = self.canvas.create_oval(cx - 10, cy - 10, cx + 10, cy + 10,
                                       outline=CURSE, width=3, tags="fx")
        ring2 = self.canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4,
                                        outline=CURSE, width=2, tags="fx")

        def up(p, e):
            r = 10 + 70 * p
            r2 = 4 + 90 * min(1.0, p * 1.3)
            self.canvas.coords(ring, cx - r, cy - r, cx + r, cy + r)
            self.canvas.coords(ring2, cx - r2, cy - r2, cx + r2, cy + r2)
            self.canvas.itemconfig(ring, outline=lerp_color(CURSE, BG, p), width=max(1, 4 - 3 * p))
            self.canvas.itemconfig(ring2, outline=lerp_color(CURSE, BG, min(1, p * 1.3)))

        self.add_fx([ring, ring2], 0.55, up)
        self.fx_particles(uid, CURSE, n=18, spread=95, dur=0.6, size=4)
        self.fx_flash(uid, CURSE, "gray50")
        self.fx_number(uid, "저주!", CURSE, 20)
        self.shakes[uid] = 0.28

    # N 3스킬 — 조준경 락온 후 장거리 저격 (색상은 스킬별로 전달됨)
    def fx_snipe(self, uid, cb, color=SPC):
        cx, cy = self.center_of(uid)
        ring = self.canvas.create_oval(cx - 110, cy - 110, cx + 110, cy + 110,
                                       outline=color, width=2, tags="fx")
        inner = self.canvas.create_oval(cx - 60, cy - 60, cx + 60, cy + 60,
                                        outline=color, width=1, tags="fx")
        hline = self.canvas.create_line(cx - 130, cy, cx + 130, cy, fill=color, width=1, tags="fx")
        vline = self.canvas.create_line(cx, cy - 130, cx, cy + 130, fill=color, width=1, tags="fx")

        def up(p, e):
            r = 110 - 80 * p
            self.canvas.coords(ring, cx - r, cy - r, cx + r, cy + r)
            r2 = max(6, 60 - 48 * p)
            self.canvas.coords(inner, cx - r2, cy - r2, cx + r2, cy + r2)
            self.canvas.itemconfig(ring, outline=lerp_color(color, WHITE, p), width=1 + 2 * p)

        self.add_fx([ring, inner, hline, vline], 0.72, up)
        beep([(1200, 40), (1400, 40), (1600, 60)], self.sound)
        self.root.after(740, lambda: self._snipe_shot(uid, cb, color))

    def _snipe_shot(self, uid, cb, color=SPC):
        x, y, w, h = self.rect_of(uid)
        cx, cy = self.center_of(uid)
        beam = self.canvas.create_line(0, cy, 0, cy, fill=WHITE, width=6, tags="fx")
        halo = self.canvas.create_line(0, cy, 0, cy, fill=color, width=14, tags="fx")

        def up(p, e):
            head = WIN_W * min(1.0, p * 3.2)
            for it in (halo, beam):
                self.canvas.coords(it, 0, cy, head, cy)
            self.canvas.itemconfig(beam, fill=lerp_color(WHITE, BG, max(0, (p - 0.4) / 0.6)))
            self.canvas.itemconfig(halo, fill=lerp_color(color, BG, p),
                                   width=max(1, 14 - 12 * p))

        self.add_fx([halo, beam], 0.38, up)
        self.fx_heavy(uid)
        self.shakes[uid] = 0.45
        beep([(180, 60), (90, 120)], self.sound)
        self.root.after(260, cb)

    # H 3스킬 — 난격 (색상은 스킬별로 전달됨)
    def fx_frenzy(self, uid, cb, n=10, color=DMG):
        x, y, w, h = self.rect_of(uid)
        for i in range(n):
            def one(_=None):
                self._one_slash(x, y, w, h, random.uniform(-70, 25), color)
                self.fx_particles(uid, color, n=5, spread=60, dur=0.3, size=3)
                self.shakes[uid] = 0.18
                beep([(random.randint(150, 260), 22)], self.sound)

            self.root.after(int(70 * i), one)

        def finale():
            self.fx_heavy(uid)
            self._one_slash(x, y, w, h, -80, color)
            self.fx_flash(uid, WHITE, "gray50")
            self.shakes[uid] = 0.5
            beep([(200, 70), (110, 140)], self.sound)

        self.root.after(70 * n + 60, finale)
        self.root.after(70 * n + 340, cb)

    # ================================================================
    # 렌더링
    # ================================================================
    def tick(self):
        dt = 0.016
        self.active_blink_timer += dt
        if self.active_blink_timer >= 0.6:
            self.active_blink_timer -= 0.6
            self.active_blink_on = not self.active_blink_on
            if self.acting and not self.game_over:
                self.render()

        for e in list(self.effects):
            e["t"] += dt
            p = min(1.0, e["t"] / e["dur"])
            if e["update"]:
                try:
                    e["update"](p, e)
                except tk.TclError:
                    pass
            if e["t"] >= e["dur"]:
                for it in e["items"]:
                    try:
                        self.canvas.delete(it)
                    except tk.TclError:
                        pass
                self.effects.remove(e)

        if self.shakes:
            for k in list(self.shakes):
                self.shakes[k] -= dt
                if self.shakes[k] <= 0:
                    del self.shakes[k]
            self.render()

        if self.codex_open and self.codex_page == "workshop":
            self._ws_acc = self.__dict__.get("_ws_acc", 0.0) + dt
            if self._ws_acc >= 0.04:
                self._ws_acc = 0.0
                self.render()
        else:
            self._ws_since = None          # 닫히면 다음에 열 때 연출을 처음부터
            self._ws_ui = True
            self._ws_ui_since = None
        if (not self.lobby and self.__dict__.get("units")
                and any(self.is_orch(_ou) and _ou.orch_ring > 0 for _ou in self.units.values())):
            self._orch_acc = self.__dict__.get("_orch_acc", 0.0) + dt      # 악장의 원 회전 애니메이션
            if self._orch_acc >= 0.05:
                self._orch_acc = 0.0
                self.render()
        if self.lobby and not (self.gacha_open or self.codex_open or self.modal):
            self._lobby_acc = self.__dict__.get("_lobby_acc", 0.0) + dt
            if self._lobby_acc >= 0.05:
                self._lobby_acc = 0.0
                self.render()

        self.root.after(16, self.tick)

    def font(self, size, mono=False, bold=False):
        """size는 픽셀 높이. 음수 size로 만들면 DPI 배율과 무관하게 크기가 고정된다."""
        key = (size, mono, bold)
        if key not in self._font_cache:
            self._font_cache[key] = tkfont.Font(
                family=self.fm if mono else self.ff, size=-size,
                weight="bold" if bold else "normal")
        return self._font_cache[key]

    def txt(self, x, y, text, size=13, color=TXT, mono=False, anchor="nw", bold=False):
        return self.canvas.create_text(x, y, text=text, fill=color,
                                       font=self.font(size, mono, bold),
                                       anchor=anchor, tags="ui")

    def wtxt(self, x, y, width, text, size=12, color=TXT, mono=False, anchor="nw", bold=False,
             justify="left"):
        return self.canvas.create_text(x, y, text=text, fill=color,
                                       font=self.font(size, mono, bold),
                                       anchor=anchor, width=width, justify=justify, tags="ui")

    def bar(self, x, y, w, h, ratio, color):
        self.canvas.create_rectangle(x, y, x + w, y + h, fill=PANEL2, outline=BRD, tags="ui")
        ratio = max(0.0, min(1.0, ratio))
        if ratio > 0:
            self.canvas.create_rectangle(x + 1, y + 1, x + 1 + (w - 2) * ratio, y + h - 1,
                                         fill=color, outline="", tags="ui")

    def render(self):
        theme = theme_of(self.phase)
        try:
            self.canvas.configure(bg=theme["bg"])
        except tk.TclError:
            pass
        self.canvas.delete("ui")
        self.buttons = []
        if self.lobby:
            self.render_lobby()
            self.render_gacha()
            self.render_codex()
            self.render_inventory()
            self.render_formation()
            self.canvas.tag_raise("fx")
            return

        # 헤더 — 로고 폭을 실제로 측정해서 뒤 문구를 배치한다
        self.txt(MARGIN, 24, "NHC", 30, TXT, bold=True, anchor="w")
        logo_w = self.font(30, bold=True).measure("NHC")
        self.txt(MARGIN + logo_w + 12, 25, "전투 프로토타입", 23, DMG, anchor="w")
        self.txt(WIN_W - MARGIN, 10, "STAGE %d · PHASE %d   ROUND %d"
                 % (stage_of(self.phase), self.phase, self.round),
                 13, theme["accent"], mono=True, anchor="ne")
        w2 = self.hbtn(WIN_W - MARGIN, 32, None, 24, "전투 종료", self.quit_battle, MUT,
                       anchor="ne")
        self.hbtn(WIN_W - MARGIN - w2 - 8, 32, None, 24,
                  "효과음 %s" % ("ON" if self.sound else "OFF"), self.toggle_sound,
                  HEAL if self.sound else MUT, anchor="ne")
        self.canvas.create_line(MARGIN, 62, WIN_W - MARGIN, 62, fill=TXT, width=2, tags="ui")

        # 획득 증강 표시
        aug_bits = []
        if self.aug_taken:
            aug_bits.append("1티어: " + " · ".join(AUG_BY_ID[i]["title"] for i in self.aug_taken))
        if self.aug_taken2:
            aug_bits.append("보스 보상: " + " · ".join(AUG2_BY_ID[i]["title"] for i in self.aug_taken2))
        if aug_bits:
            self.txt(MARGIN, 72, "증강 — " + "  /  ".join(aug_bits), 11, SPC, mono=True)

        # 카드
        self.txt(WIN_W / 2, ENEMY_Y - 20, "— B O S S —" if self.boss_mode else "— 적 —",
                 14, COSMIC if self.boss_mode else theme["accent"], mono=True, anchor="center")
        self.card_rects = {}
        if self.boss_mode:
            self.card_rects[self.enemy_ids[0]] = (MARGIN, ENEMY_Y, WIN_W - MARGIN * 2, CARD_H)
        else:
            for i, uid in enumerate(self.enemy_ids):
                x = MARGIN + i * (CARD_W + 12)
                self.card_rects[uid] = (x, ENEMY_Y, CARD_W, CARD_H)
        if self.boss_warning:
            wy = ALLY_Y - 32
            self.canvas.create_rectangle(MARGIN, wy, WIN_W - MARGIN, wy + 25, fill=COSMIC,
                                         outline="", stipple="gray50", tags="ui")
            self.canvas.create_rectangle(MARGIN, wy, WIN_W - MARGIN, wy + 25, fill="",
                                         outline=COSMIC, tags="ui")
            self.txt(WIN_W / 2, wy + 12,
                     "⚠  이상한 낌새가 느껴진다 —— [차원 붕괴] 임박 · 아군 전원 피격  ⚠",
                     14, WHITE, mono=True, anchor="center")
        else:
            self.txt(WIN_W / 2, ALLY_Y - 20, "— 아군 —", 14, MUT, mono=True, anchor="center")
        for i, uid in enumerate(self.ALLY_IDS):
            x = MARGIN + i * (CARD_W + 12)
            self.card_rects[uid] = (x, ALLY_Y, CARD_W, CARD_H)
        for uid in list(self.enemy_ids) + self.ALLY_IDS:
            if uid in self.units:
                self.render_card(self.units[uid])
        self.render_enemy_arrows()
        self.render_panel()
        self.render_log()
        self.render_tooltip()
        self.render_augment()
        self.render_overlay()
        self.render_gacha()
        self.render_codex()
        self.render_inventory()
        self.render_modal()
        self.render_admin()
        self.canvas.tag_raise("fx")

    def hbtn(self, x, y, w, h, label, cb, color, anchor="nw"):
        if w is None:
            w = self.font(12, mono=True).measure(label) + 20
        if anchor == "ne":
            x -= w
        self.canvas.create_rectangle(x, y, x + w, y + h, outline=color, fill=PANEL, tags="ui")
        self.txt(x + w / 2, y + h / 2, label, 12, color, mono=True, anchor="center")
        self.buttons.append(dict(x=x, y=y, w=w, h=h, cb=cb))
        return w

    def targetable(self, u):
        if self.admin_kill_pending:
            return u.side == "ally" and u.alive
        # 증강 '전술 재정비' 대상 지정 중에는 살아있는 아군이 대상
        if self.state == "augment_target":
            return u.side == "ally" and u.alive
        if not self.pending or self.busy:
            return False
        if self.pending["side"] != "any" and u.side != self.pending["side"]:
            return False
        return u.alive

    def render_card(self, u):
        x, y, w, h = self.card_rects[u.id]
        if u.id in self.shakes:
            mag = 7 * (self.shakes[u.id] / 0.32)
            x += random.uniform(-mag, mag)
            y += random.uniform(-mag * 0.5, mag * 0.5)

        dead = not u.alive
        tgt = self.targetable(u)
        active = (self.acting is u) and not self.game_over
        aspect = self.find_aspect(u.aspect_id)

        fill = PANEL if not dead else "#171A1F"
        outline = BRD
        width = 1
        if u.is_boss and not dead:
            outline, width = COSMIC, 2
        if aspect:
            aspect_outline = {2: "#FFD84D", 3: STAR_COLOR[3], 4: UB_RED}.get(aspect["star"])
            if aspect_outline:
                outline, width = aspect_outline, 2
        if active:
            outline = TURN_GREEN if self.active_blink_on else TURN_GREEN_DIM
            width = 3
        if tgt:
            outline, width = (SPC if self.state == "augment_target" else DMG), 2
        if self.hover == u.id and tgt:
            fill = PANEL2

        self.canvas.create_polygon(x, y, x + w, y, x + w, y + h - 12, x + w - 12, y + h,
                                   x, y + h, fill=fill, outline=outline, width=width, tags="ui")

        if self.is_orch(u) and u.orch_ring > 0 and not dead:
            self.draw_orch_ring(x, y, w, h, u.orch_ring)
        nm_color = MUT if dead else TXT
        name_f = self.font(19, bold=True)

        # 배지를 먼저 잡아서 이름이 쓸 수 있는 폭을 남긴다
        bx = x + w - 10
        badges = []
        if dead and u.immortal_turns == 0:
            badges.append(("전투불능", MUT, "#0F1216"))
        if u.is_boss and not dead:
            badges.append(("BOSS", COSMIC, "#FFFFFF"))
            if u.plans and len(u.plans) == 1 and u.plans[0]["type"] == "eaoe":
                badges.append(("차원 붕괴 예정", COSMIC, "#FFFFFF"))
        if u.broken and u.immortal_turns == 0:
            badges.append(("격파됨!", BRKC, "#FFFFFF"))
        if u.curse_turns > 0:
            badges.append(("저주 %d" % u.curse_turns, CURSE, "#FFFFFF"))
        if u.paint > 0:
            badges.append(("물감 %d" % u.paint, PAINT_RED, "#FFFFFF"))
        if u.fun_turns > 0:
            badges.append(("재미 %d" % u.fun_turns, HEAL, "#ACBD16"))
        if u.danger_turns > 0:
            badges.append(("장난 %d" % u.danger_turns, CURSE, "#8E0CD9"))
        if u.fate_turns > 0:
            badges.append(("운명 %d" % u.fate_turns, STAR_COLOR[3], "#FFFFFF"))
        if u.rib_turns > 0:
            badges.append(("늑골 %d" % u.rib_turns, MA_BONE, "#2A1C00"))
        if u.stun_turns > 0:
            badges.append(("기절 %d" % u.stun_turns, CURSE, "#FFFFFF"))
        if self.is_fate_c(u):
            if u.fate_ready:
                badges.append(("필연", STAR_COLOR[3], "#FFFFFF"))
            elif not dead:
                badges.append(("필연 %d/100" % u.fate_hp_spent, CURSE, "#FFFFFF"))
        if self.is_hero_h(u) and u.hero_buff:
            badges.append(("영웅", STAR_COLOR[3], "#FFFFFF"))
        if self.is_hero_h(u) and u.hero_echo_channel:
            badges.append(("잔상보 %d" % u.hero_echo_channel["remaining"], STAR_COLOR[3], "#FFFFFF"))
        if u.immortal_turns > 0:
            badges.append(("불사 %d" % u.immortal_turns, HEAL, "#08221D"))
        if self.is_imperial_n(u):
            if u.imperial_princess:
                badges.append(("왕녀", STAR_COLOR[3], "#FFFFFF"))
            else:
                badges.append(("기도 %d" % u.imperial_prayer, HEAL, "#08221D"))
            if u.imperial_guardian_round == self.round and not dead:
                badges.append(("수호령", STAR_COLOR[3], "#FFFFFF"))
        if self.is_underboss(u) and not dead:
            if u.ub_overheat >= 0:
                badges.append(("과열 %d/30" % u.ub_overheat, UB_RED, "#FFFFFF"))
            else:
                badges.append(("예지 %d" % u.ub_foresight, UB_RED, "#FFFFFF"))
            badges.append(("가속탄 %d" % u.ub_ammo, SPC, "#2A1C00"))
        if self.is_maestro(u) and not dead:
            badges.append(("조망 %d" % u.ma_view, UB_RED, "#FFFFFF"))
            badges.append(("생체 %d/10" % u.ma_material, MA_BONE, "#2A1C00"))
            if u.ma_masterpiece:
                badges.append(("걸작", SPC, "#2A1C00"))
        if self.is_bigsis(u) and not dead:
            badges.append(("포장 %d" % u.bs_wrap, BS_FIRE, "#2A1C00"))
            if u.bs_leva:
                badges.append(("레바테인", UB_RED, "#FFFFFF"))
            if not u.bs_leva:
                badges.append(("재미 %d" % u.bs_fun, SPC, "#2A1C00"))
        if self.is_oracle(u) and not dead:
            badges.append(("해금 %s" % OR_ROMAN[u.or_unlock], UB_RED, "#FFFFFF"))
            badges.append(("헤르메스 %d/9" % u.or_hermes, OR_GOLD, "#2A1C00"))
            if u.or_furioso:
                badges.append(("Furioso", OR_SKY, "#08221D"))
        if self.is_orch(u) and not dead:
            if u.orch_finale > 0:
                badges.append(("피날레 %d/3" % u.orch_finale_uses, ORCH_RED, "#FFFFFF"))
            badges.append(("관객 %g/%d" % (u.orch_aud, ORCH_AUD_MAX), ORCH_GOLD, "#2A1C00"))
        if u.bloom_turns > 0:
            badges.append(("개화 %d" % u.bloom_turns, ROSE, "#FFFFFF"))
        if u.side == "ally" and u.id in ULTIMATES and not dead:
            _ult = ULTIMATES[u.id]
            _ok, _why = self.ult_ready(u)
            if _ok:
                badges.append(("환상 READY", _ult["color"], "#FFFFFF"))
            elif u.ult_use_round is not None and self.round <= u.ult_use_round + ULT_COOLDOWN:
                badges.append(("환상 대기", MUT, "#0F1216"))
            else:
                badges.append(("환상 %d%%" % u.ult_gauge, _ult["color"], "#FFFFFF"))
        if u.burn > 0:
            badges.append(("화상 %d" % u.burn, BS_FIRE, "#2A1C00"))
        if u.status == "counter":
            badges.append(("반격", DMG, "#FFFFFF"))
        if u.ma_melody and not dead:
            badges.append(("선율", MA_BONE, "#2A1C00"))
        if u.shield > 0:
            badges.append(("보호막 %d" % u.shield, SHLD, "#08221D"))
        if u.focused:
            badges.append(("집중", SPC, "#2A1C00"))
        if u.speed_penalty > 0:
            badges.append(("속도 -%d" % u.speed_penalty, CURSE, "#FFFFFF"))
        if u.status == "guard":
            badges.append(("방어", HEAL, "#08221D"))
        if u.status == "evade":
            badges.append(("회피", SPC, "#2A1C00"))
        badge_f = self.font(11, mono=True)
        for label, bg, fg in badges:
            tw = badge_f.measure(label) + 12
            self.canvas.create_rectangle(bx - tw, y + 8, bx, y + 28, fill=bg, outline="",
                                         tags="ui")
            self.txt(bx - tw / 2, y + 18, label, 11, fg, mono=True, anchor="center")
            bx -= tw + 5

        # 이름 — 배지에 닿으면 잘라낸다
        avail = bx - (x + 12) - 6
        name = u.name
        while name and name_f.measure(name) > avail:
            name = name[:-1]
        if name != u.name:
            name = name[:-1] + "…"
        self.txt(x + 12, y + 8, name, 19, nm_color, bold=True)
        role_label = u.role
        if aspect:
            aspect_title = aspect["title"]
            suffix = " " + aspect["char"]
            if aspect_title.endswith(suffix):
                aspect_title = aspect_title[:-len(suffix)]
            role_label += " / " + aspect_title
        self.txt(x + 12, y + 33, role_label, 11, MUT, mono=True)

        # HP
        self.txt(x + 12, y + 54, "HP", 11, MUT, mono=True)
        self.txt(x + w - 12, y + 54, "%d/%d" % (u.hp, u.max_hp), 11, MUT, mono=True, anchor="ne")
        self.bar(x + 12, y + 70, w - 24, 9, u.hp / u.max_hp, DMG)

        # 격파체력
        self.txt(x + 12, y + 85, "격파체력", 11, MUT, mono=True)
        self.txt(x + w - 12, y + 85, "격파" if u.broken else "%d/%d" % (u.brk, u.max_brk),
                 11, MUT, mono=True, anchor="ne")
        self.bar(x + 12, y + 101, w - 24, 9, 1.0 if u.broken else u.brk / u.max_brk,
                 MUT if u.broken else BRKC)

        # SP 핍 + 속도
        sp_y = y + 117
        self.txt(x + 12, sp_y, "SP", 11, MUT, mono=True)
        px = x + 12 + self.font(11, mono=True).measure("SP") + 6
        for i in range(u.max_sp):
            self.canvas.create_rectangle(px, sp_y + 1, px + 10, sp_y + 11,
                                         fill=SPC if i < u.sp else "",
                                         outline=SPC, tags="ui")
            px += 13
        self.txt(px + 4, sp_y, "%d/%d" % (u.sp, u.max_sp), 11, MUT, mono=True)
        if u.alive and u.speed:
            self.txt(x + w - 12, sp_y, "SPD %d" % u.speed, 13, SPC, mono=True, anchor="ne")

        # 지정한 행동
        plan_label = self.plan_label(u)
        if plan_label:
            self.txt(x + 12, y + 135, plan_label, 11, MUT, mono=True)
    def enemy_targets(self, e):
        """이 적이 이번 라운드에 노리는 아군 [(아군, 행동이름), ...]"""
        plans = e.plans if (e.is_boss and e.plans) else ([e.plan] if e.plan else [])
        out = []
        for p in plans:
            t = p["type"]
            if t == "eaoe":
                out.extend((a, "차원 붕괴") for a in self.allies() if a.alive)
            elif t in ("normal", "eskill"):
                a = self.units.get(p.get("target"))
                if a and a.side == "ally":
                    out.append((a, "기본 공격" if t == "normal" else "강타"))
        return out

    def enemy_pending(self, e):
        """아직 행동하지 않은 적인가 (행동을 마친 적의 표시는 지운다)."""
        if self.state == "plan":
            return True
        if self.state == "resolve" and e in self.resolve_order:
            return self.resolve_order.index(e) >= getattr(self, "res_idx", 0)
        return False

    def enemy_plan_text(self, e):
        if e.is_boss and e.plans:
            if len(e.plans) == 1 and e.plans[0]["type"] == "eaoe":
                return "▶ ⚠ [차원 붕괴] 아군 전원 공격"
            parts = []
            for p in e.plans:
                if p["type"] == "guard":
                    parts.append("방어")
                else:
                    a = self.units.get(p.get("target"))
                    parts.append(a.name if a else "?")
            return "▶ 표적: " + " · ".join(parts)
        p = e.plan
        if p and p["type"] in ("normal", "eskill"):
            a = self.units.get(p.get("target"))
            return "▶ %s → %s" % ("기본 공격" if p["type"] == "normal" else "강타",
                                  a.name if a else "?")
        return "▶ 행동 준비 중"

    def render_enemy_arrows(self):
        """적 → 표적 아군으로 붉은 점선 화살표."""
        if self.state not in ("plan", "resolve") or self.game_over:
            return
        for e in self.enemies():
            if not e.alive or e.id not in self.card_rects or not self.enemy_pending(e):
                continue
            ex, ey, ew, eh = self.card_rects[e.id]
            seen = set()
            for a, _name in self.enemy_targets(e):
                if a.id in seen or not a.alive or a.id not in self.card_rects:
                    continue
                seen.add(a.id)
                ax, ay, aw, ah = self.card_rects[a.id]
                x1 = ax + aw / 2
                x0 = x1 if e.is_boss else ex + ew / 2
                self.canvas.create_line(x0, ey + eh, x1, ay - 4, fill=DMG, width=2,
                                        dash=(6, 4), arrow="last", tags="ui")
    def plan_label(self, u):
        if u.side == "enemy":
            if u.is_boss and u.plans:
                if len(u.plans) == 1 and u.plans[0]["type"] == "eaoe":
                    return "▶ ⚠ [차원 붕괴] 단독 행동 준비"
                return "▶ 이번 라운드 %d회 행동" % len(u.plans)
            return "▶ 행동 준비 중"
        if not u.plan or not u.alive:
            return ""
        t = u.plan["type"]
        if t == "guard":
            return "▣ 방어 태세"
        if t == "evade":
            return "▣ 회피 태세"
        if t == "imperial_servant":
            return "▶ 수호령"
        if u.side == "enemy":
            if u.is_boss and u.plans:
                if len(u.plans) == 1 and u.plans[0]["type"] == "eaoe":
                    return "▶ ⚠ [차원 붕괴] 단독 행동 준비"
                return "▶ 이번 라운드 %d회 행동" % len(u.plans)
            return "▶ 행동 준비 중"
        if t == "ultimate":
            return "★ 환상 · " + u.plan["ult"]["name"]
        if t == "normal":
            return "▶ 기본 공격"
        skill = u.plan["skill"] if "skill" in u.plan else u.skills[u.plan["idx"]]
        return "▶ " + skill["name"]

    def render_panel(self):
        x, y, w, h = MARGIN, PANEL_Y, WIN_W - MARGIN * 2, PANEL_H
        self.canvas.create_rectangle(x, y, x + w, y + h, fill=PANEL2, outline=BRD, tags="ui")

        if self.admin_kill_pending:
            self.txt(x + 16, y + 16, "[ADMIN] 처치할 아군을 선택하세요", 19, DMG, bold=True)
            self.txt(x + 16, y + 48, "아군의 불사·부활 효과는 정상 발동합니다. ESC 취소", 13, MUT, mono=True)
            return

        if self.game_over:
            self.txt(x + w / 2, y + h / 2, "전투가 종료됐다.", 16, MUT, mono=True, anchor="center")
            return

        if self.state == "augment_target":
            self.txt(x + 16, y + 16, "증강 [전술 재정비] — 대상 지정", 19, SPC, bold=True)
            self.txt(x + 16, y + 48, "SP를 즉시 최대로 채울 아군 카드를 클릭하세요.", 14, MUT, mono=True)
            return

        if self.state == "plan" and self.acting and not self.busy:
            u = self.acting
            if self.pending and not self.pending.get("mash"):
                self.txt(x + 16, y + 14, "%s — 대상 선택" % u.name, 19, TXT, bold=True)
                self.txt(x + 16, y + 46, self.status_msg or "", 14, MUT, mono=True)
                self.hbtn(x + 16, y + 78, None, 26, "← 취소하고 다시 선택", self.cancel_pending, MUT)
                return
            self.txt(x + 16, y + 10, "%s의 행동 지정  ·  SPD %d  ·  SP %d/%d"
                     % (u.name, u.speed, u.sp, u.max_sp), 18, TXT, bold=True)
            if self.is_fate_c(u):
                fate_progress = "필연 보유" if u.fate_ready else "필연 진행 %d/100" % u.fate_hp_spent
                hint = "%s · 체력은 10 미만이 되지 않음 · SP 회복 불가" % fate_progress
            elif self.is_bigsis(u):
                hint = "포장 %d · 달아오르는 재미 %s · %s · 방어 → 반격" % (
                    u.bs_wrap, ("제거됨" if u.bs_leva else u.bs_fun), "레바테인 개방" if u.bs_leva else "봉인된 검")
            elif self.is_orch(u):
                if u.orch_finale > 0:
                    hint = "피날레 · 사용 %d/3 · 남은 %d턴 · 피날레 스킬 외 사용 불가 · 격파 면역" % (
                        u.orch_finale_uses, max(0, u.orch_finale - 1))
                else:
                    hint = "관객 %g/%d · 레가토 5+ · 포르테 8+ · 다카포 10+ · 20이면 치명타를 피날레로" % (
                        u.orch_aud, ORCH_AUD_MAX)
            elif self.is_oracle(u):
                hint = "해금 %s · 헤르메스 %d/9 · %s · 이번 턴 헤르메스 %d/3" % (
                    OR_ROMAN[u.or_unlock], u.or_hermes,
                    "Furioso-Replica 준비됨" if u.or_furioso else "스킬 3 = 가호 1",
                    u.or_hermes_turn)
            elif self.is_maestro(u):
                hint = "조망 %d · 생체재료 %d/10 · %s · 폐장 %s" % (
                    u.ma_view, u.ma_material, "걸작 보유" if u.ma_masterpiece else "걸작 없음",
                    "사용함" if u.ma_closing_used else ("준비됨" if u.ma_view <= 0 else "조망 0이면 해금"))
            elif self.is_underboss(u):
                lo, hi = self.ub_range(u)
                if u.ub_overheat >= 0:
                    hint = "예지안 과열 %d/30 · 회피 주사위 %d~%d · 가속탄 %d/%d · 처분 %s" % (
                        u.ub_overheat, lo, hi, u.ub_ammo, UB_AMMO_MAX,
                        "사용함" if u.ub_disposal_used else "사용 가능")
                else:
                    hint = "예지 %d · 회피 주사위 %d~%d · 가속탄 %d/%d" % (
                        u.ub_foresight, lo, hi, u.ub_ammo, UB_AMMO_MAX)
            elif self.is_hero_h(u):
                hint = "보호막 %d · 피해 패시브 보호막 %d/50 · %s" % (
                    u.shield, u.hero_passive_shield_gained,
                    "영웅 버프" if u.hero_buff else "사망 시 전투당 1회 부활")
            elif self.is_imperial_n(u):
                hint = ("왕녀 · 기도 %d/120 · 희망 쿨다운 %d · 방어막 %s" %
                        (u.imperial_prayer, u.imperial_hope_cooldown,
                         "보호 발동" if u.imperial_safety_used else "보호 대기")) \
                    if u.imperial_princess else "수호령 · 기도 %d/120 · SP 외부 회복 불가" % u.imperial_prayer
            else:
                hint = "행동을 지정하면 SP가 즉시 반영되고, 해결은 속도 순으로 진행된다."
            if self.pending and self.pending.get("mash"):
                hint = "포르티시모 소모 SP %d/%d — 스킬 3 버튼을 연타해 늘리고, 적 카드를 클릭해 확정 (3 이상이면 모든 적)" % (
                    self.pending["skill"]["cost"], min(6, u.sp))
                self.hbtn(x + w - 16 - 130, y + 8, 130, 24, "← 취소", self.cancel_pending, MUT)
            self.txt(x + 16, y + 34, hint, 11, MUT, mono=True)

            bw, bh, gap = (w - 32 - 2 * 10) / 3, 40, 10
            base_atk = 10 + self.aug_atk_bonus
            cells = []
            imperial_guardian = self.is_imperial_n(u) and not u.imperial_princess
            normal_sub = "기도 +20 · 무작위 아군 보호 · SP +2" if imperial_guardian else \
                ("고정 %d 피해 · %s" % (
                    base_atk, "SP 회복 불가" if self.is_fate_c(u) else "SP +1"))
            normal_label = "수호령" if imperial_guardian else "기본 공격"
            normal_tip = (["대상을 지정하지 않는다", "이번 턴 자신이 받는 피해를 무작위 아군에게 절반 전이",
                           "사용 즉시 기도 +20 · 전이된 피해만큼 기도 추가 획득"]
                          if imperial_guardian else
                          ["대상 적 1기에게 %d 고정 피해" % base_atk,
                           "SP 회복 불가" if self.is_fate_c(u) else "SP +1 (지정 즉시 반영)",
                           "피해의 절반만큼 격파체력도 깎인다"])
            cells.append((normal_label, normal_sub, True,
                          STAR_COLOR[3] if imperial_guardian else DMG,
                          self.choose_normal, normal_tip))
            for idx, sk in enumerate(self.skills_for(u)):
                hp_cost = sk.get("hp_cost", 0)
                shield_cost = sk.get("shield_cost", 0)
                ok = self.can_use_skill(u, sk)
                if sk["kind"] == "attack":
                    eff = "피해 %d" % sk["dmg"]
                else:
                    eff = sk["desc"]
                costs = []
                if hp_cost:
                    costs.append("체력 %d (현재 %d, 최소 10 유지)" % (hp_cost, u.hp))
                if shield_cost:
                    costs.append("보호막 %d 이상이면 강화 (현재 %d)" % (shield_cost, u.shield))
                if sk["cost"]:
                    costs.append("SP %d/%d" % (sk["cost"], u.sp))
                cost_text = " · ".join(costs) or "자원 소모 없음"
                if sk["kind"] == "fate_ultimate":
                    cost_text = "필연 소비 · 자원 소모 없음"
                    ok = u.fate_ready
                elif sk["kind"] == "hero_echo":
                    cost_text = "자원 소모 없음 · 전투당 1회"
                tip = [cost_text, sk["desc"]]
                if self.is_imperial_n(u):
                    if not u.imperial_princess:
                        tip.append("※ 왕녀로써의 기도가 닿지 않았다")
                    elif sk["kind"] == "imperial_hope" and u.imperial_hope_cooldown > 0:
                        tip.append("※ 쿨다운 %d턴 남음" % u.imperial_hope_cooldown)
                    elif sk["kind"] == "imperial_command":
                        tip.append("수비 행동 미발동 · 격파 피해 없음 · 전투당 1회")
                if sk["kind"] == "attack":
                    tip.append("피해 %d · 격파체력 %d 감소" % (sk["dmg"], sk["dmg"] // 2))
                    if sk.get("fx") == "snipe":
                        tip.append("조준경 락온 후 관통 저격 연출")
                    elif sk.get("fx") == "frenzy":
                        tip.append("난격 10연타 후 마무리 일격")
                    if sk.get("extra_brk"):
                        tip.append("추가 격파피해 %d" % sk["extra_brk"])
                elif sk["kind"] == "curse":
                    tip.append("저주 지속 중 받는 피해 ×1.5")
                    tip.append("격파 상태와 곱연산 중첩 → 최대 ×2.25")
                if hp_cost and not ok:
                    tip.append("※ 체력이 부족하다 (사용 후 체력 10 이상 필요)")
                if sk["cost"] and u.sp < sk["cost"]:
                    tip.append("※ SP가 %d 부족하다" % (sk["cost"] - u.sp))
                if sk["kind"].startswith("imperial_"):
                    accent = STAR_COLOR[3]
                elif sk["kind"].startswith(("ub_", "ma_", "bs_", "or_")):
                    accent = UB_RED
                elif sk["kind"].startswith(("painter_", "cook_")):
                    accent = DMG
                elif sk["kind"].startswith("dist_"):
                    accent = CURSE
                elif sk["kind"].startswith("orch_"):
                    accent = STAR_COLOR[3]
                elif sk["kind"].startswith("dream_"):
                    accent = DREAM_PUR
                elif sk["kind"] in ("fate_attack", "fate_splash", "fate_stun", "fate_ultimate",
                                   "hero_attack", "hero_memory", "hero_afterimage", "hero_echo"):
                    accent = STAR_COLOR[3]
                elif sk["kind"] in ("attack", "attack_splash", "focus"):
                    accent = DMG
                elif sk["kind"] in ("curse", "speed_debuff"):
                    accent = CURSE
                elif sk["kind"] in ("shield_self", "shield_ally"):
                    accent = SHLD
                elif sk["kind"] == "sp_gain":
                    accent = SPC
                else:
                    accent = HEAL
                resource_parts = []
                if hp_cost:
                    resource_parts.append("HP %d" % hp_cost)
                if shield_cost:
                    resource_parts.append("조건부 보호막 %d" % shield_cost)
                if sk["kind"] == "fate_ultimate":
                    resource_parts.append("필연")
                elif sk["kind"] == "hero_echo":
                    resource_parts.append("전투당 1회")
                elif sk["cost"]:
                    resource_parts.append("SP %d" % sk["cost"])
                resource_label = " / ".join(resource_parts) or "자원 없음"
                cells.append((sk["name"], "%s · %s" % (resource_label, eff), ok, accent,
                              (lambda i: (lambda: self.choose_skill(i)))(idx), tip))
            guard_sub = "피해 감소 · %s · 즉시" % (
                "SP 회복 불가" if self.is_fate_c(u) else "SP +2")
            lock_guard = False   # 방어/회피는 왕녀 여부와 무관하게 사용 가능
            cells.append(("방어", guard_sub, not lock_guard, HEAL, self.choose_guard,
                          ["지정 즉시 태세를 취한다 (속도 무관)",
                           "피격 시 주사위 1~5 → 그 값×10% 피해 감소",
                           "주사위 6 → 80% 감소",
                           "SP 회복 불가" if self.is_fate_c(u) else "SP +2 · 1회 피격으로 소모"]))
            evade_sub = "완전 회피 시도 · %s · 즉시" % (
                "SP 회복 불가" if self.is_fate_c(u) else "SP +2")
            cells.append(("회피", evade_sub, not lock_guard, SPC, self.choose_evade,
                          ["지정 즉시 태세를 취한다 (속도 무관)",
                           "피격 시 양측 주사위 대결",
                           "내 값이 상대와 같거나 크면 피해 0",
                           "SP 회복 불가" if self.is_fate_c(u) else "SP +2 · 1회 피격으로 소모"]))

            if self.is_bigsis(u):                  # 방어 버튼 → 반격 버튼
                for _ci, _c in enumerate(cells):
                    if _c[0] == "방어":
                        cells[_ci] = ("반격", "받는 피해 -40% · 피격 반격 50% · SP +2", _c[2], DMG, _c[4],
                                      ["지정 즉시 반격 태세를 취한다 (속도 무관)",
                                       "이번 턴 받는 피해 40% 감소",
                                       "피격 후 받은 피해의 50%만큼 반격 (이 피해로 적을 처치할 수 없다)",
                                       "반격 2회 사용마다 달아오르는 재미 -1",
                                       "SP +2"])
            if self.is_orch(u) and u.orch_finale > 0:      # 피날레 — 피날레 스킬 외 사용 불가
                for _fi in range(len(cells)):
                    if _fi == 0 or _fi >= len(cells) - 2:
                        _c = cells[_fi]
                        cells[_fi] = (_c[0], _c[1], False, _c[3], _c[4],
                                      _c[5] + ["※ 피날레 중에는 피날레 스킬 외 사용할 수 없다"])
            self.tips = {}
            for i, (label, sub, ok, accent, cb, tip) in enumerate(cells):
                col, row = i % 3, i // 3
                bx = x + 16 + col * (bw + gap)
                by = y + 56 + row * (bh + 8)
                oc = accent if ok else BRD
                tc = TXT if ok else MUT
                hovered = self.hover == ("btn", i)
                self.canvas.create_rectangle(bx, by, bx + bw, by + bh,
                                             fill="#262D36" if hovered else PANEL,
                                             outline=oc, tags="ui")
                self.txt(bx + 10, by + 4, label, 15, tc, bold=True)
                sub_f = self.font(10, mono=True)
                if sub_f.measure(sub) > bw - 20:
                    while sub and sub_f.measure(sub + "…") > bw - 20:
                        sub = sub[:-1]
                    sub += "…"
                self.txt(bx + 10, by + 23, sub, 10, MUT, mono=True)
                self.tips[i] = (label, tip)
                self.buttons.append(dict(x=bx, y=by, w=bw, h=bh,
                                         cb=(cb if ok else (lambda: None)), key=("btn", i)))
            ult = ULTIMATES.get(u.id)
            if ult:                                  # 환상(궁극기) 버튼 — 패널 오른쪽 위
                ok_u, why = self.ult_ready(u)
                ux, uy, uw, uh = x + w - 16 - 262, y + 8, 262, 42
                hov_u = self.hover == ("btn", 100)
                col_u = ult["color"]
                self.canvas.create_rectangle(ux, uy, ux + uw, uy + uh,
                                             fill="#262D36" if hov_u else PANEL,
                                             outline=col_u if ok_u else BRD,
                                             width=3 if ok_u else 1, tags="ui")
                ratio_u = max(0.0, min(1.0, u.ult_gauge / float(ult["cost"])))
                if ratio_u > 0:
                    self.canvas.create_rectangle(ux + 1, uy + uh - 6, ux + 1 + (uw - 2) * ratio_u,
                                                 uy + uh - 1,
                                                 fill=col_u if ok_u else lerp_color(PANEL, col_u, 0.5),
                                                 outline="", tags="ui")
                self.txt(ux + 10, uy + 3, "환상 · %s" % ult["name"], 14,
                         col_u if ok_u else MUT, bold=True)
                self.txt(ux + 10, uy + 22, why, 10, MUT, mono=True)
                self.tips[100] = ("환상 · " + ult["name"], [
                    "일종의 궁극기 — 스킬 포인트 대신 환상도와 격파체력을 소비한다",
                    "환상도 %d%% 소비 · 격파체력 %d 소비 (0이 되면 발동 후 격파 상태)" %
                    (ult["cost"], ult["brk"]),
                    ult["desc"],
                    "개화: 받는 피해 20% 증가 · 턴 종료시 1 감소 · 0이 되면 소멸",
                    "사용 후 %d턴간 사용할 수 없다" % ULT_COOLDOWN,
                    "환상도는 스킬 포인트 1 소비당 %d%% 충전 (현재 %d%%)" % (ULT_GAIN_PER_SP, u.ult_gauge),
                    "※ " + why if not ok_u else "▶ 클릭 후 대상을 선택"])
                self.buttons.append(dict(x=ux, y=uy, w=uw, h=uh, key=("btn", 100),
                                         cb=(self.choose_ultimate if ok_u else (lambda: None))))
            return

        msg = self.status_msg or "진행 중..."
        self.txt(x + w / 2, y + h / 2 - 12, msg, 17, TXT, mono=True, anchor="center")
        if self.resolve_order and self.state in ("plan", "resolve"):
            order = " → ".join("%s(%d)" % (u.name, u.speed) for u in self.resolve_order if u.alive)
            self.txt(x + w / 2, y + h / 2 + 18, order, 13, MUT, mono=True, anchor="center")

    def render_log(self):
        x, y, w, h = MARGIN, LOG_Y, WIN_W - MARGIN * 2, LOG_H
        self.canvas.create_rectangle(x, y, x + w, y + h, fill=PANEL, outline=BRD, tags="ui")
        f = self.font(12, mono=True)
        lh = f.metrics("linespace") + 2
        rows = max(1, int((h - 14) // lh))
        for i, (msg, color) in enumerate(self.log_lines[-rows:]):
            text = msg
            while text and f.measure(text) > w - 24:
                text = text[:-1]
            self.txt(x + 12, y + 7 + i * lh, text, 12, color, mono=True)

    # ---------------- 증강 선택 화면 ----------------
    def render_augment(self):
        if self.state != "augment_pick" or not self.aug_options:
            return
        self.canvas.create_rectangle(0, 0, WIN_W, WIN_H, fill="#000000", outline="",
                                     stipple="gray75", tags="ui")
        title_txt = "증강 선택" + ("  (보스 보상)" if self.aug_tier == 2 else "")
        self.txt(WIN_W / 2, 150, title_txt, 36, TXT, bold=True, anchor="center")
        self.txt(WIN_W / 2, 196,
                 "PHASE %d 돌파 — 하나를 골라 영구 강화한다 (고른 증강은 이후 같은 티어 목록에서 제외)"
                 % (self.phase - 1),
                 13, MUT, mono=True, anchor="center")

        opts = self.aug_options
        n = len(opts)
        cw, ch, gap = 288, 212, 22
        total = n * cw + (n - 1) * gap
        sx = (WIN_W - total) / 2
        by = 250

        for i, aug in enumerate(opts):
            bx = sx + i * (cw + gap)
            hovered = self.hover == ("aug", i)
            self.canvas.create_rectangle(bx + 4, by + 4, bx + cw + 4, by + ch + 4,
                                         fill="#0A0C10", outline="", stipple="gray50", tags="ui")
            self.canvas.create_rectangle(bx, by, bx + cw, by + ch,
                                         fill=PANEL2 if hovered else PANEL,
                                         outline=aug["color"], width=3 if hovered else 1,
                                         tags="ui")
            self.canvas.create_rectangle(bx, by, bx + cw, by + 6, fill=aug["color"],
                                         outline="", tags="ui")
            self.txt(bx + cw / 2, by + 34, aug["title"], 21, aug["color"], bold=True,
                     anchor="center")
            self.canvas.create_line(bx + 20, by + 60, bx + cw - 20, by + 60, fill=BRD, tags="ui")
            self.wtxt(bx + cw / 2, by + 74, cw - 40, aug["desc"], 13, TXT,
                      anchor="n", justify="center")

            # 현재 수치 안내
            info = self.aug_info_line(aug)
            if info:
                self.wtxt(bx + cw / 2, by + ch - 56, cw - 34, info, 11, MUT, mono=True,
                          anchor="n", justify="center")

            btn_c = aug["color"] if hovered else MUT
            self.canvas.create_rectangle(bx + 20, by + ch - 34, bx + cw - 20, by + ch - 10,
                                         fill=PANEL2, outline=btn_c, tags="ui")
            self.txt(bx + cw / 2, by + ch - 22, "선 택", 13, btn_c, mono=True, anchor="center")

            self.buttons.append(dict(x=bx, y=by, w=cw, h=ch, key=("aug", i),
                                     cb=(lambda k: (lambda: self.choose_augment(k)))(i)))

        pool_all = AUGMENTS if self.aug_tier == 1 else AUGMENTS2
        taken = self.aug_taken if self.aug_tier == 1 else self.aug_taken2
        left = len(pool_all) - len(taken) - 1
        self.txt(WIN_W / 2, by + ch + 34,
                 "남은 증강 %d종  ·  획득 %d/%d" % (max(0, left), len(taken), len(pool_all)),
                 12, MUT, mono=True, anchor="center")

    def aug_info_line(self, aug):
        if aug["id"] == "hp":
            return "현재 최대 체력 %d → %d" % (self.units["N"].max_hp, self.units["N"].max_hp + 50)
        if aug["id"] == "atk":
            return "기본 공격 %d → %d" % (10 + self.aug_atk_bonus, 15 + self.aug_atk_bonus)
        if aug["id"] == "brk":
            return "격파피해 배율 %d%% → %d%%" % (round(100 * (1 + self.aug_brk_bonus)),
                                             round(100 * (1 + self.aug_brk_bonus + 0.15)))
        if aug["id"] == "dice":
            return "속도 주사위 %d~6 → 2~6" % self.aug_speed_min
        if aug["id"] == "sp_full":
            return "선택 후 아군 카드를 클릭해 대상 지정"
        if aug["id"] == "s2_hp":
            return "현재 최대 체력 %d → %d" % (self.units["N"].max_hp, self.units["N"].max_hp + 50)
        if aug["id"] == "s2_atk":
            return "기본 공격 %d → %d" % (10 + self.aug_atk_bonus, 15 + self.aug_atk_bonus)
        if aug["id"] == "s2_brk":
            return "현재 최대 격파체력 %d → %d" % (self.units["N"].max_brk, self.units["N"].max_brk + 50)
        if aug["id"] == "s2_reduce":
            return "받는 피해 감소 %d → %d" % (self.aug_dmg_reduction, self.aug_dmg_reduction + 10)
        if aug["id"] == "s2_undying":
            return "보유 시 전투당 1회 · 사망 직전 체력 1로 2턴 버티기"
        return ""

    def render_overlay(self):
        if not self.overlay:
            return
        o = self.overlay
        self.canvas.create_rectangle(0, 0, WIN_W, WIN_H, fill="#000000", outline="",
                                     stipple="gray50", tags="ui")
        if o["kind"] == "speed":
            self.txt(WIN_W / 2, 250, "속도 판정", 32, WHITE, bold=True, anchor="center")
            actors = o["actors"]
            n = len(actors)
            size = 74
            gap = 26
            total = n * size + (n - 1) * gap
            sx = (WIN_W - total) / 2 + size / 2
            for i, u in enumerate(actors):
                cx = sx + i * (size + gap)
                self.draw_die(cx, 340, size, o["vals"][u.id], tag="ui")
                self.txt(cx, 392, u.name, 14, SPC if u.side == "ally" else DMG,
                         mono=True, anchor="center")
            sub = "높은 값이 먼저 행동한다"
            if self.aug_speed_min > 1:
                sub += "   (아군 주사위 %d~6)" % self.aug_speed_min
            self.txt(WIN_W / 2, 440, sub, 14, MUT, mono=True, anchor="center")
        elif o["kind"] == "judge":
            pairs = o["pairs"]
            n = len(pairs)
            size = 88
            gap = 56
            total = n * size + (n - 1) * gap
            sx = (WIN_W - total) / 2 + size / 2
            for i, (lab, val) in enumerate(pairs):
                cx = sx + i * (size + gap)
                self.draw_die(cx, 360, size, val, tag="ui")
                self.txt(cx, 420, lab, 15, WHITE, mono=True, anchor="center")
        elif o["kind"] == "banner":
            self.canvas.create_rectangle(WIN_W / 2 - 230, 320, WIN_W / 2 + 230, 420,
                                         fill=PANEL, outline=BRKC, width=2, tags="ui")
            self.txt(WIN_W / 2, 352, o["text"], 42, TXT, bold=True, anchor="center")
            self.txt(WIN_W / 2, 392, o["sub"], 14, MUT, mono=True, anchor="center")

    def wrap_lines(self, lines, font, maxw):
        """툴팁 줄이 화면 밖으로 나가지 않도록 폭 기준으로 줄바꿈한다 (이어지는 줄은 들여쓴다)."""
        expanded = []
        for line in lines:                       # 설명 안의 ' / ' 는 노션 원문의 줄바꿈이다
            lead = " " * (len(line) - len(line.lstrip(" ")))
            parts = line.split(" / ")
            expanded.append(parts[0])
            expanded.extend(lead + part for part in parts[1:])
        lines = expanded
        out = []
        for line in lines:
            if font.measure(line) <= maxw:
                out.append(line)
                continue
            indent = " " * (len(line) - len(line.lstrip(" ")) + 3)
            cur = ""
            for ch in line:
                if cur and font.measure(cur + ch) > maxw:
                    cut = cur.rfind(" ")
                    if cut > len(cur) * 0.5:          # 단어 중간 대신 공백에서 끊는다
                        out.append(cur[:cut])
                        cur = indent + cur[cut + 1:]
                    else:
                        out.append(cur)
                        cur = indent
                cur += ch
            if cur.strip():
                out.append(cur)
        return out

    def render_tooltip(self):
        if self.modal or self.overlay:
            return
        if not (isinstance(self.hover, tuple) and self.hover[0] == "btn"):
            return
        info = self.tips.get(self.hover[1])
        if not info:
            return
        title, lines = info
        tf, lf = self.font(15, bold=True), self.font(12, mono=True)
        lines = self.wrap_lines(lines, lf, 520)
        tw = max([tf.measure(title)] + [lf.measure(l) for l in lines]) + 24
        lh = lf.metrics("linespace") + 3
        th = 12 + tf.metrics("linespace") + 6 + len(lines) * lh + 10

        mx, my = self.mouse
        bx = min(max(8, mx + 16), WIN_W - tw - 8)
        by = my - th - 14
        if by < 8:
            by = min(my + 22, WIN_H - th - 8)
        by = max(8, by)

        self.canvas.create_rectangle(bx + 3, by + 3, bx + tw + 3, by + th + 3,
                                     fill="#0A0C10", outline="", stipple="gray50", tags="ui")
        self.canvas.create_rectangle(bx, by, bx + tw, by + th, fill=PANEL2, outline=SPC,
                                     tags="ui")
        self.txt(bx + 12, by + 8, title, 15, TXT, bold=True)
        ty = by + 8 + tf.metrics("linespace") + 6
        for l in lines:
            color = DMG if l.startswith("※") else MUT
            self.txt(bx + 12, ty, l, 12, color, mono=True)
            ty += lh

    def render_modal(self):
        if not self.modal:
            return
        m = self.modal
        self.canvas.create_rectangle(0, 0, WIN_W, WIN_H, fill="#000000", outline="",
                                     stipple="gray50", tags="ui")
        bx, by, bw, bh = WIN_W / 2 - 200, 300, 400, 210
        self.canvas.create_rectangle(bx, by, bx + bw, by + bh, fill=PANEL, outline=BRD,
                                     width=2, tags="ui")
        self.txt(bx + bw / 2, by + 46, m["title"], 40, m["color"], bold=True, anchor="center")
        self.txt(bx + bw / 2, by + 104, m["desc"], 14, MUT, mono=True, anchor="center")
        self.hbtn(bx + 30, by + 142, 150, 34, "다시 시작", self.new_game, TXT)
        self.hbtn(bx + 220, by + 142, 150, 34, "로비로", self.go_lobby, HEAL)

    # ================================================================
    # 어드민 패널 — 전투 중 'maki' 입력으로 호출
    # ================================================================
    def on_key(self, ev):
        if self.title_screen:
            if ev.keysym in ("Return", "KP_Enter", "space"):
                self.title_play()
            return
        if self.formation_open:                    # 편성 창이 열려 있으면 R / ESC 만 받는다
            ch0 = (ev.char or "").lower()
            if ev.keysym == "Escape" or ch0 in ("r", "ㄱ") or ev.keysym.lower() == "r":
                self.close_formation()
            return "break" if ev.keysym == "Tab" else None
        if ev.keysym == "Tab":                     # 인벤토리 열기/닫기 (포커스 이동은 막는다)
            self.toggle_inventory()
            return "break"
        if self.inv_open:
            if ev.keysym == "Escape":
                self.close_inventory()
            return "break"
        if self.char_key(ev):
            return
        if self.theme_arrow_key(ev):
            return
        if self.story_key(ev):
            return
        if ev.keysym == "Escape":
            if self.admin:
                self.close_admin()
            elif self.admin_kill_pending:
                self.admin_cancel_kill_ally()
            elif self.pity_choice_open:
                self.close_pity_choice()
            elif self.codex_open:
                self.codex_esc()
            elif self.gacha_open:
                self.close_gacha()
            return
        ch = (ev.char or "").lower()
        if ch in ("r", "ㄱ") or ev.keysym.lower() == "r":
            self.toggle_formation()
            return
        if ch in ("e", "ㄷ") or ev.keysym.lower() == "e":
            self.toggle_gacha()
            return
        if ch in ("f", "ㄹ") or ev.keysym.lower() == "f":
            self.toggle_codex()
            return
        if ch in ("z", "ㅋ") or ev.keysym.lower() == "z":
            if not self.lobby:
                self.toggle_workshop()
            return
        if not ch.isalpha():
            return
        self.key_buf = (self.key_buf + ch)[-12:]
        if self.key_buf.endswith(ADMIN_CODE):
            self.key_buf = ""
            self.toggle_admin()


    def on_drag(self, ev):
        if self.__dict__.get("_sb_drag"):
            self.story_drag(ev)
        else:
            self.on_motion(ev)

    def on_release(self, ev):
        self._sb_drag = None


    # ---------------- 입력 ----------------
    # ================================================================
    # 로비 — 게임을 켜면 가장 먼저 나오는 허브. 워프 게이트로 전투 / 제작소 / 형상 / 서재로 이동한다.
    # ================================================================
    def apply_equipped_all(self):
        """로비에서 장착해 둔 형상을 새 전투의 아군에게 적용한다."""
        eq = self.__dict__.get("equipped") or {}
        owned = self.__dict__.get("owned_aspects") or ()
        for cid, unit in self.roster.items():
            if unit.side != "ally":
                continue
            aid = eq.get(cid)
            asp = next((a for a in ALL_ASPECTS if a["id"] == aid), None)
            if not asp or aid not in owned:
                continue
            unit.aspect_id = aid
            unit.skills = asp["skills"]
            unit.max_sp = 10 if aid == "n_imperial" else MAX_SP

    def go_lobby(self):
        """전투를 마치고 로비로 돌아간다. (형상·조각·형상파편은 유지, 전투 진행도는 초기화)"""
        self._enter = time.monotonic()
        self.new_game(to_lobby=True)

    def lobby_start_battle(self):
        self.new_game()


    def lobby_emblem(self, gid, cx, cy, col):
        cv = self.canvas
        if gid == "battle":
            cv.create_line(cx - 26, cy - 26, cx + 26, cy + 26, fill=col, width=5,
                           capstyle="round", tags="ui")
            cv.create_line(cx + 26, cy - 26, cx - 26, cy + 26, fill=col, width=5,
                           capstyle="round", tags="ui")
            cv.create_oval(cx - 9, cy - 9, cx + 9, cy + 9, outline=col, width=3, tags="ui")
        elif gid == "workshop":
            pts = []
            for k in range(6):
                a = math.pi / 3 * k + math.pi / 6
                pts += [cx + math.cos(a) * 32, cy + math.sin(a) * 32]
            cv.create_polygon(*pts, fill="", outline=col, width=4, tags="ui")
            cv.create_oval(cx - 11, cy - 11, cx + 11, cy + 11, outline=col, width=4, tags="ui")
        elif gid == "aspect":
            pts = []
            for k in range(10):
                a = -math.pi / 2 + math.pi * k / 5
                r = 36 if k % 2 == 0 else 15
                pts += [cx + math.cos(a) * r, cy + math.sin(a) * r]
            cv.create_polygon(*pts, fill="", outline=col, width=3, tags="ui")
        else:
            cv.create_rectangle(cx - 36, cy - 24, cx - 2, cy + 26, outline=col, width=3, tags="ui")
            cv.create_rectangle(cx + 2, cy - 24, cx + 36, cy + 26, outline=col, width=3, tags="ui")
            for k in range(3):
                cv.create_line(cx - 28, cy - 8 + k * 11, cx - 10, cy - 8 + k * 11,
                               fill=col, tags="ui")
                cv.create_line(cx + 10, cy - 8 + k * 11, cx + 28, cy - 8 + k * 11,
                               fill=col, tags="ui")

    # ---------------- 타이틀 / 로비 (로비 패치) ----------------
    def _now(self):
        if self._t0 is None:
            self._t0 = time.monotonic()
        return time.monotonic() - self._t0

    def _fc(self, col, a):
        """공허 배경에서 col 쪽으로 a(0~1)만큼 섞은 색 — 알파 대용."""
        return lerp_color(LB_BG, col, max(0.0, min(1.0, a)))

    def _stars_data(self):
        if "_stars" not in self.__dict__:
            rnd = random.Random(7)
            cols = ["#FFFFFF", "#CFC4FF", "#FFC2E2", "#9CC4FF"]
            self._stars = [(rnd.uniform(0, WIN_W), rnd.uniform(0, WIN_H),
                            rnd.choice([1, 1, 1.4, 2, 2.6]), rnd.uniform(1.5, 7),
                            rnd.uniform(0, 6.28), rnd.uniform(0.6, 2.2), rnd.choice(cols))
                           for _ in range(95)]
        return self._stars

    def _draw_void(self, t, a=1.0):
        cv = self.canvas
        try:
            cv.configure(bg=LB_BG)
        except tk.TclError:
            pass
        cx, cy = WIN_W / 2, 430
        steps = 9
        breath = 0.9 + 0.1 * math.sin(t * 0.5)
        for k in range(steps):                       # 성운
            r = 470 - k * 48
            col = lerp_color(LB_BG, LB_NEBULA, (k + 1) / steps * 0.85 * breath)
            cv.create_oval(cx - r, cy - r * 0.8, cx + r, cy + r * 0.8,
                           fill=self._fc(col, a), outline="", tags="ui")
        for r, sp in ((300, 8), (400, -5), (500, 3)):    # 굴레 — 느리게 도는 점선 고리
            cv.create_oval(cx - r, cy - r * 0.8, cx + r, cy + r * 0.8,
                           outline=self._fc(LB_RING, a * 0.55), width=2, dash=(2, 14),
                           dashoffset=int((t * sp) % 16), tags="ui")
        for sx, sy, r, drift, ph, tws, col in self._stars_data():   # 별
            y = (sy + t * drift) % WIN_H
            x = sx + math.sin(t * 0.3 + ph) * 6
            tw = 0.5 + 0.5 * math.sin(t * tws + ph * 6)
            c = self._fc(col, a * (0.25 + 0.75 * tw))
            if r > 1.8:
                L = r * 3.2
                cv.create_line(x - L, y, x + L, y, fill=c, tags="ui")
                cv.create_line(x, y - L, x, y + L, fill=c, tags="ui")
            cv.create_oval(x - r, y - r, x + r, y + r, fill=c, outline="", tags="ui")

    def _glitch_text(self, x, y, text, size, col, t, a=1.0, bold=True, mono=False):
        if int(t * 9) % 41 == 0:   # 가끔 색이 갈라지는 글리치
            self.txt(x - 4, y, text, size, self._fc(ROSE, a * 0.8), mono=mono,
                     anchor="center", bold=bold)
            self.txt(x + 4, y + 1, text, size, self._fc(BLUE_H, a * 0.8), mono=mono,
                     anchor="center", bold=bold)
        self.txt(x, y, text, size, self._fc(col, a), mono=mono, anchor="center", bold=bold)

    def title_play(self):
        self.title_screen = False
        self._enter = time.monotonic()
        beep([(523, 70), (784, 80), (1046, 140)], self.sound)
        self.render()

    # ================================================================
    # 편성 창 (R 키) — 위: 현재 편성 3슬롯 / 아래: 4명 중 터치해서 배치
    # ================================================================
    def toggle_formation(self):
        if self.formation_open:
            self.close_formation()
            return
        if not self.lobby:
            self.log("편성은 로비에서만 바꿀 수 있다. (전투 종료 → 로비)", MUT)
            self.render()
            return
        if (self.title_screen or self.gacha_open or self.codex_open or self.inv_open
                or self.modal):
            return
        self.formation_open = True
        self.form_sel = 0
        self.render()

    def close_formation(self):
        self.formation_open = False
        self.render()

    def form_select_slot(self, i):
        self.form_sel = i
        self.render()

    def form_place(self, cid):
        """선택한 슬롯에 캐릭터를 배치한다. 이미 편성된 캐릭터면 서로 자리를 맞바꾼다."""
        sel = self.form_sel
        if cid in self.party:
            j = self.party.index(cid)
            self.party[j], self.party[sel] = self.party[sel], self.party[j]
        else:
            self.party[sel] = cid
        self.form_sel = (sel + 1) % len(self.party)
        beep([(660, 40), (880, 60)], self.sound)
        self.render()

    def render_formation(self):
        if not self.formation_open:
            return
        self.buttons = []
        cv = self.canvas
        cv.create_rectangle(0, 0, WIN_W, WIN_H, fill="#000000", outline="",
                            stipple="gray75", tags="ui")
        pw, ph = 900, 560
        px, py = (WIN_W - pw) / 2, 120
        cv.create_rectangle(px + 5, py + 5, px + pw + 5, py + ph + 5, fill="#05070A",
                            outline="", stipple="gray50", tags="ui")
        cv.create_rectangle(px, py, px + pw, py + ph, fill=PANEL, outline=DREAM_PUR,
                            width=2, tags="ui")
        cv.create_rectangle(px, py, px + pw, py + 5, fill=DREAM_PUR, outline="", tags="ui")
        self.txt(px + 24, py + 16, "편성", 28, TXT, bold=True)
        self.txt(px + 100, py + 30, "슬롯을 고른 뒤, 아래 캐릭터를 터치해 배치한다", 12, MUT, mono=True)
        self.txt(px + pw - 24, py + 24, "[R] / [ESC] 닫기", 11, MUT, mono=True, anchor="ne")
        cv.create_line(px + 24, py + 64, px + pw - 24, py + 64, fill=BRD, tags="ui")

        info = dict((cid, (name, role, col)) for cid, name, role, col in ROSTER_INFO)

        # 위: 현재 편성 슬롯
        self.txt(px + 24, py + 78, "현재 편성  (앞 슬롯부터 왼쪽 → 오른쪽)", 13, TXT, bold=True)
        sw, sh, gap = (pw - 48 - 2 * 16) / 3, 150, 16
        sy = py + 106
        for i, cid in enumerate(self.party):
            name, role, col = info[cid]
            sx = px + 24 + i * (sw + gap)
            sel = (self.form_sel == i)
            hov = self.hover == ("frm", i)
            cv.create_rectangle(sx, sy, sx + sw, sy + sh, fill=PANEL2 if (sel or hov) else PANEL,
                                outline=SPC if sel else col, width=4 if sel else 2, tags="ui")
            self.txt(sx + 12, sy + 8, "SLOT %d" % (i + 1), 11, SPC if sel else MUT, mono=True)
            self.txt(sx + sw / 2, sy + 66, name, 46, col, bold=True, anchor="center")
            self.txt(sx + sw / 2, sy + 112, role, 12, TXT, mono=True, anchor="center")
            if sel:
                self.txt(sx + sw / 2, sy + sh - 14, "▼ 아래에서 배치할 캐릭터 선택", 10, SPC,
                         mono=True, anchor="center")
            self.buttons.append(dict(x=sx, y=sy, w=sw, h=sh, key=("frm", i),
                                     cb=(lambda k=i: self.form_select_slot(k))))

        # 아래: 선택 가능한 4명
        cy0 = sy + sh + 40
        self.txt(px + 24, cy0 - 26, "편성 가능한 캐릭터", 13, TXT, bold=True)
        n = len(ROSTER_INFO)
        cw, ch_, g2 = (pw - 48 - (n - 1) * 14) / n, 150, 14
        for k, (cid, name, role, col) in enumerate(ROSTER_INFO):
            cx = px + 24 + k * (cw + g2)
            in_party = cid in self.party
            hov = self.hover == ("frm", 10 + k)
            cv.create_rectangle(cx, cy0, cx + cw, cy0 + ch_, fill=PANEL2 if hov else PANEL,
                                outline=col, width=3 if hov else (2 if in_party else 1), tags="ui")
            self.txt(cx + cw / 2, cy0 + 56, name, 40, col, bold=True, anchor="center")
            self.txt(cx + cw / 2, cy0 + 100, role, 11, TXT, mono=True, anchor="center")
            if in_party:
                self.txt(cx + cw / 2, cy0 + 126, "편성 중 · SLOT %d" % (self.party.index(cid) + 1),
                         11, HEAL, mono=True, anchor="center")
            else:
                self.txt(cx + cw / 2, cy0 + 126, "터치해서 배치", 11, MUT, mono=True,
                         anchor="center")
            self.buttons.append(dict(x=cx, y=cy0, w=cw, h=ch_, key=("frm", 10 + k),
                                     cb=(lambda c=cid: self.form_place(c))))

        self.hbtn(px + pw / 2 - 70, py + ph - 46, 140, 32, "닫기 (R)", self.close_formation, MUT)


    def render_title(self):
        t = self._now()
        cx = WIN_W / 2
        self._draw_void(t)
        for k in range(5, 0, -1):                    # 로고 후광
            r = 60 + k * 34 + 6 * math.sin(t * 1.2)
            self.canvas.create_oval(cx - r * 2.2, 300 - r * 0.9, cx + r * 2.2, 300 + r * 0.9,
                                    outline=self._fc("#4B3A92", 0.10 + 0.05 * (6 - k)),
                                    width=2, tags="ui")
        self.txt(cx, 190, "P R O J E C T", 22, self._fc("#9C8FEC", 1), mono=True, anchor="center")
        self._glitch_text(cx, 300, "NHC", 130, TXT, t)
        self.canvas.create_line(cx - 230, 392, cx + 230, 392,
                                fill=self._fc(LB_LINE, 0.55), tags="ui")

        bw, bh = 260, 62
        bx, by = cx - bw / 2, 520
        hov = self.hover == ("title", 0)
        pulse = 0.5 + 0.5 * math.sin(t * 2.2)
        col = STAR_COLOR[3]
        glow = 0.45 + 0.35 * pulse + (0.2 if hov else 0)
        self.canvas.create_rectangle(bx - 8, by - 8, bx + bw + 8, by + bh + 8,
                                     outline=self._fc(col, glow * 0.5), tags="ui")
        self.canvas.create_rectangle(bx, by, bx + bw, by + bh,
                                     fill=self._fc(col, 0.22 if hov else 0.08),
                                     outline=self._fc(col, min(1.0, glow + 0.3)),
                                     width=3 if hov else 2, tags="ui")
        self.txt(cx, by + bh / 2, "▶  PLAY", 30, self._fc("#FFFFFF" if hov else col, 1),
                 bold=True, anchor="center")
        self.buttons.append(dict(x=bx, y=by, w=bw, h=bh, key=("title", 0), cb=self.title_play))
        if int(t * 1.6) % 2 == 0:
            self.txt(cx, 612, "PRESS ENTER", 12, MUT, mono=True, anchor="center")

    def render_lobby(self):
        if self.title_screen:
            self.render_title()
            return

        t = self._now()
        a = min(1.0, (time.monotonic() - self._enter) / 1.4) if self._enter else 1.0
        cv = self.canvas
        self._draw_void(t, a)

        # 헤더
        self.txt(MARGIN, 24, "NHC", 30, TXT, bold=True, anchor="w")
        logo_w = self.font(30, bold=True).measure("NHC")
        self.txt(MARGIN + logo_w + 12, 27, "LOBBY", 16, MUT, mono=True, anchor="w")
        self.txt(WIN_W - MARGIN, 10, "조각 %d   형상파편 %d" % (self.aspect_shards, self.aspect_pity),
                 13, SPC, mono=True, anchor="ne")
        self.hbtn(WIN_W - MARGIN, 32, None, 24, "게임 종료", self.root.destroy, MUT, anchor="ne")
        cv.create_line(MARGIN, 62, WIN_W - MARGIN, 62, fill=self._fc(BRD, a), width=2, tags="ui")

        # 별자리 선 + 흐르는 빛
        for n, (i, j) in enumerate(LOBBY_EDGES):
            x0, y0 = LOBBY_NODES[i][4], LOBBY_NODES[i][5]
            x1, y1 = LOBBY_NODES[j][4], LOBBY_NODES[j][5]
            cv.create_line(x0, y0, x1, y1, fill=self._fc(LB_LINE, a * 0.38), dash=(4, 8),
                           dashoffset=int((t * 14) % 12), tags="ui")
            p = (t * 0.22 + n * 0.31) % 1.0
            px, py = x0 + (x1 - x0) * p, y0 + (y1 - y0) * p
            cv.create_oval(px - 4, py - 4, px + 4, py + 4, fill=self._fc("#FFFFFF", a * 0.85),
                           outline="", tags="ui")
        cv.create_line(LOBBY_NODES[0][4], LOBBY_NODES[0][5], WIN_W / 2, 105,
                       LOBBY_NODES[1][4], LOBBY_NODES[1][5],
                       smooth=True, fill=self._fc(LB_LINE, a * 0.25), dash=(3, 9), tags="ui")

        # 노드
        for i, (gid, name, sub, col, cx, cy, rx, ry, cbname) in enumerate(LOBBY_NODES):
            hov = self.hover == ("gate", i)
            d = 1 if i % 2 == 0 else -1
            cy = cy + math.sin(t * 0.9 + i * 1.7) * 4        # 둥둥 떠 있는 느낌
            boost = 1.7 if hov else 1.0

            for k in range(4, 0, -1):                        # 바깥 후광
                e = k * 9 + (6 if hov else 0)
                cv.create_oval(cx - rx - e, cy - ry - e * 0.8, cx + rx + e, cy + ry + e * 0.8,
                               outline=self._fc(col, a * (0.10 + 0.05 * (5 - k)) * boost),
                               width=2, tags="ui")
            cv.create_oval(cx - rx, cy - ry, cx + rx, cy + ry,
                           fill=self._fc(col, a * (0.24 if hov else 0.10)),
                           outline=self._fc(col, a * (1.0 if hov else 0.75)),
                           width=4 if hov else 3, tags="ui")
            cv.create_oval(cx - rx + 12, cy - ry + 10, cx + rx - 12, cy + ry - 10,
                           outline=self._fc(col, a * 0.5), width=2, dash=(10, 8),
                           dashoffset=int((t * 30 * d) % 18), tags="ui")
            q = (t * 0.6 + i * 0.27) % 1.0                   # 퍼지는 맥동 링
            cv.create_oval(cx - rx - 40 * q, cy - ry - 32 * q, cx + rx + 40 * q, cy + ry + 32 * q,
                           outline=self._fc(col, a * (1 - q) * 0.45), tags="ui")
            for k in range(5):                               # 궤도 입자
                ang = t * 0.8 * d + k * math.tau / 5
                ox = cx + math.cos(ang) * (rx + 16)
                oy = cy + math.sin(ang) * (ry + 14)
                cv.create_oval(ox - 3, oy - 3, ox + 3, oy + 3, fill=self._fc(col, a * 0.8),
                               outline="", tags="ui")

            size = 34 if rx > 150 else 30
            self.txt(cx, cy - 8 if sub else cy, name, size, self._fc(col if hov else TXT, a),
                     bold=True, anchor="center")
            self.txt(cx, cy + 24, sub, 12, self._fc(TXT if hov else MUT, a),
                     mono=True, anchor="center")
            if hov:
                self.txt(cx, cy + ry + 24, "▶ 클릭해서 이동", 11, self._fc(col, a),
                         mono=True, anchor="center")
            self.buttons.append(dict(x=cx - rx - 10, y=cy - ry - 10, w=rx * 2 + 20, h=ry * 2 + 20,
                                     key=("gate", i),
                                     cb=(lambda n=cbname: getattr(self, n)())))

        self.txt(WIN_W / 2, WIN_H - 18, "[E] 형상해석   ·   [F] 서재   ·   [R] 편성", 11,
                 self._fc(MUT, a), mono=True, anchor="center")

    # ================================================================
    # 아이템 / 인벤토리 (인벤토리 패치)
    # ================================================================
    def add_item(self, item_id, n=1):
        inv = self.__dict__.setdefault("inventory", {})
        inv[item_id] = inv.get(item_id, 0) + n
        return inv[item_id]

    def drop_loot(self, target, queued):
        """적 처치 드랍.
        PHASE 1~2: 빛바랜 소망 1~3개 / PHASE 3~4: 희미한 소망 1~3개 /
        PHASE 3 이후: 빛바랜 소망 50% 확률로 4~6개 추가."""
        drops = []
        if self.phase in LOOT_PHASES:
            drops.append(("faded_wish", random.randint(*LOOT_RANGE)))
        elif self.phase in DIM_LOOT_PHASES:
            drops.append(("dim_wish", random.randint(*LOOT_RANGE)))
        if self.phase > max(LOOT_PHASES) and random.random() < LATE_FADED_CHANCE:
            drops.append(("faded_wish", random.randint(*LATE_FADED_RANGE)))
        dy = -48
        for iid, n in drops:
            total = self.add_item(iid, n)
            item = ITEMS[iid]
            col = ITEM_TIER_COLOR[item["tier"]]
            queued.append(("적 처치 보상: %s +%d (보유 %d개)" % (item["name"], n, total), col))
            self.fx_number(target.id, "+%d %s" % (n, item["name"]), col, 15, dy=dy)
            dy -= 18

    def toggle_inventory(self):
        if self.inv_open:
            self.close_inventory()
            return
        if (getattr(self, "title_screen", False) or self.modal or self.admin
                or self.admin_kill_pending or self.gacha_open or self.codex_open
                or self.state == "augment_pick"):
            return
        self.inv_open = True
        self.inv_sel = 0
        self.render()

    def close_inventory(self):
        self.inv_open = False
        self.render()

    def inv_select(self, k):
        self.inv_sel = k
        self.render()

    def _inv_wrap(self, text, font, maxw):
        out = []
        for para in text.split("\n"):
            cur = ""
            for ch in para:
                if cur and font.measure(cur + ch) > maxw:
                    cut = cur.rfind(" ")
                    if cut > len(cur) * 0.6:
                        out.append(cur[:cut])
                        cur = cur[cut + 1:]
                    else:
                        out.append(cur)
                        cur = ""
                cur += ch
            out.append(cur)
        return out


    def render_inventory(self):
        if not self.inv_open:
            return
        self.buttons = []     # 뒤쪽 버튼이 눌리지 않도록 교체
        cv = self.canvas
        cv.create_rectangle(0, 0, WIN_W, WIN_H, fill="#000000", outline="",
                            stipple="gray75", tags="ui")
        pw, ph = 860, 520
        px, py = (WIN_W - pw) / 2, 150
        accent = ITEM_TIER_COLOR[1]
        cv.create_rectangle(px + 5, py + 5, px + pw + 5, py + ph + 5,
                            fill="#05070A", outline="", stipple="gray50", tags="ui")
        cv.create_rectangle(px, py, px + pw, py + ph, fill=PANEL, outline=accent,
                            width=2, tags="ui")
        cv.create_rectangle(px, py, px + pw, py + 5, fill=accent, outline="", tags="ui")
        self.txt(px + 24, py + 16, "인벤토리", 28, TXT, bold=True)
        self.txt(px + pw - 24, py + 26, "[TAB] / [ESC] 닫기", 11, MUT, mono=True, anchor="ne")
        cv.create_line(px + 24, py + 62, px + pw - 24, py + 62, fill=BRD, tags="ui")

        inv = self.__dict__.get("inventory", {})
        owned = [i for i in ITEM_ORDER if inv.get(i, 0) > 0]
        self.txt(px + 24, py + 70, "소지품 %d종" % len(owned), 11, MUT, mono=True)

        cols, rows, sz, gap = 5, 4, 76, 10
        gx, gy = px + 24, py + 92
        for n in range(cols * rows):
            sx = gx + (n % cols) * (sz + gap)
            sy = gy + (n // cols) * (sz + gap)
            if n < len(owned):
                it = ITEMS[owned[n]]
                hov = self.hover == ("inv", n)
                sel = self.inv_sel == n
                tc = ITEM_TIER_COLOR.get(it["tier"], MUT)
                cv.create_rectangle(sx, sy, sx + sz, sy + sz,
                                    fill=PANEL2 if (hov or sel) else PANEL,
                                    outline=SPC if sel else tc, width=3 if sel else (2 if hov else 1),
                                    tags="ui")
                self.draw_item_icon(sx + sz / 2, sy + sz / 2 - 4, sz, it)
                self.txt(sx + sz - 6, sy + sz - 5, "x%d" % inv[owned[n]], 12, TXT, mono=True,
                         bold=True, anchor="se")
                self.buttons.append(dict(x=sx, y=sy, w=sz, h=sz, key=("inv", n),
                                         cb=(lambda k=n: self.inv_select(k))))
            else:
                cv.create_rectangle(sx, sy, sx + sz, sy + sz, fill="#14181E", outline=BRD,
                                    tags="ui")

        # 상세 정보 (호버 중인 슬롯 → 없으면 클릭해 고정한 슬롯)
        dx = gx + cols * (sz + gap) + 4
        dw = px + pw - 24 - dx
        dy, dh = gy, rows * (sz + gap) - gap
        cv.create_rectangle(dx, dy, dx + dw, dy + dh, fill=PANEL2, outline=BRD, tags="ui")
        di = self.hover[1] if (isinstance(self.hover, tuple) and self.hover[0] == "inv") \
            else self.inv_sel
        if not owned:
            self.txt(dx + dw / 2, dy + dh / 2, "보유한 아이템이 없다.", 13, MUT, anchor="center")
        else:
            di = max(0, min(di, len(owned) - 1))
            iid = owned[di]
            it = ITEMS[iid]
            tc = ITEM_TIER_COLOR.get(it["tier"], MUT)
            self.draw_item_icon(dx + 46, dy + 50, 76, it)
            nf = self.font(20, bold=True)
            self.txt(dx + 92, dy + 22, it["name"], 20, TXT, bold=True)
            self.txt(dx + 92 + nf.measure(it["name"]) + 10, dy + 28, "[%d T]" % it["tier"], 14,
                     tc, mono=True, bold=True)
            self.txt(dx + 92, dy + 56, "보유 %d개" % inv[iid], 12, MUT, mono=True)
            cv.create_line(dx + 16, dy + 98, dx + dw - 16, dy + 98, fill=BRD, tags="ui")
            ty = dy + 112
            df = self.font(14)
            for line in self._inv_wrap(it["desc"], df, dw - 32):
                self.txt(dx + 16, ty, line, 14, TXT)
                ty += df.metrics("linespace") + 4
            ty += 14
            ff = self.font(13)
            for line in self._inv_wrap(it["flavor"], ff, dw - 32):
                self.txt(dx + 16, ty, line, 13, MUT)
                ty += ff.metrics("linespace") + 4

        self.hbtn(px + pw / 2 - 70, py + ph - 46, 140, 32, "닫기 (TAB)", self.close_inventory, MUT)


    def find_aspect(self, aid):
        """형상 id 로 형상 데이터를 찾는다 (숨김 형상 포함)."""
        return next((a for a in ALL_ASPECTS if a["id"] == aid), None)


    # ================================================================
    # 언더보스/C 스킬 이펙트 — '거미집 엄지 아비 로쟈' 풍 (황금 / 진홍)
    # ================================================================
    def _ub_sparkle(self, cx, cy, n=8, spread=110, size=(7, 15), dur=0.7, cols=None):
        """네 갈래 반짝임(✦)이 커졌다가 사라진다."""
        cv = self.canvas
        cols = cols or (UB_GOLD_L, UB_GOLD, UB_CRIM)
        items, data = [], []
        for _ in range(n):
            a = random.random() * math.tau
            d = random.uniform(0.25, 1.0) * spread
            col = random.choice(cols)
            it = cv.create_polygon(cx, cy, cx, cy, cx, cy, cx, cy, cx, cy, cx, cy, cx, cy, cx, cy,
                                   fill=col, outline="", state="hidden", tags="fx")
            items.append(it)
            data.append((it, cx + math.cos(a) * d, cy + math.sin(a) * d * 0.8,
                         random.uniform(*size), random.uniform(0, 0.4), col))

        def up(p, e):
            for it, px, py, s, d0, col in data:
                q = (p - d0) / max(0.05, 1.0 - d0)
                if q <= 0.0 or q >= 1.0:
                    cv.itemconfig(it, state="hidden")
                    continue
                r = s * math.sin(math.pi * q)
                w = r * 0.28
                cv.coords(it, px, py - r, px + w, py - w, px + r, py, px + w, py + w,
                          px, py + r, px - w, py + w, px - r, py, px - w, py - w)
                cv.itemconfig(it, state="normal", fill=lerp_color(col, BG, q * q))

        self.add_fx(items, dur, up)

    def _ub_stroke(self, path, col_main, col_glow, dur=0.3, width=1.0):
        """path(꺾은선)를 따라 머리가 달리고 꼬리가 따라붙으며 사라지는 3겹 베기 궤적."""
        cv = self.canvas
        x0, y0 = path[0]

        def mk(col, w):
            return cv.create_line(x0, y0, x0, y0, fill=col, width=w * width, capstyle="round",
                                  smooth=True, state="hidden", tags="fx")

        layers = [(mk(col_glow, 17), 0.75, col_glow), (mk(col_main, 8), 0.58, col_main),
                  (mk(WHITE, 3), 0.42, WHITE)]

        def up(p, e):
            head = min(1.0, p / 0.58)
            fade = max(0.0, (p - 0.58) / 0.42)
            for ln, L, col in layers:
                tail = max(0.0, head - L) if p < 0.58 else (1.0 - L) + L * fade
                seg = self._fx_poly_slice(path, tail, head)
                if seg:
                    cv.coords(ln, *seg)
                    cv.itemconfig(ln, state="normal", fill=lerp_color(col, BG, fade * 0.9))
                else:
                    cv.itemconfig(ln, state="hidden")

        self.add_fx([l[0] for l in layers], dur, up)

    def _ub_crescent(self, cx, cy, rx, ry, a0, span, tilt, col_main, col_glow, dur=0.3, width=1.0):
        """타원 궤도를 도는 회전 베기 한 줄기."""
        ct, st = math.cos(tilt), math.sin(tilt)
        path = []
        for i in range(23):
            a = a0 + span * i / 22.0
            x, y = math.cos(a) * rx, math.sin(a) * ry
            path.append((cx + x * ct - y * st, cy + x * st + y * ct))
        self._ub_stroke(path, col_main, col_glow, dur, width)


    # ================================================================
    # 큰누님/N 스킬 이펙트 (보라 / 주황) — bsx 패치
    # ================================================================
    def _bsx_ease(self, v):
        v = max(0.0, min(1.0, v))
        return 1 - (1 - v) ** 3

    def _bsx_ring(self, cx, cy, col, r0=14, r1=150, dur=0.45, width=5, squash=0.62):
        cv = self.canvas
        ring = cv.create_oval(cx, cy, cx, cy, outline=col, width=width, tags="fx")

        def up(p, e):
            r = r0 + (r1 - r0) * self._bsx_ease(p)
            cv.coords(ring, cx - r, cy - r * squash, cx + r, cy + r * squash)
            cv.itemconfig(ring, outline=lerp_color(col, BG, p), width=max(1, width * (1 - p * 0.8)))

        self.add_fx([ring], dur, up)


    def _bsx_veil(self, col, dur=0.4, stipple="gray25"):
        cv = self.canvas
        veil = cv.create_rectangle(0, 0, WIN_W, WIN_H, fill=col, outline="", stipple=stipple, tags="fx")

        def up(p, e):
            cv.itemconfig(veil, stipple=stipple if p < 0.45 else "gray12",
                          fill=lerp_color(col, BG, max(0.0, (p - 0.45) / 0.55)))

        self.add_fx([veil], dur, up)

    def _bsx_sunburst(self, cx, cy, cols, n=14, rmin=26, rmax=150, dur=0.5):
        """주황 선버스트 — 중심에서 쐐기가 퍼져나간다."""
        cv = self.canvas
        items, data = [], []
        for i in range(n):
            a = i * math.tau / n + random.uniform(-0.08, 0.08)
            col = cols[i % len(cols)]
            it = cv.create_polygon(cx, cy, cx, cy, cx, cy, fill=col, outline="", tags="fx")
            items.append(it)
            data.append((it, a, math.tau / n * 0.34, random.uniform(0.75, 1.0), col))

        def up(p, e):
            grow = self._bsx_ease(p * 2.2)
            fade = max(0.0, (p - 0.4) / 0.6)
            for it, a, w, k, col in data:
                r1 = rmin + (rmax * k - rmin) * grow
                r0 = rmin + (r1 - rmin) * fade * 0.85
                cv.coords(it, cx + math.cos(a - w) * r0, cy + math.sin(a - w) * r0 * 0.8,
                          cx + math.cos(a) * r1, cy + math.sin(a) * r1 * 0.8,
                          cx + math.cos(a + w) * r0, cy + math.sin(a + w) * r0 * 0.8)
                cv.itemconfig(it, fill=lerp_color(col, BG, fade))

        self.add_fx(items, dur, up)


    # ================================================================
    # 환상(幻想) — 궁극기 시스템
    # ================================================================
    def ult_charge(self, u, sp):
        """스킬 포인트를 소비한 만큼 환상도 충전."""
        ult = ULTIMATES.get(u.id)
        if not ult or u.side != "ally" or sp <= 0:
            return
        before = u.ult_gauge
        u.ult_gauge = min(100, u.ult_gauge + sp * ULT_GAIN_PER_SP)
        gained = u.ult_gauge - before
        if gained > 0:
            self.fx_number(u.id, "환상 +%d%%" % gained, ult["color"], 13, dy=-48)
            if before < ult["cost"] <= u.ult_gauge:
                self.log("%s의 환상도가 %d%%에 도달했다 — 환상 [%s] 사용 가능!" %
                         (u.name, ult["cost"], ult["name"]), ult["color"])

    def ult_ready(self, u):
        """(사용 가능 여부, 표시 문구)"""
        ult = ULTIMATES.get(u.id)
        if not ult:
            return False, ""
        if u.broken:
            return False, "격파 상태 — 사용 불가"
        if u.ult_use_round is not None and self.round <= u.ult_use_round + ULT_COOLDOWN:
            left = u.ult_use_round + ULT_COOLDOWN - self.round + 1
            return False, "재사용 대기 %d턴" % left
        if u.ult_gauge < ult["cost"]:
            return False, "환상도 %d%% / %d%%" % (u.ult_gauge, ult["cost"])
        return True, "READY %d%% · 격파체력 -%d" % (u.ult_gauge, ult["brk"])

    def choose_ultimate(self):
        if self.state != "plan" or self.busy or not self.acting:
            return
        u = self.acting
        ult = ULTIMATES.get(u.id)
        ok, _why = self.ult_ready(u)
        if not ult or not ok:
            return
        self.pending = dict(type="ultimate", side="enemy", ult=ult)
        self.status_msg = "환상 [%s] — 대상을 선택하세요." % ult["name"]
        self.render()

    def ult_pay_break(self, u, ult):
        """환상 사용으로 소비되는 격파체력 — 0 이 되면 격파 상태에 빠진다."""
        amt = ult.get("brk", 0)
        if amt <= 0 or u.broken or not u.alive:
            return
        u.brk = max(0, u.brk - amt)
        self.fx_number(u.id, "격파 -%d" % amt, BRKC, 16, dy=-30)
        self.log("[환상] %s의 격파체력 -%d (%d/%d)." % (u.name, amt, u.brk, u.max_brk), BRKC)
        if u.brk == 0:
            u.broken = True
            u.broken_skips = 1
            self.log("💥 %s은(는) 환상의 반동으로 격파 상태에 빠졌다!" % u.name, BRKC)
            self.fx_break(u.id)

    def execute_ultimate(self, u, plan, done):
        ult = plan.get("ult") or ULTIMATES.get(u.id)
        t = self.valid_target(u, plan, "enemy")
        if not ult or not t or t.side != "enemy":
            self.log("%s의 환상은 목표를 잃었다." % u.name, MUT)
            self.schedule(300, done)
            return
        self.log("%s — 환상 [%s]" % (u.name, ult["name"]), ult["color"])
        cut_ms = self.fx_ult_cutscene(u, ult)

        def after(dealt):
            self.log("%s의 환상 [%s]! %s에게 %d 피해." % (u.name, ult["name"], t.name, dealt), ult["color"])
            if t.alive and ult.get("bloom"):
                t.bloom_turns = max(t.bloom_turns, ult["bloom"])
                self.fx_number(t.id, "개화 %d" % t.bloom_turns, ult["color"], 20, dy=-30)
                self.log("[개화] %s — 받는 피해 20%% 증가 (남은 %d턴)." % (t.name, t.bloom_turns), ult["color"])
            self.ult_pay_break(u, ult)
            self.schedule(450, done)

        def strike():
            ms = self.fx_rose_of_sharon(u.id, t.id)
            self.schedule(ms, lambda: self.apply_damage(u, t, ult["dmg"], "heavy", after))

        self.schedule(cut_ms, strike)

    # ---------------- 컷씬 (이미지가 없으면 자리표시) ----------------
    def fx_ult_cutscene(self, u, ult):
        """레터박스 + 대각선 타이틀 밴드 + 속도선 + 꽃잎 + 컷인 자리. 끝나는 시각(ms)을 돌려준다."""
        cv = self.canvas
        col, cd, cl = ult["color"], ult["color_d"], ult["color_l"]
        dur = 1.9
        ease = self._bsx_ease
        items = []

        def add(it):
            items.append(it)
            return it

        veil = add(cv.create_rectangle(0, 0, WIN_W, WIN_H, fill="#000000", outline="",
                                       stipple="gray50", tags="fx"))
        top = add(cv.create_rectangle(0, 0, WIN_W, 0, fill="#000000", outline="", tags="fx"))
        bot = add(cv.create_rectangle(0, WIN_H, WIN_W, WIN_H, fill="#000000", outline="", tags="fx"))
        streaks = []
        for _ in range(18):
            y = random.uniform(110, 700)
            ln = add(cv.create_line(0, y, 0, y, fill=random.choice((cl, col, WHITE)),
                                    width=random.choice((1, 2, 3)), tags="fx"))
            streaks.append((ln, y, random.uniform(160, 460), random.uniform(0, 0.6)))
        band = add(cv.create_polygon(*([0] * 8), fill=cd, outline=cl, width=3, tags="fx"))
        accent = add(cv.create_polygon(*([0] * 8), fill=col, outline="", tags="fx"))
        t_sh = add(cv.create_text(0, 0, text=ult["title_en"], fill="#000000",
                                  font=(self.fm, 50, "bold"), anchor="w", tags="fx"))
        t_main = add(cv.create_text(0, 0, text=ult["title_en"], fill=WHITE,
                                    font=(self.fm, 50, "bold"), anchor="w", tags="fx"))
        t_sub = add(cv.create_text(0, 0, text="환상  ·  %s" % ult["name"], fill=cl,
                                   font=(self.ff, 20, "bold"), anchor="w", tags="fx"))
        t_who = add(cv.create_text(0, 0, text="%s" % u.name, fill=col,
                                   font=(self.fm, 16, "bold"), anchor="w", tags="fx"))
        # 컷인 자리
        fx0, fy0, fx1, fy1 = 650, 126, 985, 704
        frame = add(cv.create_rectangle(fx0, fy0, fx1, fy1, fill="#0B0A10", outline=cl, width=3,
                                        state="hidden", tags="fx"))
        pic = None
        img = None
        fname = ULT_PORTRAITS.get(u.id)
        if fname:
            img = self._char_image(fname)
        if img:
            sc = getattr(cv, "s", 1.0)
            pic = add(cv.create_image((fx0 + fx1) / 2 - img.width() / sc / 2,
                                      (fy0 + fy1) / 2 - img.height() / sc / 2,
                                      image=img, anchor="nw", state="hidden", tags="fx"))
        letter = add(cv.create_text((fx0 + fx1) / 2, (fy0 + fy1) / 2 - 20, text=u.id, fill=col,
                                    font=(self.fm, 150, "bold"), state="hidden", tags="fx"))
        note = add(cv.create_text((fx0 + fx1) / 2, fy1 - 30, text="CUT-IN 이미지 준비 중", fill=MUT,
                                  font=(self.fm, 11), state="hidden", tags="fx"))
        petals = []
        for _ in range(16):
            it = add(cv.create_polygon(*([0] * 8), fill=random.choice((col, cl, cd)), outline="",
                                       tags="fx"))
            petals.append((it, random.uniform(0, WIN_W), random.uniform(0, WIN_H),
                           random.uniform(0.5, 1.4), random.uniform(5, 10), random.uniform(0, 6.28)))
        flash = add(cv.create_rectangle(0, 0, WIN_W, WIN_H, fill=WHITE, outline="",
                                        stipple="gray50", state="hidden", tags="fx"))

        def up(p, e):
            fade = max(0.0, (p - 0.9) / 0.1)
            bh = 96 * ease(p / 0.14)
            cv.coords(top, 0, 0, WIN_W, bh)
            cv.coords(bot, 0, WIN_H - bh, WIN_W, WIN_H)
            s = ease((p - 0.06) / 0.22)
            off = (1 - s) * -(WIN_W + 200)
            cv.coords(band, -80 + off, 380, WIN_W + 80 + off, 320, WIN_W + 80 + off, 500, -80 + off, 560)
            cv.coords(accent, -80 + off, 560, WIN_W + 80 + off, 500, WIN_W + 80 + off, 518, -80 + off, 578)
            tx_ = 56 + off * 0.55
            cv.coords(t_sh, tx_ + 4, 428 + 4)
            cv.coords(t_main, tx_, 428)
            cv.coords(t_sub, tx_ + 4, 484)
            cv.coords(t_who, tx_ + 4, 350)
            for ln, y, L, d0 in streaks:
                q = ((p - d0) / 0.4) % 1.0 if p > d0 else 0.0
                x0 = -L + (WIN_W + 2 * L) * q
                cv.coords(ln, x0, y, x0 + L, y)
            for it, px0, py0, sp, sz, ph in petals:
                px = (px0 - 520 * p * sp) % (WIN_W + 80) - 40
                py = (py0 + 260 * p * sp) % WIN_H
                rot = ph + p * 8 * sp
                cv.coords(it, px + math.cos(rot) * sz * 1.6, py + math.sin(rot) * sz * 1.6,
                          px + math.cos(rot + 1.57) * sz, py + math.sin(rot + 1.57) * sz,
                          px - math.cos(rot) * sz * 1.2, py - math.sin(rot) * sz * 1.2,
                          px + math.cos(rot - 1.57) * sz, py + math.sin(rot - 1.57) * sz)
            if s > 0.55:
                cv.itemconfig(frame, state="normal")
                if pic:
                    cv.itemconfig(pic, state="normal")
                else:
                    cv.itemconfig(letter, state="normal")
                    cv.itemconfig(note, state="normal")
            if fade > 0:
                cv.itemconfig(flash, state="normal", stipple="gray50" if fade < 0.5 else "gray25")
                for it, c0 in ((t_main, WHITE), (t_sub, cl), (t_who, col)):
                    cv.itemconfig(it, fill=lerp_color(c0, BG, fade))

        self.add_fx(items, dur, up)
        beep([(392, 70), (587, 70), (784, 100), (1175, 220)], self.sound)
        self.root.after(int(dur * 380), lambda: self.fx_flash(u.id, col, "gray50"))
        return int(dur * 1000)

    # ---------------- 로즈 오브 샤론 이펙트 ----------------
    def fx_petal_stream(self, src, tgt, n=28, dur=0.9):
        """시전자에게서 대상으로 장미 꽃잎이 휘감겨 날아간다."""
        cv = self.canvas
        sx, sy = self.center_of(src)
        tx, ty = self.center_of(tgt)
        items, data = [], []
        for _ in range(n):
            col = random.choice((ROSE, ROSE_L, ROSE_D))
            it = cv.create_polygon(*([sx, sy] * 4), fill=col, outline="", state="hidden", tags="fx")
            items.append(it)
            data.append((it, random.uniform(0, 0.4), random.uniform(-90, 90), random.uniform(5, 9),
                         col, random.uniform(0, 6.28)))

        def up(p, e):
            for it, d0, off, sz, col, ph in data:
                q = (p - d0) / 0.55
                if q <= 0.0 or q >= 1.0:
                    cv.itemconfig(it, state="hidden")
                    continue
                q = self._bsx_ease(q)
                mx, my = (sx + tx) / 2, min(sy, ty) - 120 + off * 0.4
                x = (1 - q) ** 2 * sx + 2 * (1 - q) * q * mx + q * q * tx
                y = (1 - q) ** 2 * sy + 2 * (1 - q) * q * my + q * q * ty + off * math.sin(q * math.pi) * 0.5
                rot = ph + q * 9
                cv.coords(it, x + math.cos(rot) * sz * 1.6, y + math.sin(rot) * sz * 1.6,
                          x + math.cos(rot + 1.57) * sz, y + math.sin(rot + 1.57) * sz,
                          x - math.cos(rot) * sz * 1.2, y - math.sin(rot) * sz * 1.2,
                          x + math.cos(rot - 1.57) * sz, y + math.sin(rot - 1.57) * sz)
                cv.itemconfig(it, state="normal", fill=lerp_color(col, BG, max(0.0, (q - 0.8) / 0.2)))

        self.add_fx(items, dur, up)

    def fx_rose_bloom(self, uid, dur=1.1):
        """대상 위에서 장미가 겹겹이 피어난다."""
        cv = self.canvas
        cx, cy = self.center_of(uid)
        cols = (ROSE, ROSE_D, ROSE_L)
        layers = [(6, 30, 20), (6, 54, 28), (8, 82, 36)]       # (꽃잎 수, 반지름, 크기)
        petals = []
        for li, (n, R, S) in enumerate(layers):
            for k in range(n):
                it = cv.create_polygon(*([cx, cy] * 12), fill=cols[li], outline=ROSE_L, width=1, tags="fx")
                petals.append((it, k * math.tau / n + li * 0.35, R, S, li))
        core = cv.create_oval(cx, cy, cx, cy, fill=ROSE_L, outline=WHITE, width=2, tags="fx")
        items = [p[0] for p in petals] + [core]

        def up(p, e):
            g = self._bsx_ease(p / 0.6)
            fade = max(0.0, (p - 0.8) / 0.2)
            for it, a, R, S, li in petals:
                aa = a + p * 1.2 * (1 if li % 2 == 0 else -1)
                r = R * g
                px, py = cx + math.cos(aa) * r, cy + math.sin(aa) * r * 0.7
                w, h = S * g, S * 0.55 * g
                pts = []
                for j in range(12):
                    tt = j * math.tau / 12
                    lx, ly = math.cos(tt) * w, math.sin(tt) * h
                    pts.append(px + lx * math.cos(aa) - ly * math.sin(aa))
                    pts.append(py + (lx * math.sin(aa) + ly * math.cos(aa)) * 0.7)
                cv.coords(it, *pts)
                cv.itemconfig(it, fill=lerp_color(cols[li], BG, fade), outline=lerp_color(ROSE_L, BG, fade))
            cr = 16 * g
            cv.coords(core, cx - cr, cy - cr * 0.8, cx + cr, cy + cr * 0.8)
            cv.itemconfig(core, fill=lerp_color(ROSE_L, BG, fade), outline=lerp_color(WHITE, BG, fade))

        self.add_fx(items, dur, up)
        beep([(523, 40), (659, 40), (784, 60)], self.sound)

    def fx_rose_of_sharon(self, src, tgt):
        """꽃잎이 휘감겨 날아가 → 장미 개화 → 대형 베기 → 폭발. 피해가 들어갈 시점(ms)을 돌려준다."""
        tx, ty = self.center_of(tgt)
        self.fx_flash(src, ROSE, "gray50")
        self.fx_petal_stream(src, tgt)
        self.root.after(380, lambda: self.fx_rose_bloom(tgt))

        def cut():
            self._ub_crescent(tx, ty, 190, 116, math.radians(200), math.radians(250), -0.35,
                              ROSE_L, ROSE, 0.45, 1.8)
            self._ub_crescent(tx, ty, 140, 84, math.radians(25), math.radians(230), 0.3,
                              WHITE, ROSE_D, 0.4, 1.3)
            beep([(300, 40), (200, 70)], self.sound)

        def burst():
            self._bsx_sunburst(tx, ty, (ROSE, ROSE_D, ROSE_L), 18, 26, 190, 0.6)
            self._bsx_ring(tx, ty, ROSE_L, 14, 220, 0.6, 6)
            self._bsx_veil(ROSE_D, 0.4, "gray25")
            self.fx_particles(tgt, ROSE, n=34, spread=210, dur=0.8, size=5)
            self.fx_particles(tgt, ROSE_L, n=18, spread=150, dur=0.8, size=3)
            self.fx_flash(tgt, WHITE, "gray50")
            self.shakes[tgt] = 0.55
            beep([(220, 60), (440, 80), (880, 140)], self.sound)

        self.root.after(980, cut)
        self.root.after(1150, burst)
        return 1200


    # ================================================================
    # ★★★ Orchestra/D (형상해석 획득 형상 — 오케스트라 패치)
    # ================================================================
    def is_orch(self, unit):
        return unit.side == "ally" and unit.aspect_id == "d_orchestra"

    def orch_reset(self, u):
        u.orch_aud = 0.0
        u.orch_amt = 1
        u.orch_finale = 0
        u.orch_finale_uses = 0
        u.orch_ring = 0
        u.orch_break_immune = False

    def orch_skills(self, u):
        """관객 수치에 따라 스킬 1/2/3 이 바뀐다. 피날레 중에는 스킬 3 자리가 [피날레]."""
        aud = u.orch_aud
        s1 = ORCH_S1B if aud >= ORCH_REQ["orch_s1b"] else ORCH_S1
        s2 = ORCH_S2B if aud >= ORCH_REQ["orch_s2b"] else ORCH_S2
        if u.orch_finale > 0:
            s3 = ORCH_FINALE
        elif aud >= ORCH_REQ["orch_s3b"]:
            s3 = ORCH_S3B
        else:
            amt = max(1, min(6, u.orch_amt))
            dmg = ORCH_S3_BASE + ORCH_S3_PER_SP * (amt - 1)
            s3 = dict(ORCH_S3, cost=amt, dmg=dmg,
                      desc="소모 SP %d (버튼 연타로 1~6) · 지정한 적에게 %d 피해%s · 관객 +%d" % (
                          amt, dmg, " · 모든 적 공격" if amt >= 3 else "", amt))
        return [s1, s2, s3]

    def orch_mash(self, idx):
        """포르티시모 — 버튼을 누를 때마다 소모 SP 가 1 늘어난다 (최대 6, 넘으면 1 로)."""
        u = self.acting
        cur = self.pending["skill"]["cost"] if (self.pending and self.pending.get("mash")) else 0
        amt = cur + 1
        if amt > min(6, u.sp):
            amt = 1
        u.orch_amt = amt
        sk = self.skills_for(u)[idx]
        self.pending = dict(type="skill", idx=idx, skill=sk, side="enemy", mash=True)
        self.status_msg = "포르티시모 소모 SP %d" % amt
        self.render()

    def orch_gain_aud(self, u, n):
        if n <= 0 or not u.alive:
            return
        before = u.orch_aud
        u.orch_aud = min(ORCH_AUD_MAX, u.orch_aud + n)
        gained = u.orch_aud - before
        if gained <= 0:
            return
        self.fx_number(u.id, "관객 +%g" % gained, ORCH_GOLD, 14, dy=-34)
        names = {5: "레가토", 8: "포르테", 10: "다카포 알 피네"}
        for need in (5, 8, 10):
            if before < need <= u.orch_aud:
                self.log("관객 %d — 스킬이 [%s]로 변경됐다." % (need, names[need]), ORCH_GOLD)
        if before < ORCH_AUD_MAX <= u.orch_aud:
            self.log("관객이 가득 찼다 — 전투불능에 이르는 피해를 받으면 [피날레]에 진입한다.", ORCH_GOLD)

    def orch_enter_finale(self, u):
        """관객 20 — 전투불능에 이르는 피해를 받으면 피날레에 진입한다."""
        u.orch_finale = ORCH_FINALE_TURNS
        u.orch_finale_uses = 0
        u.orch_ring = 0
        if u.broken:                                   # 격파 상태였다면 해제
            u.broken = False
            u.broken_skips = 0
            u.brk = u.max_brk
        u.orch_break_immune = True                     # 이번 전투 동안 격파 면역
        u.plan = None                                  # 이번 턴 미리 정한 행동은 취소
        self.log("♪ %s — 관객의 환호 속에서 [피날레] 진입! 전투불능이 되지 않는다. (격파 면역 · 피날레 스킬만 사용 가능)" %
                 u.name, STAR_COLOR[3])
        self.fx_flash(u.id, STAR_COLOR[3], "gray50")
        self.fx_number(u.id, "FINALE", STAR_COLOR[3], 22, dy=-34)
        beep([(523, 70), (784, 80), (1046, 140), (1568, 200)], self.sound)

    def orch_end_finale(self, u, why):
        u.orch_finale = 0
        u.orch_ring = 0
        if u.alive:
            u.hp = 0
            self.log("%s의 피날레가 막을 내렸다 (%s) — 전투불능." % (u.name, why), STAR_COLOR[3])
            self.fx_number(u.id, "전투불능", MUT, 18)
            self.fx_flash(u.id, MUT, "gray50")

    def orch_round_start(self, u):
        if u.orch_finale > 0:
            u.orch_finale -= 1
            if u.orch_finale == 0:
                self.orch_end_finale(u, "4턴 경과")

    # ---------------- 실행 ----------------
    def execute_orchestra(self, u, sk, plan, done):
        kind = sk["kind"]
        if kind == "orch_finale":
            self.orch_finale_run(u, sk, done)
            return
        if kind == "orch_s3b":
            self.orch_dacapo(u, sk, done)
            return
        t = self.valid_target(u, plan, "enemy")
        if not t or t.side != "enemy":
            self.log("%s의 [%s]은 목표를 잃었다." % (u.name, sk["name"]), MUT)
            self.schedule(300, done)
            return
        if sk.get("sp_back"):
            got = self.gain_sp(u, sk["sp_back"])
            if got:
                self.fx_number(u.id, "SP +%d" % got, SPC, 15, dy=-12)
        self.orch_gain_aud(u, sk["aud"] if sk.get("aud") is not None else sk["cost"])
        enemies = self.enemies()
        hits = [(t, sk["dmg"])]
        if kind in ("orch_s2", "orch_s2b") and t in enemies:
            i = enemies.index(t)
            for j in (i - 1, i + 1):
                if 0 <= j < len(enemies) and enemies[j].alive:
                    hits.append((enemies[j], sk["splash"]))
        if kind == "orch_s3" and sk["cost"] >= 3:
            hits += [(e, sk["dmg"]) for e in enemies if e.alive and e is not t]
        self.log("%s의 [%s]!" % (u.name, sk["name"]), ORCH_GOLD)
        ms = self.fx_orch_skill(kind, u.id, [h[0].id for h in hits], sk.get("cost", 1))
        self.schedule(ms, lambda: self.orch_hits(u, hits, sk["name"], done))

    def orch_hits(self, u, hits, label, done):
        def step(i):
            if i >= len(hits):
                done()
                return
            tg, amt = hits[i]
            if not tg.alive:
                step(i + 1)
                return
            self.apply_damage(u, tg, amt, "heavy",
                              lambda d, tg=tg, i=i: (
                                  self.log("   └ [%s] %s에게 %d 피해." % (label, tg.name, d), ORCH_GOLD),
                                  step(i + 1)))

        step(0)

    def orch_dacapo(self, u, sk, done):
        """3-2 다카포 알 피네 — 모든 적 65 피해 → 25 고정 격파피해 → 다음 턴 속도 -1."""
        targets = [e for e in self.enemies() if e.alive]
        if not targets:
            self.schedule(300, done)
            return
        got = self.gain_sp(u, sk["sp_back"])
        if got:
            self.fx_number(u.id, "SP +%d" % got, SPC, 15, dy=-12)
        self.orch_gain_aud(u, sk["aud"])
        self.log("%s의 [%s]! 처음으로 돌아가 끝을 맺는다." % (u.name, sk["name"]), ORCH_GOLD)
        ms = self.fx_orch_skill("orch_s3b", u.id, [e.id for e in targets], 6)
        hit = []

        def finish():
            for e in hit:
                if e.alive:
                    self.ub_break_fixed(e, sk["brk"], sk["name"])
                    e.speed_minus = max(e.speed_minus, 1)
                    self.fx_number(e.id, "속도 -1", ORCH_IV, 15, dy=-12)
            self.log("[%s] 적중한 적의 다음 턴 속도 -1." % sk["name"], ORCH_GOLD)
            self.schedule(300, done)

        def step(i):
            if i >= len(targets):
                finish()
                return
            tg = targets[i]
            if not tg.alive:
                step(i + 1)
                return
            hit.append(tg)
            self.apply_damage(u, tg, sk["dmg"], "heavy",
                              lambda d, tg=tg, i=i: (
                                  self.log("   └ [%s] %s에게 %d 피해." % (sk["name"], tg.name, d), ORCH_GOLD),
                                  step(i + 1)))

        self.schedule(ms, lambda: step(0))

    def orch_finale_run(self, u, sk, done):
        """피날레 — 사용할 때마다 효과가 달라진다. 3번째 사용 뒤 전투불능."""
        n = u.orch_finale_uses
        u.orch_finale_uses += 1
        titles = ("ONE MOVEMENT", "TWO MOVEMENT", "FINALE")
        self.fx_orch_title(titles[min(n, 2)])
        self.log("%s: [피날레] %s (%d/3)" % (u.name, titles[min(n, 2)], n + 1), STAR_COLOR[3])

        def seq(targets, dmg, with_break, after):
            def step(i):
                if i >= len(targets):
                    after()
                    return
                tg = targets[i]
                if not tg.alive:
                    step(i + 1)
                    return

                def cb(d, tg=tg, i=i):
                    self.log("   └ [피날레] %s에게 고정피해 %d." % (tg.name, d), STAR_COLOR[3])
                    if with_break and tg.alive and tg.side == "enemy":
                        self.ub_break_fixed(tg, dmg, "피날레")
                    step(i + 1)

                self.fx_orch_hit(tg.id, True)
                self.apply_damage(u, tg, dmg, "heavy", cb, fixed=True, skip_defense=True)

            step(0)

        if n == 0:
            def first():
                u.hp = u.max_hp
                u.brk = u.max_brk
                u.broken = False
                u.broken_skips = 0
                u.orch_ring = 1
                self.fx_heal(u.id, "FULL")
                self.log("%s의 체력과 격파체력이 최대치로 회복됐다." % u.name, HEAL)
                self.schedule(700, done)

            self.schedule(700, first)
            return
        if n == 1:
            targets = [e for e in self.enemies() if e.alive]

            def second():
                u.orch_ring = 2
                seq(targets, 50, True, lambda: self.schedule(300, done))

            self.schedule(700, second)
            return

        def third():
            u.orch_ring = 0
            self.fx_orch_burst(u.id)
            targets = [e for e in self.enemies() if e.alive] + [a for a in self.allies() if a.alive]

            def end():
                self.orch_end_finale(u, "피날레 3회 사용")
                self.schedule(400, done)

            seq(targets, 100, False, end)

        self.schedule(900, third)

    # ---------------- 이펙트 (아이보리 / 금빛 악보) ----------------
    def fx_orch_hit(self, tid, big=False):
        cx, cy = self.center_of(tid)
        self.fx_flash(tid, ORCH_GOLD, "gray50")
        self.fx_particles(tid, ORCH_IV, n=18 if big else 10, spread=130 if big else 95, dur=0.5, size=3)
        self.fx_particles(tid, ORCH_GOLD, n=12 if big else 6, spread=110, dur=0.55, size=4)
        self._bsx_ring(cx, cy, ORCH_IV, 12, 140 if big else 95, 0.42, 4)
        self._ub_sparkle(cx, cy, n=6 if big else 3, spread=90, size=(7, 13), dur=0.55,
                         cols=(ORCH_IV, ORCH_GOLD, WHITE))
        self.shakes[tid] = 0.4 if big else 0.22
        beep([(random.randint(520, 880), 24)], self.sound)

    def fx_orch_staff(self, tid, dur=0.55, span=420, amp=1.0, notes=7, tilt=0.0):
        """다섯 줄 악보가 파도치며 대상을 가로지르고, 음표가 하나씩 떠오른다."""
        cv = self.canvas
        cx, cy = self.center_of(tid)
        gaps = (-18, -9, 0, 9, 18)
        lines = [cv.create_line(cx, cy, cx, cy, cx, cy, fill=ORCH_IV, width=2, smooth=True,
                                state="hidden", tags="fx") for _ in gaps]
        nts = []
        for _ in range(notes):
            head = cv.create_oval(cx, cy, cx, cy, fill=ORCH_GOLD, outline=ORCH_IV, width=1,
                                  state="hidden", tags="fx")
            stem = cv.create_line(cx, cy, cx, cy, fill=ORCH_IV, width=2, state="hidden", tags="fx")
            nts.append((head, stem, random.uniform(0.08, 0.92), random.choice(gaps)))
        items = lines + [n[0] for n in nts] + [n[1] for n in nts]
        ct, st = math.cos(tilt), math.sin(tilt)

        def at(f, gy, p):
            x = -span / 2 + span * f
            y = gy + math.sin(f * 9 + p * 12) * 10 * amp
            return cx + x * ct - y * st, cy + x * st + y * ct

        def up(p, e):
            q = min(1.0, p / 0.6)
            fade = max(0.0, (p - 0.75) / 0.25)
            for ln, gy in zip(lines, gaps):
                pts = []
                for j in range(13):
                    pts.extend(at(j / 12.0 * q, gy, p))
                cv.coords(ln, *pts)
                cv.itemconfig(ln, state="normal", fill=lerp_color(ORCH_IV, BG, fade))
            for head, stem, pos, gy in nts:
                if q < pos:
                    continue
                hx, hy = at(pos, gy, p)
                cv.coords(head, hx - 6, hy - 4.5, hx + 6, hy + 4.5)
                cv.coords(stem, hx + 6, hy, hx + 6, hy - 26)
                cv.itemconfig(head, state="normal", fill=lerp_color(ORCH_GOLD, BG, fade),
                              outline=lerp_color(ORCH_IV, BG, fade))
                cv.itemconfig(stem, state="normal", fill=lerp_color(ORCH_IV, BG, fade))

        self.add_fx(items, dur, up)

    def fx_orch_circle(self, tid, dur=0.8):
        """원형으로 회전하는 악보 — 음표가 대상 주위를 돌며 순환한다."""
        cv = self.canvas
        cx, cy = self.center_of(tid)
        rings = [cv.create_oval(cx, cy, cx, cy, outline=c, width=w, tags="fx")
                 for c, w in ((ORCH_IV, 2), (ORCH_GOLD, 3), (ORCH_IV, 1))]
        nts = []
        for i in range(10):
            head = cv.create_oval(cx, cy, cx, cy, fill=ORCH_GOLD, outline=ORCH_IV, width=1, tags="fx")
            stem = cv.create_line(cx, cy, cx, cy, fill=ORCH_IV, width=2, tags="fx")
            nts.append((head, stem, i * math.tau / 10))
        items = rings + [n[0] for n in nts] + [n[1] for n in nts]

        def up(p, e):
            g = self._bsx_ease(p / 0.35)
            fade = max(0.0, (p - 0.8) / 0.2)
            for k, rg in enumerate(rings):
                rx, ry = (92 + k * 14) * g, (56 + k * 9) * g
                cv.coords(rg, cx - rx, cy - ry, cx + rx, cy + ry)
                cv.itemconfig(rg, outline=lerp_color((ORCH_IV, ORCH_GOLD, ORCH_IV)[k], BG, fade))
            for head, stem, a0 in nts:
                a = a0 + p * math.tau * 1.6
                hx, hy = cx + math.cos(a) * 100 * g, cy + math.sin(a) * 62 * g
                cv.coords(head, hx - 6, hy - 4.5, hx + 6, hy + 4.5)
                cv.coords(stem, hx + 6, hy, hx + 6, hy - 24)
                cv.itemconfig(head, fill=lerp_color(ORCH_GOLD, BG, fade))
                cv.itemconfig(stem, fill=lerp_color(ORCH_IV, BG, fade))

        self.add_fx(items, dur, up)

    def fx_orch_baton(self, src, tid):
        """지휘봉이 시전자에게서 대상을 향해 호를 그린다."""
        sx, sy = self.center_of(src)
        tx, ty = self.center_of(tid)
        mid = ((sx + tx) / 2, min(sy, ty) - 60)
        path = []
        for i in range(17):
            q = i / 16.0
            path.append(((1 - q) ** 2 * sx + 2 * (1 - q) * q * mid[0] + q * q * tx,
                         (1 - q) ** 2 * sy + 2 * (1 - q) * q * mid[1] + q * q * ty))
        self._ub_stroke(path, ORCH_IV, ORCH_GOLD, 0.3, 1.2)

    def fx_orch_skill(self, kind, src, ids, sp=1):
        """스킬별 연출을 시작하고 피해가 들어갈 시점(ms)을 돌려준다."""
        tid = ids[0]
        if kind == "orch_s1":
            self.fx_orch_baton(src, tid)
            self.fx_orch_staff(tid, 0.45, 360, 0.8, 5)
            self.root.after(230, lambda: self.fx_orch_hit(tid, False))
            return 320
        if kind == "orch_s1b":
            self.fx_orch_baton(src, tid)
            self.fx_orch_circle(tid, 0.8)
            self.root.after(520, lambda: self.fx_orch_hit(tid, True))
            return 620
        if kind in ("orch_s2", "orch_s2b"):
            self.fx_orch_baton(src, tid)
            self.fx_orch_staff(tid, 0.6, 520, 1.3, 8)
            self.root.after(300, lambda: self.fx_orch_hit(tid, True))
            for k, other in enumerate(ids[1:]):
                self.root.after(380 + k * 80, lambda o=other: (
                    self.fx_orch_staff(o, 0.45, 300, 0.8, 4), self.fx_orch_hit(o, False)))
            if kind == "orch_s2b":
                self.fx_orch_circle(tid, 0.7)
            return 460
        if kind == "orch_s3":
            n = max(1, sp)
            self.fx_orch_baton(src, tid)
            for k, i in enumerate(ids):
                self.root.after(k * 90, lambda i=i: self.fx_orch_staff(i, 0.6, 360 + 40 * n, 0.8 + 0.2 * n, 4 + n))
            self.root.after(380, lambda: [self.fx_orch_hit(i, n >= 3) for i in ids])
            if n >= 3:
                self.root.after(380, lambda: self._bsx_veil(ORCH_RED, 0.4, "gray12"))
            return 460 + 60 * len(ids)
        # orch_s3b — 다카포 알 피네
        for k, i in enumerate(ids):
            self.root.after(k * 110, lambda i=i, k=k: self.fx_orch_staff(i, 0.65, 560, 1.4, 8,
                                                                             0.12 * (k - 1)))
        self.root.after(180, lambda: self._bsx_veil(ORCH_GOLD, 0.5, "gray12"))
        self.root.after(600, lambda: [self.fx_orch_hit(i, True) for i in ids])
        return 760

    def fx_orch_title(self, text, dur=1.3):
        """화면 가운데에 하얀 글자가 잠깐 떴다 사라진다 (ONE / TWO MOVEMENT, FINALE)."""
        cv = self.canvas
        cx, cy = WIN_W / 2, 300
        shadow = cv.create_text(cx + 3, cy + 3, text=text, fill="#000000",
                                font=(self.fm, 56, "bold"), tags="fx")
        main = cv.create_text(cx, cy, text=text, fill=WHITE, font=(self.fm, 56, "bold"), tags="fx")
        l1 = cv.create_line(cx, cy - 44, cx, cy - 44, fill=WHITE, width=2, tags="fx")
        l2 = cv.create_line(cx, cy + 44, cx, cy + 44, fill=WHITE, width=2, tags="fx")

        def up(p, e):
            a = min(1.0, p / 0.2) * (1.0 - max(0.0, (p - 0.7) / 0.3))
            w = 260 * min(1.0, p / 0.3)
            col = lerp_color(BG, WHITE, a)
            cv.itemconfig(main, fill=col)
            cv.itemconfig(shadow, fill=lerp_color(BG, "#000000", a))
            for ln, yy in ((l1, cy - 44), (l2, cy + 44)):
                cv.coords(ln, cx - w, yy, cx + w, yy)
                cv.itemconfig(ln, fill=col)

        self.add_fx([shadow, main, l1, l2], dur, up)
        beep([(659, 50), (880, 70)], self.sound)

    def fx_orch_burst(self, uid):
        """악장의 원이 사방으로 퍼져나가며 사라진다."""
        cv = self.canvas
        cx, cy = self.center_of(uid)
        rings = [cv.create_oval(cx, cy, cx, cy, outline=c, width=w, tags="fx")
                 for c, w in ((WHITE, 4), (ORCH_IV, 3), (ORCH_GOLD, 3), (ORCH_RED, 2))]

        def up(p, e):
            for k, rg in enumerate(rings):
                q = self._bsx_ease(min(1.0, max(0.0, p * 1.3 - k * 0.12)))
                rx, ry = 40 + 520 * q, 30 + 320 * q
                cv.coords(rg, cx - rx, cy - ry, cx + rx, cy + ry)
                cv.itemconfig(rg, outline=lerp_color((WHITE, ORCH_IV, ORCH_GOLD, ORCH_RED)[k], BG, q))

        self.add_fx(rings, 1.1, up)
        self._bsx_veil(WHITE, 0.45, "gray25")
        beep([(392, 80), (523, 90), (784, 120), (1175, 220)], self.sound)

    def draw_orch_ring(self, x, y, w, h, n):
        """카드 주위를 도는 악장의 원 (피날레 1회 이후 1단 / 2회 이후 2배)."""
        cx, cy = x + w / 2, y + h / 2
        rx, ry = w / 2 - 6, h / 2 - 6
        t = time.monotonic()
        segs = 4 if n <= 1 else 8
        span = math.tau / segs * 0.55
        line_col = lerp_color(PANEL, ORCH_IV, 0.55)
        for s in range(segs):
            a0 = t * 0.9 + s * math.tau / segs
            for k in range(5):
                rr = 1.0 + (k - 2) * 0.03
                pts = []
                for j in range(9):
                    a = a0 + span * j / 8.0
                    pts.extend((cx + math.cos(a) * rx * rr, cy + math.sin(a) * ry * rr))
                self.canvas.create_line(*pts, fill=line_col, width=1, smooth=True, tags="ui")
            am = a0 + span / 2
            nx, ny = cx + math.cos(am) * rx, cy + math.sin(am) * ry
            self.canvas.create_oval(nx - 5, ny - 3.5, nx + 5, ny + 3.5, fill=ORCH_GOLD,
                                    outline=ORCH_IV, tags="ui")

    def toggle_sound(self):
        self.sound = not self.sound
        self.render()

    def on_canvas_resize(self, ev):
        if ev.width < 50 or ev.height < 50:
            return
        self.canvas.set_view(ev.width, ev.height)
        job = self.__dict__.get("_resize_job")
        if job:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        self._resize_job = self.root.after(30, self.render)

    def on_click(self, ev):
        self.canvas.unscale_event(ev)
        if self.admin_kill_pending:
            for uid, (x, y, w, h) in self.card_rects.items():
                if x <= ev.x <= x + w and y <= ev.y <= y + h:
                    self.on_card_click(uid)
                    return
            return
        for b in self.buttons:
            if b["x"] <= ev.x <= b["x"] + b["w"] and b["y"] <= ev.y <= b["y"] + b["h"]:
                b["cb"]()
                return
        if (self.modal or self.overlay or self.admin or self.gacha_open or self.inv_open
                or self.codex_open or self.lobby or self.state == "augment_pick"):
            return
        for uid, (x, y, w, h) in self.card_rects.items():
            if x <= ev.x <= x + w and y <= ev.y <= y + h:
                self.on_card_click(uid)
                return

    def on_motion(self, ev):
        self.canvas.unscale_event(ev)
        moved = abs(ev.x - self.mouse[0]) + abs(ev.y - self.mouse[1]) > 6
        self.mouse = (ev.x, ev.y)
        new = None
        for b in self.buttons:
            if "key" in b and b["x"] <= ev.x <= b["x"] + b["w"] and b["y"] <= ev.y <= b["y"] + b["h"]:
                new = b["key"]
                break
        if (new is None and not self.modal and not self.overlay and not self.admin
                and not self.gacha_open and not self.codex_open and not self.lobby
                and not self.inv_open and self.state != "augment_pick"):
            for uid, (x, y, w, h) in self.card_rects.items():
                if x <= ev.x <= x + w and y <= ev.y <= y + h and self.targetable(self.units[uid]):
                    new = uid
                    break
        if new != self.hover:
            self.hover = new
            self.render()
        elif moved and isinstance(new, tuple):
            self.render()


def main():
    root = tk.Tk()
    NHCBattle(root)
    root.mainloop()


if __name__ == "__main__":
    main()

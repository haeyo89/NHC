#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NHC — 전투 프로토타입 (Python / tkinter 단일 파일)

실행:  python nhc_battle.py
필요:  파이썬 3.8+ (tkinter 포함). 외부 패키지 없음.

이번 갱신에서 바뀐 점
---------------------
1. 페이즈 클리어 증강(1티어) — 일반 페이즈 클리어 보상
   - 웨이브(페이즈)를 클리어하면 5종 중 3개를 무작위로 제시하고 그중 하나를 선택한다.
   - 한 번 고른 증강은 이후 선택지에서 완전히 제외된다(최대 5회 획득).
       · 불굴의 의지   — 모든 아군 최대 체력 +50 (즉시 회복)
       · 강화 훈련     — 모든 아군 기본 공격 피해 +5
       · 전술 재정비   — 지정한 아군 1명의 SP 즉시 최대
       · 파쇄의 기술   — 적에게 입히는 격파피해 +15%
       · 속도의 비기   — 아군 속도 주사위 1 눈 제거 (최솟값 2)
2. 보스 클리어 전용 증강(2티어) — 신규
   - 보스를 잡을 때마다 별도의 5종 중 3개를 제시하고 하나를 선택한다 (1티어와 별개로 관리).
       · 격파 강화     — 모든 아군 최대 격파체력 +50 (즉시 회복)
       · 투사 본능     — 모든 아군 기본 공격 피해 +5 (1티어 강화 훈련과 중첩)
       · 불사의 가호   — 전투당 1회, 아군이 죽기 직전이면 체력 1로 버티는 불사 상태(2턴)에 진입
       · 철벽 방어     — 아군이 받는 모든 피해 -10
       · 생명 강화     — 모든 아군 최대 체력 +50 (1티어 불굴의 의지와 중첩)
3. C 재조정 — 3스킬 '파멸의 예연': 지정한 적이 3턴간 받는 피해 1.5배 (격파 상태와 곱연산 중첩).
4. 연출/색상 — N 3스킬 '진입 저지 저격'(분홍), H 3스킬 '진-걸착'(파란).
5. 어드민 패널 — 전투 중 'maki' 입력으로 열림(ESC 로 닫기). 탭 구조(이동/증강/기타)로 재구성.
   - 이동: 스테이지1(1~5)·보스1(6)·스테이지2(7~11)·보스2(12) 즉시 이동, 아군 상태 완전 복구.
   - 증강: 1티어·2티어 개별 강제 지급 + 각 티어 선택창 강제 호출.
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
import random
import threading
import tkinter as tk
import tkinter.font as tkfont

# ----------------------------------------------------------------------------
# 팔레트 / 레이아웃
# ----------------------------------------------------------------------------
BG = "#12151A"
PANEL = "#1B2027"
PANEL2 = "#20262E"
TXT = "#EDEAE1"
MUT = "#8A919C"
BRD = "#2C333C"
DMG = "#E2603D"
HEAL = "#49B6A4"
BRKC = "#9C8FEC"
SPC = "#E8B24D"
WHITE = "#FFFFFF"
ROSE = "#F45FA6"     # N 3스킬 — 진입 저지 저격
BLUE_H = "#3E8BFF"   # H 3스킬 — 진-걸착
CURSE = "#B34FE0"    # C 3스킬 — 파멸의 예연
COSMIC = "#8E6BFF"   # 보스 '혼돈의 주인'
SHLD = "#725FE0"     # 보호막(shield) 표시색
TURN_GREEN = "#39D778"
TURN_GREEN_DIM = "#1E5838"

ADMIN_CODE = "maki"  # 전투 중 이 문자열을 입력하면 어드민 패널이 열린다
BOSS_PHASE = 6       # 이 배수의 페이즈는 보스전
BOSS_NAME = "혼돈의 주인"
BOSS_ACTIONS = 3     # 보스는 한 라운드에 3번 행동한다 (광역기 라운드는 예외 — 1회만)

WIN_W, WIN_H = 1040, 830
MARGIN = 20
CARD_W = (WIN_W - MARGIN * 2 - 24) // 3
CARD_H = 156
ENEMY_Y = 96
ALLY_Y = 288
PANEL_Y = 462
PANEL_H = 152
LOG_Y = 628
LOG_H = 182

MAX_SP = 6
BOSS_AOE_COST = MAX_SP   # 광역기 [차원 붕괴] 소모 SP — 가득 차면 발동
DICE_PIPS = {
    1: [(0.5, 0.5)],
    2: [(0.28, 0.28), (0.72, 0.72)],
    3: [(0.26, 0.26), (0.5, 0.5), (0.74, 0.74)],
    4: [(0.28, 0.28), (0.72, 0.28), (0.28, 0.72), (0.72, 0.72)],
    5: [(0.28, 0.28), (0.72, 0.28), (0.5, 0.5), (0.28, 0.72), (0.72, 0.72)],
    6: [(0.28, 0.24), (0.72, 0.24), (0.28, 0.5), (0.72, 0.5), (0.28, 0.76), (0.72, 0.76)],
}

# ----------------------------------------------------------------------------
# 효과음 (Windows 한정, 없으면 무음)
# ----------------------------------------------------------------------------
try:
    import winsound

    _HAS_SOUND = True
except Exception:
    _HAS_SOUND = False


def beep(seq, enabled):
    """seq = [(freq, ms), ...]"""
    if not (_HAS_SOUND and enabled):
        return

    def run():
        try:
            for f, d in seq:
                winsound.Beep(int(f), int(d))
        except Exception:
            pass

    threading.Thread(target=run, daemon=True).start()


# ----------------------------------------------------------------------------
# 유틸
# ----------------------------------------------------------------------------
def hex_to_rgb(c):
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    a, b = hex_to_rgb(c1), hex_to_rgb(c2)
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def d6():
    return random.randint(1, 6)


# ----------------------------------------------------------------------------
# 스킬 / 유닛 정의
# ----------------------------------------------------------------------------
N_SKILLS = [
    dict(name="조준 사격", cost=1, kind="attack", dmg=20, fx="bullet", desc="권총형 자세 · 빠른 견제사격"),
    dict(name="관통 저격", cost=3, kind="attack", dmg=30, fx="bullet", desc="저격총 전환 · 관통탄"),
    dict(name="진입 저지 저격", cost=5, kind="attack", dmg=40, fx="snipe", accent=ROSE,
         desc="조준경 락온 후 급소 관통 (분홍빛 섬광)"),
]
H_SKILLS = [
    dict(name="베기", cost=2, kind="attack", dmg=25, fx="slash", desc="한 호흡에 베어넘기는 검격"),
    dict(name="연속 참격", cost=4, kind="attack", dmg=35, fx="slash2", desc="두 번 베어넘기는 강공"),
    dict(name="진-걸착", cost=6, kind="attack", dmg=45, fx="frenzy", accent=BLUE_H,
         desc="난격 · 전력을 담은 마무리 (푸른 검광)"),
]
C_SKILLS = [
    dict(name="응급 처치", cost=2, kind="heal", hp=30, brk=0, desc="아군 1명 체력 +30"),
    dict(name="정신 집중", cost=4, kind="heal", hp=0, brk=30, desc="아군 1명 격파체력 +30"),
    dict(name="파멸의 예연", cost=6, kind="curse", accent=CURSE, curse_turns=3,
         desc="지정한 적 1기, 3턴간 받는 피해 1.5배 (격파 상태와 중첩)"),
]

# ----------------------------------------------------------------------------
# 형상 데이터 (노션 '형상' 페이지 기준)
#  · 모든 형상의 일반 공격 대미지는 형상 종류 불문 동일(기본값) → 형상마다 다른 건 스킬 3개.
#  · target: enemy(적 1기) / ally(아군 1명) / self(자신).
#  · desc 의 ' / ' 는 노션 원문의 줄바꿈.
#  · ★★ 화가 N / 요리사 H / 성직자 C 는 노션상 '개발예정', ★★★ 3종은 '미정'이라 아직 없다.
# ----------------------------------------------------------------------------
STAR_COLOR = {1: MUT, 2: SPC, 3: "#FF6EC7"}

N_SWORDSMAN_SKILLS = [
    dict(name="배기", cost=2, kind="attack", target="enemy", dmg=25,
         desc="대상에게 25의 대미지"),
    dict(name="휩쓸기", cost=5, kind="attack_splash", target="enemy", dmg=30, splash=15,
            desc="한 번에 지정한 대상에게 30의 대미지 / 나머지 모든 적에게 15(절반)의 대미지"),
    dict(name="집중 참격", cost=6, kind="focus", target="enemy", dmg=50, delay=1,
         desc="1턴간 집중 상태 진입 / 다음턴에 스킬이 발동하여 지정했던 대상에게 50의 대미지"),
]
H_GUARDIAN_SKILLS = [
    dict(name="가다듬기", cost=1, kind="heal_self", target="self", hp=15,
         desc="자신의 체력 15 회복"),
    dict(name="밀쳐내기", cost=3, kind="attack", target="enemy", dmg=25, extra_brk=5,
         desc="25의 대미지, 대상에게 5의 추가 격파피해"),
    dict(name="성전", cost=5, kind="shield_self", target="self", amt=50,
         desc="자신에게 50의 피해를 보호하는 보호막 생성 / "
              "(보호막은 최대체력을 초과하여 생성 될 수 없음)"),
]
# 예언자 C — 1~3스킬이 동일한 스킬 포인트(3)를 소모한다.
C_PROPHET_SKILLS = [
    dict(name="방호 예언", cost=3, kind="shield_ally", target="ally", amt=40,
         desc="지정한 아군에게 40의 피해를 보호하는 보호막 생성 / "
              "(보호막은 최대체력을 초과하여 생성 될 수 없음)"),
    dict(name="시간 예언", cost=3, kind="speed_debuff", target="enemy", amt=3,
         desc="지정한 적의 다음턴 속도 주사위 최대값 3 감소"),
    dict(name="암시 예언", cost=3, kind="sp_gain", target="ally", amt=2,
         desc="지정한 아군의 스킬 포인트 즉시 2 회복 / "
              "(최대 스킬 포인트를 초과하여 회복 할 수 없음)"),
]

ASPECTS = [
    dict(id="n_base", char="N", title="기본 N", star=1, desc="꽝(기본 장착 형상)", skills=N_SKILLS),
    dict(id="h_base", char="H", title="기본 H", star=1, desc="꽝(기본 장착 형상)", skills=H_SKILLS),
    dict(id="c_base", char="C", title="기본 C", star=1, desc="꽝(기본 장착 형상)", skills=C_SKILLS),
    dict(id="n_swordsman", char="N", title="검사 N", star=2, desc="", skills=N_SWORDSMAN_SKILLS),
    dict(id="h_guardian", char="H", title="수호자 H", star=2, desc="", skills=H_GUARDIAN_SKILLS),
    dict(id="c_prophet", char="C", title="예언자 C", star=2, desc="", skills=C_PROPHET_SKILLS),
]
# 가챠 확률: ★ 계열 합 70%, ★★ 계열 합 30% 를 각 등급 안에서 균등 분배 (★★★ 은 아직 없음)
for _star, _total in ((1, 70.0), (2, 30.0)):
    _grp = [_a for _a in ASPECTS if _a["star"] == _star]
    for _a in _grp:
        _a["w"] = _total / len(_grp)
GACHA_POOL = ASPECTS

GACHA_COST_SINGLE = 10     # 1회 해석 조각
GACHA_COST_TEN = 100       # 10회 비용으로 11회 해석 (+1 보너스)
GACHA_PITY_TIER2 = 200     # 형상파편 200 — ★★ 확정 교환
GACHA_PITY_TIER3 = 350     # 형상파편 350 — ★★★ 확정 교환 (★★★ 미구현)

# ----------------------------------------------------------------------------
# 스테이지 테마 — 스테이지마다 다른 몹 이름 / 배경색을 쓴다.
# 보스(BOSS_PHASE의 배수 페이즈)를 그 스테이지의 마지막 페이즈로 삼아 6페이즈씩 묶는다.
# ----------------------------------------------------------------------------
STAGE_THEMES = [
    dict(label="STAGE 1 · 국경 전선",
         tiers=["적병", "정예병", "돌격대", "사령관 부대", "이형 병기"],
         bg=BG, accent=MUT),
    dict(label="STAGE 2 · 오염된 갱도",
         tiers=["잔재병", "기생 돌격체", "포자 강화병", "균사 지휘관", "심연의 포식자"],
         bg="#171022", accent="#B98CFF"),
]


def stage_of(phase):
    """이 페이즈가 몇 번째 스테이지에 속하는지 (그 스테이지의 보스 페이즈도 포함)."""
    return (phase - 1) // BOSS_PHASE + 1


def local_index(phase):
    """스테이지 내에서 몇 번째 페이즈인지 — 1~5 는 일반, 6 은 보스."""
    return (phase - 1) % BOSS_PHASE + 1


def theme_of(phase):
    idx = (stage_of(phase) - 1) % len(STAGE_THEMES)
    return STAGE_THEMES[idx]


# ----------------------------------------------------------------------------
# 페이즈 클리어 증강(1티어) — 5종 중 3개를 무작위 제시, 하나 선택
# 한 번 획득한 증강은 이후 선택지에서 제외된다.
# ----------------------------------------------------------------------------
AUGMENTS = [
    dict(id="hp", title="불굴의 의지", color=HEAL,
         desc="모든 아군의 최대 체력이 50 늘어나고 그만큼 즉시 회복된다."),
    dict(id="atk", title="강화 훈련", color=DMG,
         desc="모든 아군의 기본 공격 피해가 5 늘어난다. (10 → 15)"),
    dict(id="sp_full", title="전술 재정비", color=SPC,
         desc="지정한 아군 1명의 스킬 포인트를 즉시 최대로 채운다."),
    dict(id="brk", title="파쇄의 기술", color=BRKC,
         desc="적에게 입히는 격파피해량이 15% 늘어난다."),
    dict(id="dice", title="속도의 비기", color=SPC,
         desc="아군 속도 주사위에서 1 눈이 제거된다. (최솟값 2)"),
]
AUG_BY_ID = {a["id"]: a for a in AUGMENTS}

# ----------------------------------------------------------------------------
# 보스 클리어 전용 증강(2티어) — 5종 중 3개를 무작위 제시, 하나 선택
# ----------------------------------------------------------------------------
AUGMENTS2 = [
    dict(id="s2_brk", title="격파 강화", color=BRKC,
         desc="모든 아군의 최대 격파체력이 50 늘어나고 그만큼 즉시 회복된다."),
    dict(id="s2_atk", title="투사 본능", color=DMG,
         desc="모든 아군의 기본 공격 피해가 5 늘어난다. (강화 훈련과 중첩 가능)"),
    dict(id="s2_undying", title="불사의 가호", color=HEAL,
         desc="전투당 1회, 아군 중 한 명이 전투불능 전 불사 상태(2턴)에 진입한다. (전투당 1회)"),
    dict(id="s2_reduce", title="철벽 방어", color=SPC,
         desc="아군이 받는 모든 피해가 10 줄어든다."),
    dict(id="s2_hp", title="생명 강화", color=HEAL,
         desc="모든 아군의 최대 체력이 50 늘어나고 그만큼 즉시 회복된다. (불굴의 의지와 중첩 가능)"),
]
AUG2_BY_ID = {a["id"]: a for a in AUGMENTS2}


def is_boss_phase(phase):
    return phase % BOSS_PHASE == 0


def boss_template(phase):
    tier = max(1, phase // BOSS_PHASE)
    mult = 1 + (tier - 1) * 0.55
    name = BOSS_NAME if tier == 1 else "%s Lv.%d" % (BOSS_NAME, tier)
    return dict(
        name=name,
        max_hp=round(850 * mult),
        max_brk=round(180 * mult),
        normal_dmg=round(24 * mult),
        skill_dmg=round(45 * mult),
        aoe_dmg=round(35 * mult),
    )


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
        self.status = None          # 'guard' / 'evade' / None
        self.broken = False
        self.broken_skips = 0
        self.curse_turns = 0        # 파멸의 예연 — 남은 저주 턴 수
        self.immortal_turns = 0     # 불사의 가호 — 남은 불사 턴 수 (체력 1 밑으로 안 내려감)
        self.skills = skills or []
        self.aspect_id = "%s_base" % uid.lower() if side == "ally" else None
        self.shield = 0
        self.speed_penalty = 0
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


def enemy_template(phase):
    theme = theme_of(phase)
    li = local_index(phase)          # 보스 페이즈에서는 호출되지 않음 — 항상 1~5
    tier = theme["tiers"][min(li - 1, len(theme["tiers"]) - 1)]
    return dict(
        max_hp=round(100 * (1 + (phase - 1) * 0.22)),
        max_brk=round(50 * (1 + (phase - 1) * 0.15)),
        normal_dmg=round(10 * (1 + (phase - 1) * 0.15)),
        skill_dmg=round(20 * (1 + (phase - 1) * 0.18)),
        tier=tier,
    )


# ----------------------------------------------------------------------------
# 게임
# ----------------------------------------------------------------------------
class NHCBattle:
    ALLY_IDS = ["N", "H", "C"]
    ENEMY_IDS = ["E1", "E2", "E3"]

    def __init__(self, root):
        self.root = root
        root.title("NHC — 전투 프로토타입")
        root.configure(bg=BG)
        root.resizable(False, False)

        fams = set(tkfont.families(root))
        self.ff = next((f for f in ["Malgun Gothic", "Apple SD Gothic Neo", "NanumGothic",
                                    "Noto Sans CJK KR", "Noto Sans KR", "AppleGothic"]
                        if f in fams), "TkDefaultFont")
        self.fm = next((f for f in ["D2Coding", "Consolas", "Menlo", "DejaVu Sans Mono",
                                    "Courier New"] if f in fams), self.ff)

        self.canvas = tk.Canvas(root, width=WIN_W, height=WIN_H, bg=BG,
                                highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_motion)

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

        self.new_game()
        self.tick()

    # ---------------- 초기화 ----------------
    def new_game(self):
        self.units = {
            "N": Unit("N", "N", "저격/근접 전환형", "ally", 100, 50, N_SKILLS),
            "H": Unit("H", "H", "전위 검사", "ally", 100, 50, H_SKILLS),
            "C": Unit("C", "C", "후방 지원", "ally", 100, 50, C_SKILLS),
        }
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
        self.owned_aspects = {"n_base", "h_base", "c_base"}
        self.aspect_shards = 0
        self.aspect_pity = 0
        self.gacha_open = False
        self.gacha_results = []     # [(pool항목, 신규여부), ...]
        self.gacha_notice = ""
        self.gacha_reveal = None
        self.status_msg = "전투 개시..."
        self.log("전투가 시작되었다. N / H / C 대 적병 3기.", TXT)
        self.log("(E 키 → 형상해석 창)", MUT)
        self.log("(전투 중 'maki' 입력 → 어드민 패널)", MUT)
        self.begin_wave(600)

    def spawn_wave(self):
        self.undying_used = False   # 불사의 가호 — 새 전투(웨이브)마다 1회 충전
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
        self.state = "roll"
        self.pending = None
        self.acting = None
        self.boss_warning = False
        self.log("── 라운드 %d ──  전원 SP +1 · 속도 판정" % self.round, TXT)

        for u in self.units.values():
            u.status = None
            u.plan = None
            u.plans = []
            u.speed = 0

        for u in self.units.values():
            if not u.alive:
                u.focused = None
                continue
            if u.curse_turns > 0:
                u.curse_turns -= 1
                if u.curse_turns == 0:
                    self.log("%s에게 걸린 저주가 풀렸다." % u.name, CURSE)
            if u.immortal_turns > 0:
                u.immortal_turns -= 1
                if u.immortal_turns == 0:
                    self.log("%s의 불사 상태가 풀렸다." % u.name, HEAL)
            if u.broken:
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
            u.sp = min(MAX_SP, u.sp + 1)
            if u.side == "enemy":
                max_speed = max(1, 6 - u.speed_penalty)
                u.speed = random.randint(1, max_speed)
                if u.speed_penalty:
                    self.log("%s의 속도 저하 효과가 적용됐다. (주사위 1~%d)" % (u.name, max_speed), CURSE)
                    u.speed_penalty = 0
            else:
                u.speed = random.randint(self.aug_speed_min, 6)

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
        self.pending = dict(type="normal", side="enemy")
        self.status_msg = "공격할 적을 선택하세요."
        self.render()

    def choose_skill(self, idx):
        if self.state != "plan" or self.busy or not self.acting:
            return
        sk = self.acting.skills[idx]
        if self.acting.sp < sk["cost"]:
            return
        target_side = sk.get("target", "ally" if sk["kind"] == "heal" else "enemy")
        if target_side == "self":
            self.acting.sp -= sk["cost"]
            self.acting.plan = dict(type="skill", idx=idx, skill=sk,
                                    target=self.acting.id)
            self.log("%s: [%s] 발동 지정 (SP -%d)" %
                     (self.acting.name, sk["name"], sk["cost"]), MUT)
            self.next_ally_plan()
            return
        self.pending = dict(type="skill", idx=idx, skill=sk, side=target_side)
        if target_side == "ally":
            self.status_msg = "회복할 아군을 선택하세요."
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
        self.status_msg = None
        self.render()

    def apply_guard(self, u):
        u.status = "guard"
        u.sp = min(MAX_SP, u.sp + 2)
        self.log("%s이(가) 방어 태세. 즉시 발동 · SP +2" % u.name, HEAL)

    def apply_evade(self, u):
        u.status = "evade"
        u.sp = min(MAX_SP, u.sp + 2)
        self.log("%s이(가) 회피 태세. 즉시 발동 · SP +2" % u.name, SPC)

    def on_card_click(self, uid):
        # 증강 '전술 재정비' 대상 지정
        if self.state == "augment_target":
            self.apply_sp_full_target(uid)
            return
        if not self.pending or self.busy:
            return
        t = self.units[uid]
        if t.side != self.pending["side"]:
            return
        u = self.acting
        if self.pending["type"] == "skill":
            sk = self.pending["skill"]
            if not t.alive:
                return
            u.sp -= sk["cost"]
            u.plan = dict(type="skill", idx=self.pending["idx"], skill=sk, target=uid)
            self.log("%s: [%s] 지정 (SP -%d)" % (u.name, sk["name"], sk["cost"]), MUT)
        else:
            if not t.alive:
                return
            u.sp = min(MAX_SP, u.sp + 1)
            u.plan = dict(type="normal", target=uid)
            self.log("%s: 기본 공격 지정 (SP +1)" % u.name, MUT)
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
        if not u.alive or not u.plan:
            self.resolve_next()
            return
        if u.broken and u.broken_skips > 0:
            u.broken_skips -= 1
            self.log("%s은 격파되어 행동이 무너졌다!" % u.name, BRKC)
            self.status_msg = "%s 행동 불가 (격파)" % u.name
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

        if ptype in ("guard", "evade"):
            self.log("%s은 %s 태세를 유지한다." % (u.name, "방어" if ptype == "guard" else "회피"),
                     HEAL if ptype == "guard" else SPC)
            self.schedule(320, done)
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
                self.log("%s이 조준경을 든다 — %s 락온." % (u.name, t.name), accent)
                self.fx_snipe(t.id, hit, color=accent)
            elif fx == "frenzy":
                self.log("%s이 검을 낮게 잡는다 — 난격!" % u.name, accent)
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
            before = t.shield
            t.shield = min(t.max_hp, t.shield + sk["amt"])
            gained = t.shield - before
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
            before = t.sp
            t.sp = min(MAX_SP, t.sp + sk["amt"])
            gained = t.sp - before
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
            self.log("%s의 [%s]! %s에게 파멸의 저주를 걸었다. (3턴간 받는 피해 1.5배, 격파 상태와 중첩)"
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

    # ---------------- 피해 처리 ----------------
    def apply_damage(self, attacker, target, raw, fx, cb):
        if self._action_epoch != self.epoch:   # 어드민 개입으로 무효화된 행동
            return
        if target.status == "guard":
            roll = d6()
            target.status = None

            def after():
                red = 0.8 if roll == 6 else roll * 0.1
                dmg = max(1, round(raw * (1 - red)))
                self.log("%s 방어! 주사위 %d → 피해 %d%% 감소 (%d→%d)" %
                         (target.name, roll, round(red * 100), raw, dmg), BRKC)
                self.finalize(attacker, target, dmg, fx, cb)

            self.dice_judge_overlay([("방어 판정", roll)], after)
            return

        if target.status == "evade":
            a, b = d6(), d6()
            target.status = None

            def after():
                dodged = a == 6 or a > b
                self.log("%s 회피 판정 %d vs %d → %s" %
                         (target.name, a, b, "완전 회피!" if dodged else "회피 실패"), BRKC)
                self.finalize(attacker, target, 0 if dodged else raw, "dodge" if dodged else fx, cb)

            self.dice_judge_overlay([("회피측", a), ("공격측", b)], after)
            return

        self.finalize(attacker, target, raw, fx, cb)

    def finalize(self, attacker, target, dmg, fx, cb):
        if self._action_epoch != self.epoch:
            return
        blocked_to_zero = False
        if dmg > 0:
            mult = 1.0
            tags = []
            if target.broken:
                mult *= 1.5
                tags.append("격파")
            if target.curse_turns > 0:
                mult *= 1.5
                tags.append("저주")
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

        was_alive = target.alive
        undying_proc = False
        if dmg > 0 and target.side == "ally":
            projected = target.hp - dmg
            if target.immortal_turns > 0:
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
        if dmg > 0 and not target.broken:
            bd = dmg // 2
            if attacker.side == "ally" and target.side == "enemy" and self.aug_brk_bonus:
                bd = round(bd * (1 + self.aug_brk_bonus))
            if bd > 0:
                target.brk = max(0, target.brk - bd)
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
            self.banner("PHASE %d" % self.phase, "적 전멸 · 증강을 선택하세요")
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
        u.sp = MAX_SP
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
        """폭 제한이 있는 자동 줄바꿈 텍스트."""
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

        self.render_panel()
        self.render_log()
        self.render_tooltip()
        self.render_augment()
        self.render_overlay()
        self.render_gacha()
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
        # 증강 '전술 재정비' 대상 지정 중에는 살아있는 아군이 대상
        if self.state == "augment_target":
            return u.side == "ally" and u.alive
        if not self.pending or self.busy:
            return False
        if u.side != self.pending["side"]:
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
        aspect = next((item for item in ASPECTS if item["id"] == u.aspect_id), None)

        fill = PANEL if not dead else "#171A1F"
        outline = BRD
        width = 1
        if u.is_boss and not dead:
            outline, width = COSMIC, 2
        if aspect:
            aspect_outline = {2: "#FFD84D", 3: STAR_COLOR[3]}.get(aspect["star"])
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
        if u.immortal_turns > 0:
            badges.append(("불사 %d" % u.immortal_turns, HEAL, "#08221D"))
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
        for i in range(MAX_SP):
            self.canvas.create_rectangle(px, sp_y + 1, px + 10, sp_y + 11,
                                         fill=SPC if i < u.sp else "",
                                         outline=SPC, tags="ui")
            px += 13
        self.txt(px + 4, sp_y, "%d/%d" % (u.sp, MAX_SP), 11, MUT, mono=True)
        if u.alive and u.speed:
            self.txt(x + w - 12, sp_y, "SPD %d" % u.speed, 13, SPC, mono=True, anchor="ne")

        # 지정한 행동
        plan_label = self.plan_label(u)
        if plan_label:
            self.txt(x + 12, y + 135, plan_label, 11, MUT, mono=True)

    def plan_label(self, u):
        if not u.plan or not u.alive:
            return ""
        t = u.plan["type"]
        if t == "guard":
            return "▣ 방어 태세"
        if t == "evade":
            return "▣ 회피 태세"
        if u.side == "enemy":
            if u.is_boss and u.plans:
                if len(u.plans) == 1 and u.plans[0]["type"] == "eaoe":
                    return "▶ ⚠ [차원 붕괴] 단독 행동 준비"
                return "▶ 이번 라운드 %d회 행동" % len(u.plans)
            return "▶ 행동 준비 중"
        if t == "normal":
            return "▶ 기본 공격"
        skill = u.plan["skill"] if "skill" in u.plan else u.skills[u.plan["idx"]]
        return "▶ " + skill["name"]

    def render_panel(self):
        x, y, w, h = MARGIN, PANEL_Y, WIN_W - MARGIN * 2, PANEL_H
        self.canvas.create_rectangle(x, y, x + w, y + h, fill=PANEL2, outline=BRD, tags="ui")

        if self.game_over:
            self.txt(x + w / 2, y + h / 2, "전투가 종료됐다.", 16, MUT, mono=True, anchor="center")
            return

        if self.state == "augment_target":
            self.txt(x + 16, y + 16, "증강 [전술 재정비] — 대상 지정", 19, SPC, bold=True)
            self.txt(x + 16, y + 48, "SP를 즉시 최대로 채울 아군 카드를 클릭하세요.", 14, MUT, mono=True)
            return

        if self.state == "plan" and self.acting and not self.busy:
            u = self.acting
            if self.pending:
                self.txt(x + 16, y + 14, "%s — 대상 선택" % u.name, 19, TXT, bold=True)
                self.txt(x + 16, y + 46, self.status_msg or "", 14, MUT, mono=True)
                self.hbtn(x + 16, y + 78, None, 26, "← 취소하고 다시 선택", self.cancel_pending, MUT)
                return
            self.txt(x + 16, y + 10, "%s의 행동 지정  ·  SPD %d  ·  SP %d/%d"
                     % (u.name, u.speed, u.sp, MAX_SP), 18, TXT, bold=True)
            self.txt(x + 16, y + 34, "행동을 지정하면 SP가 즉시 반영되고, 해결은 속도 순으로 진행된다.",
                     11, MUT, mono=True)

            bw, bh, gap = (w - 32 - 2 * 10) / 3, 40, 10
            base_atk = 10 + self.aug_atk_bonus
            cells = []
            cells.append(("기본 공격", "고정 %d 피해 · SP +1" % base_atk, True, DMG, self.choose_normal,
                          ["대상 적 1기에게 %d 고정 피해" % base_atk,
                           "SP +1 (지정 즉시 반영)",
                           "피해의 절반만큼 격파체력도 깎인다"]))
            for idx, sk in enumerate(u.skills):
                ok = u.sp >= sk["cost"]
                if sk["kind"] == "attack":
                    eff = "피해 %d" % sk["dmg"]
                else:
                    eff = sk["desc"]
                tip = ["SP 소모 %d  (현재 %d/%d)" % (sk["cost"], u.sp, MAX_SP), sk["desc"]]
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
                if u.sp < sk["cost"]:
                    tip.append("※ SP가 %d 부족하다" % (sk["cost"] - u.sp))
                if sk["kind"] in ("attack", "attack_splash", "focus"):
                    accent = DMG
                elif sk["kind"] in ("curse", "speed_debuff"):
                    accent = CURSE
                elif sk["kind"] in ("shield_self", "shield_ally"):
                    accent = SHLD
                elif sk["kind"] == "sp_gain":
                    accent = SPC
                else:
                    accent = HEAL
                cells.append((sk["name"], "SP %d · %s" % (sk["cost"], eff), ok, accent,
                              (lambda i: (lambda: self.choose_skill(i)))(idx), tip))
            cells.append(("방어", "피해 감소 · SP +2 · 즉시", True, HEAL, self.choose_guard,
                          ["지정 즉시 태세를 취한다 (속도 무관)",
                           "피격 시 주사위 1~5 → 그 값×10% 피해 감소",
                           "주사위 6 → 80% 감소", "SP +2 · 1회 피격으로 소모"]))
            cells.append(("회피", "완전 회피 시도 · SP +2 · 즉시", True, SPC, self.choose_evade,
                          ["지정 즉시 태세를 취한다 (속도 무관)",
                           "피격 시 양측 주사위 대결",
                           "내 값이 크거나 6이면 피해 0",
                           "SP +2 · 1회 피격으로 소모"]))

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
                self.txt(bx + 10, by + 23, sub, 10, MUT, mono=True)
                self.tips[i] = (label, tip)
                self.buttons.append(dict(x=bx, y=by, w=bw, h=bh,
                                         cb=(cb if ok else (lambda: None)), key=("btn", i)))
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
        tw = max([tf.measure(title)] + [lf.measure(l) for l in lines]) + 24
        lh = lf.metrics("linespace") + 3
        th = 12 + tf.metrics("linespace") + 6 + len(lines) * lh + 10

        mx, my = self.mouse
        bx = min(max(8, mx + 16), WIN_W - tw - 8)
        by = my - th - 14
        if by < 8:
            by = min(my + 22, WIN_H - th - 8)

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
        self.hbtn(bx + bw / 2 - 75, by + 142, 150, 34, "다시 시작", self.new_game, TXT)

    # ================================================================
    # 어드민 패널 — 전투 중 'maki' 입력으로 호출
    # ================================================================
    def on_key(self, ev):
        if ev.keysym == "Escape":
            if self.admin:
                self.close_admin()
            elif self.gacha_open:
                self.close_gacha()
            return
        ch = (ev.char or "").lower()
        if ch in ("e", "ㄷ") or ev.keysym.lower() == "e":
            self.toggle_gacha()
            return
        if not ch.isalpha():
            return
        self.key_buf = (self.key_buf + ch)[-12:]
        if self.key_buf.endswith(ADMIN_CODE):
            self.key_buf = ""
            self.toggle_admin()

    def toggle_admin(self):
        if self.admin:
            self.close_admin()
            return
        self.admin = True
        self.log("[ADMIN] 어드민 패널을 열었다. (ESC 로 닫기)", SPC)
        beep([(880, 50), (1175, 60)], self.sound)
        self.render()

    def close_admin(self):
        self.admin = False
        self.render()

    def admin_set_tab(self, tab):
        self.admin_tab = tab
        self.render()

    # ---------------- 어드민 동작 ----------------
    def admin_jump(self, phase):
        """지정 스테이지로 즉시 이동. 진행 중인 흐름은 전부 끊는다."""
        self.epoch += 1
        self._action_epoch = self.epoch
        self.cancel_flow()
        self.admin = False
        self.game_over = False
        self.modal = None
        self.aug_options = None
        self.state = "idle"
        self.phase = phase
        self.round = 1
        for u in self.allies():
            u.hp = u.max_hp
            u.brk = u.max_brk
            u.sp = min(MAX_SP, max(u.sp, 1))
            u.broken = False
            u.broken_skips = 0
            u.curse_turns = 0
            u.immortal_turns = 0
            u.status = None
            u.plan = None
            u.speed = 0
        self.spawn_wave()
        if self.boss_mode:
            self.log("[ADMIN] PHASE %d 보스전으로 이동 — %s."
                     % (phase, self.units[self.enemy_ids[0]].name), COSMIC)
        else:
            self.log("[ADMIN] PHASE %d 로 이동. 아군 상태를 완전히 복구했다." % phase, SPC)
        self.begin_wave(500)

    def admin_grant(self, aug_id, tier=1):
        aug = (AUG_BY_ID if tier == 1 else AUG2_BY_ID)[aug_id]
        if tier == 1 and aug_id == "sp_full":
            for u in self.allies():
                u.sp = MAX_SP
            if "sp_full" not in self.aug_taken:
                self.aug_taken.append("sp_full")
            self.log("[ADMIN] 증강 [전술 재정비] — 아군 전원 SP 최대.", SPC)
        else:
            self.apply_augment(aug, tier)
            self.log("[ADMIN] 증강 [%s] (%s) 강제 지급."
                     % (aug["title"], "1티어" if tier == 1 else "2티어"), SPC)
        beep([(1046, 45), (1318, 60)], self.sound)
        self.render()

    def admin_open_augment(self, tier=1):
        self.epoch += 1
        self._action_epoch = self.epoch
        self.cancel_flow()
        self.admin = False
        self.modal = None
        self.game_over = False
        self.log("[ADMIN] %s 증강 선택창을 강제로 열었다." % ("1티어" if tier == 1 else "2티어"), SPC)
        self.offer_augment(tier)
        if self.state != "augment_pick":
            # 이미 그 티어를 모두 획득한 상태 — 선택창이 열리지 않는다
            self.state = "idle"
            self.status_msg = "획득 가능한 증강이 없다."
            self.render()

    def admin_full_heal(self):
        for u in self.allies():
            u.hp = u.max_hp
            u.brk = u.max_brk
            u.broken = False
            u.broken_skips = 0
            u.curse_turns = 0
            u.immortal_turns = 0
            self.fx_heal(u.id, "FULL")
        self.log("[ADMIN] 아군 전원 체력·격파체력 완전 회복.", HEAL)
        self.render()

    def admin_sp_max(self):
        for u in self.allies():
            u.sp = MAX_SP
        self.log("[ADMIN] 아군 전원 SP 최대.", SPC)
        self.render()

    def admin_shard_add(self, n):
        self.aspect_shards += n
        self.log("[ADMIN] 조각 +%d → 보유 %d개" % (n, self.aspect_shards), SPC)
        self.render()

    def admin_shard_reset(self):
        self.aspect_shards = 0
        self.log("[ADMIN] 조각 초기화.", SPC)
        self.render()

    def admin_pity_add(self, n):
        self.aspect_pity += n
        self.log("[ADMIN] 형상파편 +%d → 보유 %d개" % (n, self.aspect_pity), SHLD)
        self.render()

    def admin_pity_reset(self):
        self.aspect_pity = 0
        self.log("[ADMIN] 형상파편 초기화.", SPC)
        self.render()

    def admin_clear_wave(self):
        self.epoch += 1
        self._action_epoch = self.epoch
        self.cancel_flow()
        self.admin = False
        self.game_over = False
        self.modal = None
        self.state = "idle"
        for e in self.enemies():
            e.hp = 0
        self.log("[ADMIN] 현재 적 병력을 전멸시켰다.", SPC)
        self.render()
        self.schedule(300, self.next_phase)

    # ---------------- 어드민 렌더 ----------------
    def abtn(self, x, y, w, h, label, sub, cb, color, idx):
        hovered = self.hover == ("adm", idx)
        self.canvas.create_rectangle(x, y, x + w, y + h,
                                     fill=PANEL2 if hovered else PANEL,
                                     outline=color, width=2 if hovered else 1, tags="ui")
        if sub:
            self.txt(x + w / 2, y + h / 2 - 10, label, 14, color, bold=True, anchor="center")
            self.wtxt(x + w / 2, y + h / 2 + 4, w - 10, sub, 10, MUT, mono=True,
                      anchor="n", justify="center")
        else:
            self.txt(x + w / 2, y + h / 2, label, 14, color, mono=True, anchor="center")
        self.buttons.append(dict(x=x, y=y, w=w, h=h, key=("adm", idx), cb=cb))

    def render_admin(self):
        if not self.admin:
            return
        # 패널 뒤쪽 버튼이 눌리지 않도록 클릭 대상을 전부 교체한다
        self.buttons = []

        self.canvas.create_rectangle(0, 0, WIN_W, WIN_H, fill="#000000", outline="",
                                     stipple="gray75", tags="ui")
        pw, ph = 900, 520
        px, py = (WIN_W - pw) / 2, 130
        self.canvas.create_rectangle(px + 5, py + 5, px + pw + 5, py + ph + 5,
                                     fill="#05070A", outline="", stipple="gray50", tags="ui")
        self.canvas.create_rectangle(px, py, px + pw, py + ph, fill=PANEL, outline=SPC,
                                     width=2, tags="ui")
        self.canvas.create_rectangle(px, py, px + pw, py + 5, fill=SPC, outline="", tags="ui")

        ix, iw = px + 24, pw - 48
        self.txt(ix, py + 16, "ADMIN PANEL", 24, SPC, bold=True)
        state_txt = "STAGE %d · PHASE %d · ROUND %d · %s" % (
            stage_of(self.phase), self.phase, self.round,
            "BOSS" if self.boss_mode else "일반 웨이브")
        self.txt(px + pw - 24, py + 20, state_txt, 11, MUT, mono=True, anchor="ne")

        # 탭
        tabs = [("move", "이동"), ("augment", "증강"), ("aspect", "형상"), ("misc", "기타")]
        tw = 110
        for i, (tid, label) in enumerate(tabs):
            tx = ix + i * (tw + 8)
            on = self.admin_tab == tid
            self.canvas.create_rectangle(tx, py + 44, tx + tw, py + 72,
                                         fill=SPC if on else PANEL2,
                                         outline=SPC, tags="ui")
            self.txt(tx + tw / 2, py + 58, label, 13, "#101318" if on else MUT,
                     bold=on, mono=True, anchor="center")
            self.buttons.append(dict(x=tx, y=py + 44, w=tw, h=28,
                                     cb=(lambda t=tid: self.admin_set_tab(t))))
        self.canvas.create_line(ix, py + 84, ix + iw, py + 84, fill=BRD, tags="ui")

        body_y = py + 96
        idx = 0
        gap = 10

        if self.admin_tab == "move":
            bw = (iw - gap * 4) / 5
            self.txt(ix, body_y, STAGE_THEMES[0]["label"], 13, TXT, bold=True)
            for i in range(1, 6):
                self.abtn(ix + (i - 1) * (bw + gap), body_y + 20, bw, 44,
                          "PHASE %d" % i, STAGE_THEMES[0]["tiers"][i - 1],
                          (lambda k: (lambda: self.admin_jump(k)))(i), TXT, idx)
                idx += 1
            self.abtn(ix, body_y + 74, iw, 40,
                      "PHASE %d — %s 보스전" % (BOSS_PHASE, BOSS_NAME),
                      "체력 850 / 격파 180 / 1라운드 3행동 · SP 6에서 [차원 붕괴] 단독 사용",
                      lambda: self.admin_jump(BOSS_PHASE), COSMIC, idx)
            idx += 1

            self.txt(ix, body_y + 128, STAGE_THEMES[1]["label"], 13, TXT, bold=True)
            for i in range(7, 12):
                self.abtn(ix + (i - 7) * (bw + gap), body_y + 148, bw, 44,
                          "PHASE %d" % i, STAGE_THEMES[1]["tiers"][i - 7],
                          (lambda k: (lambda: self.admin_jump(k)))(i), TXT, idx)
                idx += 1
            self.abtn(ix, body_y + 202, iw, 40,
                      "PHASE %d — %s 보스전 (Lv.2)" % (BOSS_PHASE * 2, BOSS_NAME),
                      "이전보다 55%% 강화된 개체",
                      lambda: self.admin_jump(BOSS_PHASE * 2), COSMIC, idx)
            idx += 1

        elif self.admin_tab == "augment":
            bw = (iw - gap * 4) / 5
            self.txt(ix, body_y, "1티어 증강 강제 지급 (일반 페이즈 보상)", 13, TXT, bold=True)
            for i, aug in enumerate(AUGMENTS):
                owned = aug["id"] in self.aug_taken
                self.abtn(ix + i * (bw + gap), body_y + 20, bw, 52,
                          aug["title"], "보유 중" if owned else "미보유",
                          (lambda k: (lambda: self.admin_grant(k, 1)))(aug["id"]),
                          aug["color"] if not owned else MUT, idx)
                idx += 1
            self.abtn(ix, body_y + 78, iw, 34, "1티어 선택창 강제 호출", None,
                      lambda: self.admin_open_augment(1), SPC, idx)
            idx += 1

            self.txt(ix, body_y + 128, "2티어 증강 강제 지급 (보스 클리어 보상)", 13, TXT, bold=True)
            for i, aug in enumerate(AUGMENTS2):
                owned = aug["id"] in self.aug_taken2
                self.abtn(ix + i * (bw + gap), body_y + 148, bw, 52,
                          aug["title"], "보유 중" if owned else "미보유",
                          (lambda k: (lambda: self.admin_grant(k, 2)))(aug["id"]),
                          aug["color"] if not owned else MUT, idx)
                idx += 1
            self.abtn(ix, body_y + 206, iw, 34, "2티어 선택창 강제 호출", None,
                      lambda: self.admin_open_augment(2), SPC, idx)
            idx += 1

        elif self.admin_tab == "aspect":
            mw = (iw - gap * 3) / 4
            self.txt(ix, body_y, "형상해석 재화 — 조각 %d · 형상파편 %d"
                     % (self.aspect_shards, self.aspect_pity), 14, SPC, bold=True)
            self.txt(ix, body_y + 24, "형상해석 창은 전투 중 E 키로 연다. 조각/파편 지급은 여기서 한다.",
                     11, MUT, mono=True)
            row1 = [("조각 +10", lambda: self.admin_shard_add(10), SPC),
                    ("조각 +100", lambda: self.admin_shard_add(100), SPC),
                    ("조각 +1000", lambda: self.admin_shard_add(1000), SPC),
                    ("조각 초기화", self.admin_shard_reset, MUT)]
            row2 = [("파편 +50", lambda: self.admin_pity_add(50), SHLD),
                    ("파편 +200", lambda: self.admin_pity_add(200), SHLD),
                    ("파편 +350", lambda: self.admin_pity_add(350), SHLD),
                    ("파편 초기화", self.admin_pity_reset, MUT)]
            for r, row in enumerate((row1, row2)):
                for i, (label, cb, color) in enumerate(row):
                    self.abtn(ix + i * (mw + gap), body_y + 54 + r * 52, mw, 42,
                              label, None, cb, color, idx)
                    idx += 1

        else:  # misc
            mw = (iw - gap * 2) / 3
            misc = [
                ("아군 완전 회복", "체력·격파체력 최대", self.admin_full_heal, HEAL),
                ("아군 SP 최대", "전원 SP %d" % MAX_SP, self.admin_sp_max, SPC),
                ("현재 적 전멸", "즉시 페이즈 클리어", self.admin_clear_wave, DMG),
            ]
            for i, (label, sub, cb, color) in enumerate(misc):
                self.abtn(ix + i * (mw + gap), body_y, mw, 52, label, sub, cb, color, idx)
                idx += 1

        # 닫기
        self.abtn(px + pw / 2 - 100, py + ph - 46, 200, 34, "닫기 (ESC)", None,
                  self.close_admin, MUT, idx)
        self.txt(px + pw / 2, py + ph - 8, "전투 중 'maki' 를 입력하면 언제든 다시 열린다.",
                 10, MUT, mono=True, anchor="center")

    # ================================================================
    # 형상해석(가챠) 창 — E 키로 열고 닫으며, 보유 형상을 클릭해 장착한다.
    # ================================================================
    def toggle_gacha(self):
        if self.gacha_open:
            self.close_gacha()
            return
        if self.admin or self.modal or self.state == "augment_pick":
            return
        self.gacha_open = True
        self.render()

    def close_gacha(self):
        self.gacha_open = False
        if self.gacha_reveal:
            self.gacha_reveal = None
        self.render()

    def equip_aspect(self, aspect_id):
        aspect = next((item for item in ASPECTS if item["id"] == aspect_id), None)
        if not aspect or aspect_id not in self.owned_aspects:
            return
        unit = self.units.get(aspect["char"])
        if not unit or unit.side != "ally":
            return
        unit.aspect_id = aspect_id
        unit.skills = aspect["skills"]
        self.gacha_notice = "%s 장착 완료." % aspect["title"]
        self.log("%s에게 [%s] 형상을 장착했다." % (unit.name, aspect["title"]), STAR_COLOR[aspect["star"]])
        self.render()

    def gacha_draw(self, count, cost):
        if self.aspect_shards < cost:
            return
        self.aspect_shards -= cost
        total = sum(a["w"] for a in GACHA_POOL)
        results = []
        for _ in range(count):
            r = random.random() * total
            pick = GACHA_POOL[-1]
            for a in GACHA_POOL:
                if r < a["w"]:
                    pick = a
                    break
                r -= a["w"]
            results.append((pick, pick["id"] not in self.owned_aspects))
            self.owned_aspects.add(pick["id"])
        self.aspect_pity += count
        self.gacha_results = results
        self.gacha_notice = ""
        self.gacha_reveal = {"revealed": 0, "index": 0, "frame": 0}
        self.log("형상해석 %d회 (조각 -%d) — ★★ %d개" %
                 (count, cost, sum(1 for a, _ in results if a["star"] >= 2)), SPC)
        beep([(880, 50), (1046, 60), (1318, 90)], self.sound)
        self.render()
        self.schedule(28, self.gacha_reveal_step)

    def gacha_reveal_step(self):
        reveal = self.gacha_reveal
        if not self.gacha_open or not reveal:
            return
        reveal["frame"] += 1
        if reveal["frame"] >= 8:
            reveal["revealed"] += 1
            reveal["index"] += 1
            reveal["frame"] = 0
            if reveal["revealed"] >= len(self.gacha_results):
                self.gacha_reveal = None
            beep([(523, 25), (784, 40)], self.sound)
        self.render()
        if self.gacha_reveal:
            self.schedule(28, self.gacha_reveal_step)

    def gacha_pity_exchange(self, tier):
        if tier == 2:
            self.gacha_notice = "★★ 확정 교환 — 형상 선택 화면은 아직 미구현 (파편은 소비되지 않음)"
        else:
            self.gacha_notice = "★★★ 형상이 아직 없어 교환할 수 없다 (준비 중)"
        self.render()

    def gbtn(self, x, y, w, h, label, sub, cb, color, enabled, idx):
        hovered = enabled and self.hover == ("gch", idx)
        self.canvas.create_rectangle(x, y, x + w, y + h, fill=PANEL2 if hovered else PANEL,
                                     outline=color if enabled else BRD,
                                     width=2 if hovered else 1, tags="ui")
        tc = color if enabled else MUT
        if sub:
            self.txt(x + w / 2, y + h / 2 - 9, label, 15, tc, bold=True, anchor="center")
            self.txt(x + w / 2, y + h / 2 + 11, sub, 10, MUT, mono=True, anchor="center")
        else:
            self.txt(x + w / 2, y + h / 2, label, 12, tc, mono=True, anchor="center")
        self.buttons.append(dict(x=x, y=y, w=w, h=h, key=("gch", idx),
                                 cb=(cb if enabled else (lambda: None))))

    def aspect_tip_lines(self, a):
        lines = []
        if a.get("desc"):
            lines.append(a["desc"])
        for i, sk in enumerate(a["skills"], 1):
            lines.append("스킬 %d: %s [%d포인트 소비]" % (i, sk["name"], sk["cost"]))
            for part in sk["desc"].split(" / "):
                lines.append("   " + part)
        return lines

    def draw_aspect_tip(self, a):
        c = STAR_COLOR.get(a["star"], TXT)
        title = "%s  %s" % ("★" * a["star"], a["title"])
        lines = self.aspect_tip_lines(a)
        tf, lf = self.font(15, bold=True), self.font(11, mono=True)
        tw = max([tf.measure(title)] + [lf.measure(l) for l in lines]) + 24
        lh = lf.metrics("linespace") + 3
        th = 12 + tf.metrics("linespace") + 6 + len(lines) * lh + 10
        mx, my = self.mouse
        bx = min(max(8, mx + 16), WIN_W - tw - 8)
        by = my + 22
        if by + th > WIN_H - 8:
            by = max(8, my - th - 14)
        self.canvas.create_rectangle(bx + 3, by + 3, bx + tw + 3, by + th + 3,
                                     fill="#0A0C10", outline="", stipple="gray50", tags="ui")
        self.canvas.create_rectangle(bx, by, bx + tw, by + th, fill=PANEL2, outline=c,
                                     width=2, tags="ui")
        self.txt(bx + 12, by + 8, title, 15, c, bold=True)
        ty = by + 8 + tf.metrics("linespace") + 6
        for l in lines:
            self.txt(bx + 12, ty, l, 11, TXT if l.startswith("스킬") else MUT, mono=True)
            ty += lh

    def render_gacha(self):
        if not self.gacha_open:
            return
        self.buttons = []     # 뒤쪽 버튼이 눌리지 않도록 교체
        self.canvas.create_rectangle(0, 0, WIN_W, WIN_H, fill="#000000", outline="",
                                     stipple="gray75", tags="ui")
        pw, ph = 900, 704
        px, py = (WIN_W - pw) / 2, 60
        self.canvas.create_rectangle(px + 5, py + 5, px + pw + 5, py + ph + 5,
                                     fill="#05070A", outline="", stipple="gray50", tags="ui")
        self.canvas.create_rectangle(px, py, px + pw, py + ph, fill=PANEL, outline=SHLD,
                                     width=2, tags="ui")
        self.canvas.create_rectangle(px, py, px + pw, py + 5, fill=SHLD, outline="", tags="ui")
        ix, iw = px + 24, pw - 48

        self.txt(ix, py + 14, "형상해석", 28, TXT, bold=True)
        self.txt(ix + 140, py + 28, "조각으로 형상을 해석한다", 12, MUT, mono=True)
        self.txt(px + pw - 24, py + 24, "[E] / [ESC] 닫기", 11, MUT, mono=True, anchor="ne")

        # 재화
        for i, (label, val, color) in enumerate([("조각", self.aspect_shards, SPC),
                                                  ("형상파편", self.aspect_pity, SHLD)]):
            bx = ix + i * 232
            self.canvas.create_rectangle(bx, py + 64, bx + 220, py + 114, fill=PANEL2,
                                         outline=BRD, tags="ui")
            self.txt(bx + 14, py + 70, label, 11, MUT, mono=True)
            self.txt(bx + 14, py + 86, str(val), 20, color, bold=True)

        # 확률
        self.txt(ix, py + 128, "확률", 11, MUT, mono=True)
        self.txt(ix + 50, py + 127, "★  70%", 13, STAR_COLOR[1], bold=True)
        self.txt(ix + 150, py + 127, "★★  30%", 13, STAR_COLOR[2], bold=True)
        self.txt(ix + 262, py + 127, "★★★  — (미구현)", 13, MUT, bold=True)

        # 형상 도감 — 칩에 마우스를 올리면 스킬 확인
        self.txt(ix, py + 158, "형상 도감", 12, TXT, bold=True)
        self.txt(ix + 80, py + 160, "보유 형상을 클릭해 장착 · 마우스를 올리면 스킬 확인", 11, MUT,
             mono=True)
        n = len(ASPECTS)
        dw = (iw - (n - 1) * 8) / n
        for i, a in enumerate(ASPECTS):
            dx, dy = ix + i * (dw + 8), py + 178
            owned = a["id"] in self.owned_aspects
            c = STAR_COLOR.get(a["star"], TXT)
            hov = self.hover == ("gdex", i)
            self.canvas.create_rectangle(dx, dy, dx + dw, dy + 46,
                                         fill=PANEL2 if hov else PANEL,
                                         outline=c if owned else BRD,
                                         width=2 if hov else 1, tags="ui")
            self.txt(dx + dw / 2, dy + 12, "★" * a["star"], 11, c if owned else MUT,
                     bold=True, anchor="center")
            self.txt(dx + dw / 2, dy + 28, a["title"], 13, TXT if owned else MUT,
                     bold=True, anchor="center")
            unit = self.units.get(a["char"])
            equipped = bool(unit and unit.aspect_id == a["id"])
            status = "장착 중" if equipped else ("클릭해 장착" if owned else "미보유")
            self.txt(dx + dw / 2, dy + 40, status, 9, HEAL if equipped else MUT,
                     mono=True, anchor="center")
            callback = (lambda aid=a["id"]: self.equip_aspect(aid)) if owned else (lambda: None)
            self.buttons.append(dict(x=dx, y=dy, w=dw, h=46, key=("gdex", i), cb=callback))

        # 해석 버튼
        bw = (iw - 12) / 2
        can_draw = not self.gacha_reveal
        self.gbtn(ix, py + 238, bw, 66, "1회 해석", "조각 %d 소모" % GACHA_COST_SINGLE,
                  lambda: self.gacha_draw(1, GACHA_COST_SINGLE), SPC,
              self.aspect_shards >= GACHA_COST_SINGLE and can_draw, 0)
        self.gbtn(ix + bw + 12, py + 238, bw, 66, "10회 해석  (+1회 보너스)",
                  "조각 %d 소모 · 총 11회 해석" % GACHA_COST_TEN,
                  lambda: self.gacha_draw(11, GACHA_COST_TEN), SPC,
              self.aspect_shards >= GACHA_COST_TEN and can_draw, 1)

        # 형상파편 진행도
        y0 = py + 326
        self.txt(ix, y0, "형상파편  (해석 1회당 +1 · 교환 시 전부 소비)", 12, TXT, bold=True)
        by = y0 + 26
        self.canvas.create_rectangle(ix, by, ix + iw, by + 16, fill=PANEL2, outline=BRD, tags="ui")
        ratio = min(1.0, self.aspect_pity / float(GACHA_PITY_TIER3))
        if ratio > 0:
            self.canvas.create_rectangle(ix + 1, by + 1, ix + 1 + (iw - 2) * ratio, by + 15,
                                         fill=SHLD, outline="", tags="ui")
        x200 = ix + iw * GACHA_PITY_TIER2 / float(GACHA_PITY_TIER3)
        self.canvas.create_line(x200, by - 4, x200, by + 20, fill=STAR_COLOR[2], width=2, tags="ui")
        self.txt(x200, by + 22, "%d  ★★ 확정" % GACHA_PITY_TIER2, 10, STAR_COLOR[2],
                 mono=True, anchor="n")
        self.txt(ix + iw, by + 22, "%d  ★★★ 확정" % GACHA_PITY_TIER3, 10, STAR_COLOR[3],
                 mono=True, anchor="ne")

        ey = y0 + 68
        self.gbtn(ix, ey, bw, 42, "★★ 확정 교환  (%d)" % GACHA_PITY_TIER2, None,
                  lambda: self.gacha_pity_exchange(2), STAR_COLOR[2],
                  self.aspect_pity >= GACHA_PITY_TIER2 and can_draw, 2)
        self.gbtn(ix + bw + 12, ey, bw, 42,
                  "★★★ 확정 교환  (%d)  — 준비 중" % GACHA_PITY_TIER3, None,
                  lambda: self.gacha_pity_exchange(3), STAR_COLOR[3],
                  self.aspect_pity >= GACHA_PITY_TIER3 and can_draw, 3)
        if self.gacha_notice:
            self.txt(ix, ey + 50, self.gacha_notice, 11, SPC, mono=True)

        # 해석 결과 (카드에 마우스를 올리면 스킬 확인)
        y1 = py + 472
        self.txt(ix, y1, "해석 결과", 12, TXT, bold=True)
        if not self.gacha_results:
            self.txt(ix + iw / 2, y1 + 70, "아직 해석 기록이 없다.", 13, MUT, mono=True,
                     anchor="center")
        cw, ch = (iw - 5 * 10) / 6, 64
        revealed = self.gacha_reveal["revealed"] if self.gacha_reveal else len(self.gacha_results)
        for i, (pick, is_new) in enumerate(self.gacha_results):
            cx = ix + (i % 6) * (cw + 10)
            cy = y1 + 24 + (i // 6) * (ch + 10)
            c = STAR_COLOR.get(pick["star"], TXT)
            hov = self.hover == ("gcard", i)
            active_reveal = self.gacha_reveal and i == self.gacha_reveal["index"]
            face_up = i < revealed or (active_reveal and self.gacha_reveal["frame"] >= 4)
            card_w = cw
            if active_reveal:
                frame = self.gacha_reveal["frame"]
                card_w *= max(0.06, abs((frame - 4) / 4.0))
            card_x = cx + (cw - card_w) / 2
            if face_up:
                self.canvas.create_rectangle(card_x, cy, card_x + card_w, cy + ch,
                                             fill=PANEL if hov else PANEL2, outline=c,
                                             width=2 if (pick["star"] >= 2 or hov) else 1, tags="ui")
                if card_w > cw * 0.45:
                    self.txt(cx + cw / 2, cy + 14, "★" * pick["star"], 12, c,
                             bold=True, anchor="center")
                    self.txt(cx + cw / 2, cy + 33, pick["title"], 13, TXT,
                             bold=True, anchor="center")
                if i < revealed and not self.gacha_reveal:
                    unit = self.units.get(pick["char"])
                    equipped = bool(unit and unit.aspect_id == pick["id"])
                    status = "장착 중" if equipped else "클릭해 장착"
                    self.txt(cx + cw / 2, cy + 52, status, 10, HEAL if equipped else MUT,
                             mono=True, anchor="center")
                    callback = lambda aid=pick["id"]: self.equip_aspect(aid)
                    self.buttons.append(dict(x=cx, y=cy, w=cw, h=ch,
                                             key=("gcard", i), cb=callback))
                elif card_w > cw * 0.45:
                    label = "NEW" if is_new else "중복 해석"
                    self.txt(cx + cw / 2, cy + 52, label, 10, SPC if is_new else MUT,
                             mono=True, anchor="center")
            else:
                self.canvas.create_rectangle(card_x, cy, card_x + card_w, cy + ch,
                                             fill=PANEL, outline=SHLD, width=2, tags="ui")
                if card_w > cw * 0.45:
                    self.txt(cx + cw / 2, cy + 32, "✦", 24, SHLD, bold=True, anchor="center")

        # 하단
        fy = py + ph - 62
        self.gbtn(ix + iw - 140, fy, 140, 34, "닫기", None, self.close_gacha, MUT, True, 4)
        self.txt(ix, fy + 9, "※ 적 처치 +10 · 스테이지 클리어 +100 조각  |  추가 조정: 어드민 패널(maki)",
             11, MUT, mono=True)
        self.txt(px + pw / 2, py + ph - 18,
             "※ 해석 결과 또는 도감에서 보유 형상을 클릭하면 장착할 수 있다.",
             10, MUT, mono=True, anchor="center")

        h = self.hover
        if isinstance(h, tuple):
            if h[0] == "gdex" and h[1] < len(ASPECTS):
                self.draw_aspect_tip(ASPECTS[h[1]])
            elif h[0] == "gcard" and h[1] < len(self.gacha_results):
                self.draw_aspect_tip(self.gacha_results[h[1]][0])

    # ---------------- 입력 ----------------
    def toggle_sound(self):
        self.sound = not self.sound
        self.render()

    def on_click(self, ev):
        for b in self.buttons:
            if b["x"] <= ev.x <= b["x"] + b["w"] and b["y"] <= ev.y <= b["y"] + b["h"]:
                b["cb"]()
                return
        if (self.modal or self.overlay or self.admin or self.gacha_open
                or self.state == "augment_pick"):
            return
        for uid, (x, y, w, h) in self.card_rects.items():
            if x <= ev.x <= x + w and y <= ev.y <= y + h:
                self.on_card_click(uid)
                return

    def on_motion(self, ev):
        moved = abs(ev.x - self.mouse[0]) + abs(ev.y - self.mouse[1]) > 6
        self.mouse = (ev.x, ev.y)
        new = None
        for b in self.buttons:
            if "key" in b and b["x"] <= ev.x <= b["x"] + b["w"] and b["y"] <= ev.y <= b["y"] + b["h"]:
                new = b["key"]
                break
        if (new is None and not self.modal and not self.overlay and not self.admin
                and not self.gacha_open and self.state != "augment_pick"):
            for uid, (x, y, w, h) in self.card_rects.items():
                if x <= ev.x <= x + w and y <= ev.y <= y + h and self.targetable(self.units[uid]):
                    new = uid
                    break
        if new != self.hover:
            self.hover = new
            self.render()
        elif moved and isinstance(new, tuple):
            self.render()


class NHCIntro:
    STORY = (
        
    )

    def __init__(self, root):
        self.root = root
        root.title("PROJECT NHC")
        root.configure(bg=BG)
        root.resizable(False, False)
        self.canvas = tk.Canvas(root, width=WIN_W, height=WIN_H, bg=BG,
                                highlightthickness=0)
        self.canvas.pack()
        self.canvas.configure(takefocus=True)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<space>", self.on_space)
        self.canvas.focus_set()
        fams = set(tkfont.families(root))
        self.font = next((f for f in ["Malgun Gothic", "Apple SD Gothic Neo",
                                      "NanumGothic", "Noto Sans CJK KR",
                                      "Noto Sans KR", "AppleGothic"]
                          if f in fams), "TkDefaultFont")
        self.page = "title"
        self.buttons = []
        self.hover = None
        self.story_index = 0
        self.draw_title()

    def draw_button(self, x, y, w, h, label, callback, key):
        fill = "#303943" if self.hover == key else PANEL2
        outline = SPC if self.hover == key else BRD
        self.canvas.create_rectangle(x, y, x + w, y + h, fill=fill,
                                     outline=outline, width=2)
        self.canvas.create_text(x + w / 2, y + h / 2, text=label,
                               fill=TXT, font=(self.font, 17, "bold"))
        self.buttons.append(dict(x=x, y=y, w=w, h=h, cb=callback, key=key))

    def draw_title(self):
        self.page = "title"
        self.buttons = []
        self.canvas.delete("all")
        self.canvas.create_rectangle(34, 34, WIN_W - 34, WIN_H - 34,
                                     outline=BRD, width=2)
        self.canvas.create_text(WIN_W / 2, 280, text="PROJECT",
                               fill=MUT, font=(self.font, 19, "bold"))
        self.canvas.create_text(WIN_W / 2, 360, text="NHC",
                               fill=TXT, font=(self.font, 72, "bold"))
        self.canvas.create_line(380, 420, 660, 420, fill=SPC, width=2)
        self.canvas.create_text(WIN_W / 2, 462, text="국경 전선 작전 기록",
                               fill=MUT, font=(self.font, 17))
        self.draw_button(400, 680, 240, 64, "START", self.show_story, "start")

    def show_story(self):
        self.page = "story"
        self.canvas.focus_set()
        self.story_index = 0
        self.buttons = []
        self.canvas.delete("all")
        self.canvas.create_rectangle(34, 34, WIN_W - 34, WIN_H - 34,
                                     outline=BRD, width=2)
        self.canvas.create_text(90, 90, anchor="w", text="NHC  /  PROLOGUE",
                               fill=SPC, font=(self.font, 15, "bold"))
        self.canvas.create_line(90, 122, WIN_W - 90, 122, fill=BRD, width=2)
        self.canvas.create_text(90, 170, anchor="w", text="국경 전선",
                               fill=TXT, font=(self.font, 30, "bold"))
        self.canvas.create_text(WIN_W / 2, 640,
                       text="스페이스바를 눌러 건너뛰기",
                       fill=MUT, font=(self.font, 14))
        self.story_text = self.canvas.create_text(
            90, 230, anchor="nw", width=850, text="", fill=TXT,
            font=(self.font, 19), spacing=13, justify="left")
        self.canvas.create_text(WIN_W - 90, 735, anchor="e",
                               text="PROJECT NHC", fill=MUT,
                               font=(self.font, 11))
        self.draw_story_buttons()
        self.reveal_next()

    def draw_story_buttons(self):
        self.buttons = []
        if self.story_index < len(self.STORY):
            self.draw_button(710, 680, 240, 54, "건너뛰기", self.start_battle, "skip")
        else:
            self.draw_button(90, 680, 190, 54, "타이틀", self.draw_title, "title")
            self.draw_button(710, 680, 240, 54, "전투 시작", self.start_battle, "battle")

    def reveal_next(self):
        if self.page != "story":
            return
        self.story_index = min(self.story_index + 2, len(self.STORY))
        self.canvas.itemconfigure(self.story_text, text=self.STORY[:self.story_index])
        if self.story_index < len(self.STORY):
            self.root.after(24, self.reveal_next)
        else:
            self.draw_story_buttons()

    def start_battle(self):
        self.canvas.destroy()
        NHCBattle(self.root)

    def on_space(self, event):
        if self.page == "story":
            self.start_battle()
            return "break"

    def on_click(self, event):
        for button in self.buttons:
            if (button["x"] <= event.x <= button["x"] + button["w"]
                    and button["y"] <= event.y <= button["y"] + button["h"]):
                button["cb"]()
                return

    def on_motion(self, event):
        hovered = next((button["key"] for button in self.buttons
                        if button["x"] <= event.x <= button["x"] + button["w"]
                        and button["y"] <= event.y <= button["y"] + button["h"]), None)
        if hovered != self.hover:
            self.hover = hovered
            if self.page == "title":
                self.draw_title()
            else:
                current_index = self.story_index
                current_text = self.STORY[:current_index]
                self.canvas.delete("all")
                self.show_story_frame(current_text, current_index)

    def show_story_frame(self, text, index):
        self.story_index = index
        self.canvas.create_rectangle(34, 34, WIN_W - 34, WIN_H - 34,
                                     outline=BRD, width=2)
        self.canvas.create_text(90, 90, anchor="w", text="NHC  /  PROLOGUE",
                               fill=SPC, font=(self.font, 15, "bold"))
        self.canvas.create_line(90, 122, WIN_W - 90, 122, fill=BRD, width=2)
        self.canvas.create_text(90, 170, anchor="w", text="국경 전선",
                               fill=TXT, font=(self.font, 30, "bold"))
        self.canvas.create_text(WIN_W / 2, 640,
                       text="스페이스바를 눌러 넘어가기",
                       fill=MUT, font=(self.font, 14))
        self.story_text = self.canvas.create_text(
            90, 230, anchor="nw", width=850, text=text, fill=TXT,
            font=(self.font, 19), spacing=13, justify="left")
        self.canvas.create_text(WIN_W - 90, 735, anchor="e",
                               text="PROJECT NHC", fill=MUT,
                               font=(self.font, 11))
        self.draw_story_buttons()


def main():
    root = tk.Tk()
    NHCIntro(root)
    root.mainloop()


if __name__ == "__main__":
    main()
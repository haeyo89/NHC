# -*- coding: utf-8 -*-
"""NHC 데이터 · 상수 · 유틸 — 스킬/형상/아이템/도감 수치는 여기서 고친다."""
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math
import os
import random
import threading
import time
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
PAINT_BLUE = BLUE_H     # 화가 N — 블루
PAINT_RED = "#E5484D"   # 화가 N — 레드
PAINT_GREEN = "#46C26A" # 화가 N — 그린

DREAM_YEL = "#FFF3A8"     # D 드리머 — 연노랑
DREAM_PUR = "#C9B2FF"     # D 드리머 — 연보라
DREAM_PUR_D = "#6A55B0"   # D 드리머 — 짙은 보라 (베일)
DREAM_WHITE = "#FFFFFF"

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
STAR_COLOR = {1: MUT, 2: SPC, 3: "#FF6EC7", 4: "#FF2D2D"}
UB_RED = STAR_COLOR[4]      # ★★★★ 언더보스 — 빨간색 테두리
UB_GOLD = "#FFC83D"        # 언더보스 이펙트 — 황금
UB_GOLD_L = "#FFF0B0"      # 밝은 황금(광택)
UB_CRIM = "#E5282B"        # 진홍
UB_CRIM_D = "#7A1014"      # 어두운 진홍(잔광)
UB_DODGE_LINES = ["왜? 못맞추겠어?", "그딴 자세론 내 옷깃도 못 스쳐", "너무 뻔하잖아.", "훤히 다보여"]
UB_AMMO_MAX = 10           # 가속탄 최대치

# ---- 아이템 / 인벤토리 ----
# tier 는 이름 옆 [n T] 로 표시된다. flavor 는 스토리와 연관된 툴팁(따옴표 포함해서 적는다).
ITEM_TIER_COLOR = {1: "#B9B3A6", 2: "#7FC8F8", 3: "#FF6EC7"}
ITEMS = {
    "faded_wish": dict(
        name="빛바랜 소망", tier=1,
        desc="빛이 나지 않는 잘게 부셔져 가루처럼 되어버린 소망",
        flavor="'살아가는 모든 이들은 저마다의 소망을 가지고 살아간다죠..? "
               "이는 그 소망이 실체화된 무언가로 보여요'"),
}
ITEMS["small_mirror"] = dict(
    name="작은 거울", tier=1, icon="mirror",
    desc="빛바랜 소망을 모아 기도하니 생겨난 거울\n아군의 생명력을 소폭 증가시키는 듯 하다",
    flavor="'그렇게 모아서 만들어진게 고작 거울 하나에요..? 뭐.. 싫다는건 아닌데..'",
    effect="효과: 모든 아군 최대 체력 +50")                      # 플레이버 텍스트는 나중에 여기에 적는다
ITEMS["torn_umbrella"] = dict(
    name="헤진 우산", tier=1, icon="umbrella",
    desc="소망을 모아 기도하니 생겨난 용도 불명의 우산\n아군의 공격력을 증가시키는 듯 하다",
    flavor="'왜 이런게 만들어지는지는 아직 아무도 모르는거죠? 그쵸?, 빛 모아서 우산 만들기는 좀 수지타산이 안맞잖아요..'",
    effect="효과: 모든 아군 공격력 +5")
ITEMS["dim_wish"] = dict(
    name="희미한 소망", tier=2,
    desc="희미하지만 약간의 빛이 느껴지는 소망",
    flavor="'전에 주웠던거랑은 다르게 살짝식 빛이 나네요\n금방이라도 꺼질거같긴하지만요...'")
ITEMS["worn_cloak"] = dict(
    name="낡은 망토", tier=2, icon="cloak",
    desc="희미한 소망으로 무언가 소망하자 나타난 망토\n입게되면 쉽게 격파되지 않게 해주는 듯 하다",
    flavor="'옷..이에요?  망토인가? 많이 낡아서 제대로 입고다니진..\n어라 N님 이걸 입어보신다구요..?'",
    effect="효과: 모든 아군 최대 격파체력 +50")
ITEM_ORDER = ["faded_wish", "dim_wish", "small_mirror", "torn_umbrella", "worn_cloak"]
# 제작소 레시피 — cost: {재료 아이템 id: 개수}
WORKSHOP_RECIPES = [
    dict(id="small_mirror", cost={"faded_wish": 15}, max=2),
    dict(id="torn_umbrella", cost={"faded_wish": 25}, max=1),
    dict(id="worn_cloak", cost={"dim_wish": 20}, max=2),
]
LOOT_PHASES = (1, 2)        # 이 PHASE 에서 적을 처치하면 빛바랜 소망을 얻는다
LOOT_CLEAR_AMOUNT = 10      # PHASE 클리어 1회당 빛바랜 소망 지급 개수 (LOOT_PHASES 에 해당하는 페이즈)
DIM_LOOT_PHASES = (3, 4)    # 이 PHASE 에서 적 처치 시 희미한 소망 드랍 (LOOT_RANGE 개)
DIM_CLEAR_AMOUNT = 20       # DIM_LOOT_PHASES 클리어 1회당 희미한 소망 지급 개수
LATE_FADED_CHANCE = 0.5     # PHASE 3 이후 처치 시 빛바랜 소망 추가 드랍 확률
LATE_FADED_RANGE = (4, 6)   # 그때 드랍 개수
LOOT_RANGE = (1, 3)         # 처치 1회당 획득 개수

# ---- 로비 / 타이틀 ----
LB_BG = "#07060D"          # 공허의 색
LB_NEBULA = "#22123F"
LB_RING = "#3A2E70"
LB_LINE = "#6A5FA8"
# (id, 이름, 부제, 색, cx, cy, rx, ry, 콜백 이름)
LOBBY_NODES = [
    ("aspect", "형상", "형상해석 · 장착", STAR_COLOR[3], 225, 250, 105, 84, "lobby_aspect"),
    ("workshop", "제작소", "", SPC, 815, 235, 125, 84, "lobby_workshop"),
    ("battle", "전투", "적과 싸운다", DMG, 520, 440, 185, 78, "lobby_start_battle"),
    ("library", "서재", "도감 열람", BRKC, 520, 665, 200, 72, "lobby_library"),
]
LOBBY_EDGES = [(0, 2), (1, 2), (2, 3)]   # 별자리처럼 이어지는 선

D_SKILLS = [
    dict(name="밀치기", cost=2, kind="dream_push", target="enemy", dmg=20,
         desc="지정한 대상에게 20의 피해"),
    dict(name="별점 사격", cost=4, kind="dream_star", target="enemy", dmg=35,
         desc="지정한 대상에게 35의 피해"),
    dict(name="이터널 드림", cost=6, kind="dream_eternal", target="enemy", dmg=45, splash=20,
         desc="지정한 대상에게 45의 피해 / 이후 양 옆의 대상에게 20의 피해"),
]

# 편성 창에 표시할 아군 정보 (id, 이름, 역할, 색)
ROSTER_INFO = [
    ("N", "N", "저격/근접 전환형", ROSE),
    ("H", "H", "전위 검사", BLUE_H),
    ("C", "C", "후방 지원", CURSE),
    ("D", "D", "드리머", DREAM_PUR),
]

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
HERO_H_SKILLS = [
    dict(name="횡베기", kind="hero_attack", target="enemy", cost=2, dmg=25,
         desc="지정한 적에게 25의 피해"),
    dict(name="스쳐가는 기억", kind="hero_memory", target="enemy", cost=4,
         shield_cost=20, shield_gain=10, dmg=30, bonus_dmg=10,
            desc="대상에게 30 피해 · 보호막 20 이상이면 20 소비, 보호막 10 획득 후 추가 10 피해"),
    dict(name="잔상", kind="hero_afterimage", target="enemy", cost=6,
         shield_cost=40, dmg=55,
            desc="지정한 대상에게 55 피해 · 보호막 40 이상이면 40 소비 후 무작위 적에게 55 피해 재사용"),
]
HERO_H_ECHO = dict(
    name="잔상보", kind="hero_echo", target="enemy", cost=0, dmg=60,
    repeats=2, desc="한 턴에 3회 공격 · 첫 타격은 지정 대상, 다음 2회는 무작위 적 (총 최대 180 피해)")
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
FATE_LOST_C_SKILLS = [
    dict(name="그려내기", kind="fate_attack", target="enemy", cost=0, hp_cost=10,
         dmg=20, fixed_dmg=10,
         desc="체력 10 소비 · 지정한 적에게 20 피해와 방어 무시 고정피해 10"),
    dict(name="휩쓸기", kind="fate_splash", target="enemy", cost=0, hp_cost=15,
         dmg=35, splash=20,
         desc="체력 15 소비 · 지정한 대상에게 35 피해, 양 옆 적에게 20 피해"),
    dict(name="카즈나", kind="fate_stun", target="enemy", cost=0, hp_cost=20,
         dmg=70, stun_turns=1,
         desc="체력 20 소비 · 지정한 대상에게 70 피해, 다음 행동 1회 불가"),
]
FATE_LOST_C_ULTIMATE = dict(
    name="운명", kind="fate_ultimate", target="all_enemies", cost=0, hp_cost=0,
    dmg=80, fate_turns=3,
    desc="필연 소비 · 모든 적에게 80 피해와 운명 3 부여")
IMPERIAL_N_SKILLS = [
    dict(name="별책", kind="imperial_star", target="enemy", cost=3, dmg=40,
        desc="별을 날려 지정한 적에게 40 피해"),
    dict(name="헌신", kind="imperial_devotion", target="ally", cost=4,
        hp=30, brk=30, desc="지정한 아군의 체력과 격파체력 30 회복"),
    dict(name="희망", kind="imperial_hope", target="any", cost=7, cooldown=3,
        desc="아군: 보호막 40 및 자신 체력 30 회복 · 적: 체력/격파체력/고정 피해 50"),
]
IMPERIAL_N_COMMAND = dict(
    name="(관측불가) 섬멸 명령", kind="imperial_command", target="all_enemies",
    cost=10, dmg=100, desc="포격 30발 · 모든 적에게 100 피해, 격파 피해 없음")

PAINTER_N_SKILLS = [
    dict(name="덧칠", cost=1, kind="painter_overcoat", target="enemy", dmg=20, max_dmg=30,
         desc="지정한 적에게 20 피해 (물감 3당 +5, 최대 30) / 물감 3 이상이면 효과 발동 후 물감 2 감소"),
    dict(name="붓 털기", cost=4, kind="painter_brush", target="enemy", dmg=25,
         desc="지정한 대상에게 25 피해 / 대상 물감이 3 이상이면 2 줄이고 무작위 대상에게 재사용 (최대 1회)"),
    dict(name="트리플 아틀리에", cost=6, kind="painter_triple", target="enemy",
         desc="무작위 효과 1가지 발동 (대상 물감 5 이상이면 전부 소비하고 3가지 모두 발동) / "
              "블루: 45 피해 · 다음턴 대상 속도 -1 (최소 1) / 레드: 55 피해 / "
              "그린: 체력피해 없음 · 대상에게 30 격파피해"),
]
COOK_H_SKILLS = [
    dict(name="후라이팬(물리)", cost=2, kind="cook_attack", target="enemy", dmg=25, stun_chance=0.2,
         desc="지정한 대상에게 25 피해 / 20% 확률로 적중한 대상 1턴간 기절"),
    dict(name="예열하기", cost=3, kind="cook_attack", target="enemy", dmg=40, stun_chance=0.2,
         desc="지정한 대상에게 40 피해 / 20% 확률로 적중한 대상 1턴간 기절"),
    dict(name="요리 시작", cost=5, kind="heal", target="ally", hp=40, brk=20,
         desc="아군에게만 사용 가능 / 아군의 체력 40, 격파체력 20 회복"),
]
DISTRIBUTOR_C_SKILLS = [
    dict(name="약간의 불공평한 분배와", cost=2, kind="dist_share", target="any",
         enemy_dmg=25, ally_dmg=25, heal=25,
         desc="적: 25 피해 / 아군: 25 피해 후 그 아군을 제외한 아군 체력 25 회복 (보호막 무시)"),
    dict(name="소소한 재미를 준다면", cost=3, kind="dist_fun", target="any",
         enemy_dmg=50, ally_dmg=40, enemy_fun=3, ally_fun=2,
         desc="적: 50 피해 후 재미난 장난 3 / 아군: 40 피해 후 재미난 장난 2"),
    dict(name="너희를 위한 게임을 시작해줄게", cost=5, kind="dist_game", target="any",
         enemy_dmg=50, ally_dmg=50, ally_fun=7, ally_danger=3,
         desc="적: 다음턴 속도 1로 고정 · 50 피해 / 아군: 50 피해 후 재미난 장난 7, 위험한 장난 3"),
]

ASPECTS = [
    dict(id="n_base", char="N", title="기본 N", star=1, desc="꽝(기본 장착 형상)", skills=N_SKILLS),
    dict(id="h_base", char="H", title="기본 H", star=1, desc="꽝(기본 장착 형상)", skills=H_SKILLS),
    dict(id="c_base", char="C", title="기본 C", star=1, desc="꽝(기본 장착 형상)", skills=C_SKILLS),
    dict(id="n_swordsman", char="N", title="검사 N", star=2, desc="", skills=N_SWORDSMAN_SKILLS),
    dict(id="h_guardian", char="H", title="수호자 H", star=2, desc="", skills=H_GUARDIAN_SKILLS),
    dict(id="c_prophet", char="C", title="예언자 C", star=2, desc="", skills=C_PROPHET_SKILLS),
    dict(id="n_painter", char="N", title="화가 N", star=2,
         desc="공격으로 피해를 입히면 대상에게 물감 +1 (최대 5) / 물감은 스킬로 소비된다",
         skills=PAINTER_N_SKILLS),
    dict(id="h_cook", char="H", title="요리사 H", star=2, desc="", skills=COOK_H_SKILLS),
    dict(id="c_distributor", char="C", title="분배자 C", star=2,
         desc="모든 스킬을 적·아군 모두에게 사용 가능 (대상에 따라 효과가 다름) / "
              "아군에게 피해를 줄 때 격파체력 미감소 · 체력 1 미만으로 내리지 않음 / "
              "재미난 장난: 매턴 체력 10 회복 후 1 감소 · 위험한 장난: 공격력 +15, 턴 종료 시 1 감소",
         skills=DISTRIBUTOR_C_SKILLS),
    dict(id="c_fate_lost", char="C", title="Fate Lost/C", star=3,
         desc="체력 100 소비 시 필연 획득 · 적 처치 시 체력 30 회복",
         skills=FATE_LOST_C_SKILLS),
        dict(id="h_hero", char="H", title="HERO/H", star=3,
            desc="피해를 받으면 보호막 획득 · 사망 시 전투당 1회 부활 및 영웅 버프",
            skills=HERO_H_SKILLS),
            dict(id="n_imperial", char="N", title="Imperial/N", star=3,
                desc="기본 SP 10 · 수호령과 기도로 왕녀 상태 획득",
                skills=IMPERIAL_N_SKILLS),
]
# 가챠 확률: ★ 69.3%, ★★ 29.7%, ★★★ 1%.
# 1성/2성은 기존 비율을 유지하고, 3성은 천장 선택도 가능하다.
for _star, _total in ((1, 69.3), (2, 29.7), (3, 1.0)):
    _grp = [_a for _a in ASPECTS if _a["star"] == _star]
    for _a in _grp:
        _a["w"] = _total / len(_grp)
GACHA_POOL = ASPECTS

# ---- ★★★ 언더보스/C — 특별해석 {거미집} 전용 (ASPECTS 에 넣지 않는다: 일반 해석·일반 도감에는 나오지 않는다) ----
UNDERBOSS_C_SKILLS = [
    dict(name="콜피 탈리오", cost=2, kind="ub_colpi", target="enemy", dmg=25, ammo=1, extra_brk=10,
         fx="bullet", desc="25 피해 · 가속탄 1 소비시 10 추가 격파 고정피해"),
    dict(name="기꺼이 이 탄환으로 꿰뚫어주지", cost=4, kind="ub_pierce", target="enemy", dmg=50,
         ammo=2, extra_brk=20, fx="bullet", line="'한눈 팔았으면 죽어야지'",
         desc="50 피해 · 가속탄 2 소비시 20 추가 격파 고정피해"),
    dict(name="세치오나투라 디 엘리판테", cost=6, kind="ub_elephant", target="enemy", dmg=65,
         ammo=3, extra_brk=30, fx="snipe", line="'사냥 끝! 모조리 해체해줄게!'",
         desc="65 피해 · 가속탄 3 소비시 30 추가 격파 고정피해 · 사용 시 예지 -5 (소비한 가속탄만큼 추가 감소, 최대 -10)"),
]
# 스킬 2 → 2-2 (가속탄 부족시). 노션에 SP 소모가 적혀 있지 않아 스킬 2와 같게 둔다.
UB_SKILL_CERVO = dict(
    name="세치오나투라 디 체르보", cost=4, kind="ub_cervo", target="enemy", dmg=35, fixed_dmg=5,
    ammo=0, fx="bullet", line="'교본, 이게 어려워?'", desc="35 피해 이후 5 고정피해")
# 스킬 3 → 3-2 (예지 0). 스킬 포인트를 소비/회복하지 않는다.
UB_SKILL_DISPOSAL = dict(
    name="처분", cost=0, kind="ub_disposal", target="enemy", dmg=70, ammo=3, extra_brk=35,
    fx="frenzy", line="'지긋 지긋해! 너네도 그새끼도 전부 다!!'",
    desc="가속탄 10 획득 · 70 피해(체력 50% 이하면 2배) · 가속탄 3 소비시 35 추가 격파 고정피해")
UNDERBOSS_ASPECT = dict(id="c_underboss", char="C", title="언더보스/C", star=3,
                        desc="특별해석 {거미집} 전용 형상", skills=UNDERBOSS_C_SKILLS, theme="web")

# ---- ★★★ 마에스트로/H — 특별해석 {거미집} 전용 ----
MA_BONE = "#E6DFD0"          # 뼈의 색 (이펙트/배지)
MA_BLOOD = "#9C1B26"         # 뼈 칼의 핏빛
MA_GOLD = "#FFC83D"          # 큼직한 피해 숫자
MA_GOLD_D = "#7A3B00"        # 숫자 그림자
MA_VIEW_START = 21           # 조망 시작값
MA_VIEW_DROP_CAP = 4         # 조망이 턴당 감소할 수 있는 최대치
MA_COSTS = (1, 3, 5)         # 스킬 1/2/3 의 SP 소모 — 노션에 적혀 있지 않아 임시값
MAESTRO_H_SKILLS = [
    dict(name="해체", cost=MA_COSTS[0], kind="ma_dismantle", target="enemy", dmg=20, gain=1,
         desc="지정한 적에게 20 피해 · 생체재료 +1"),
    dict(name="재료 획득-피로 목욕하는 오브제", cost=MA_COSTS[1], kind="ma_material", target="enemy",
         dmg=40, gain=2, desc="40 피해 · 50% 확률로 [간이늑골] 발동 · 생체재료 +2"),
    dict(name="티비아의 멜로디", cost=MA_COSTS[2], kind="ma_melody", target="enemy", dmg=55,
         splash=45, gain=3,
         line="'들리세요? 한쌍의 상완골과 스물 네개의 늑골이 자아내는 (관측불가)의  멜로디가!'",
         desc="55 피해 · 걸작 보유시 양 옆 대상에게 45 피해 · 생체재료 +3"),
]
# 스킬 3 → 3-2 (조망 0, 전투당 1회). 스킬 포인트를 소모/획득하지 않고 수비 스킬을 무시한다.
MA_SKILL_CLOSING = dict(
    name="폐장", cost=0, kind="ma_closing", target="all_enemies", dmg=120,
    line="'폐장시간이 되었답니다. 그럼, 안녕히!'",
    desc="모든 적에게 120 고정피해(수비 무시) · 모든 적에게 간이늑골 3 · 아군에게 선율")
MAESTRO_ASPECT = dict(id="h_maestro", char="H", title="마에스트로/H", star=3,
                      desc="특별해석 {거미집} 전용 형상", skills=MAESTRO_H_SKILLS, theme="web")

# ---- ★★★ 큰누님/N — 특별해석 {거미집} 전용 ----
BS_FIRE = "#FF7A2E"          # 불꽃/화상 색
BS_WRAP_START = 3            # 전투 시작시 포장
BS_FUN_START = 2             # 전투 시작시 달아오르는 재미
BS_WRAP_CUT = 5              # 포장 1당 스킬 피해 감소량
BS_BURN = 5                  # 레바테인 상태 스킬 적중시 화상
# 큰누님/N 이펙트 팔레트 (보라 / 주황)
BSX_PUR = "#B04CFF"
BSX_PUR_D = "#3E1366"
BSX_PUR_L = "#E2B8FF"
BSX_ORG = "#FF8A2E"
BSX_ORG_D = "#8A3200"
BSX_ORG_L = "#FFD08A"
BIGSIS_N_SKILLS = [
    dict(name="짓밟기", cost=2, kind="bs_stomp", target="enemy", dmg=20, wrap_cut=BS_WRAP_CUT, fun_cost=0,
         desc="지정한 대상에게 20 피해 / 포장 1당 피해 5 감소 (20→5까지)"),
    dict(name="고작 이거에 부셔지지 말라고!", cost=4, kind="bs_crush", target="enemy", dmg=45,
         wrap_cut=BS_WRAP_CUT, fun_cost=1,
         desc="지정한 대상에게 45 피해 / 포장 1당 피해 5 감소 / 달아오르는 재미 1 감소"),
    dict(name="원한 스탬핑", cost=6, kind="bs_stamp", target="enemy", dmg=65, wrap_cut=BS_WRAP_CUT, fun_cost=1,
         desc="지정한 대상에게 65 피해 / 포장 1당 피해 5 감소 (65→50까지) / 달아오르는 재미 1 감소"),
]
# 레바테인 전용 스킬 — 소모 SP 는 노션에 적혀 있지 않아 원래 스킬 1/2/3 과 같게 두었다.
BIGSIS_LEVA_SKILLS = [
    dict(name="배때지를 갈라주지", cost=2, kind="bs_l_belly", target="enemy", dmg=25,
         desc="[레바테인] 지정한 대상에게 25 피해"),
    dict(name="칼빵 [레바테인]", cost=4, kind="bs_l_slash", target="enemy", dmg=65, extra_brk=15, speed_down=3,
         desc="[레바테인] 65 피해 / 15 고정 격파피해 / 다음턴 속도 감소 3"),
    dict(name="즉결처형 [레바테인]", cost=6, kind="bs_l_execute", target="enemy", dmg=100, extra_brk=20,
         speed_down=3, stun=True,
         desc="[레바테인] 100 피해 / 20 고정 격파피해 / 다음턴 속도 감소 3 · 기절 부여"),
]
BIGSIS_ASPECT = dict(id="n_bigsis", char="N", title="큰누님/N", star=3,
                     desc="특별해석 {거미집} 전용 형상", skills=BIGSIS_N_SKILLS, theme="web")

# ---- ★★★ 신탁 대행자/H — 특별해석 {거미집} 전용 ----
OR_GOLD = "#FFD56B"
OR_GOLD_L = "#FFF6D6"
OR_SKY = "#8FD8FF"
OR_DEEP = "#2B4A7A"
OR_COSTS = (2, 4, 6)         # 스킬 1/2/3 의 SP 소모 — 스킬 3 은 노션에 없어 임시값
OR_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}
OR_UNLOCK_LINES = {2: "무아몽중", 3: "아비규환", 4: "지리멸렬"}   # 해금 단계 상승 대사
# 신탁 단말기 무기 9종 — line 에 원문 대사를 직접 넣는다 (지금은 괄호 안 짧은 이름)
ORACLE_WEAPONS = [
    dict(id="axe", name="손도끼로 갈비뼈를 찍어 내릴 때는…", line="(손도끼)", eff="추가 효과 없음"),
    dict(id="stiletto", name="스틸레토로 허파를 꿰뚫을 때는…", line="(스틸레토)", eff="추가 효과 없음"),
    dict(id="bastard", name="바스타드 소드로 어깨와 머리를 짓이길 때는…", line="(바스타드 소드)", eff="추가 효과 없음"),
    dict(id="rapier", name="레이피어로 몸에 10개 이상의 구멍을 내야할 때는…(레이피어)", line="(레이피어)", eff="속도 감소 1 부여"),
    dict(id="hammer", name="망치로 뒤통수를 으깨야 할 때는…(망치)", line="(망치)", eff="격파피해 +5"),
    dict(id="sword", name="커다란 검으로 몸통을 갈라야 할 때는…", line="(검)", eff="피해량 +5"),
    dict(id="lance", name="랜스로 20인치의 구멍을 내야 할 때는…", line="(랜스)", eff="속도 감소 2 부여"),
    dict(id="whip", name="채찍으로 살점을 만 갈래 떼어내야 할 때는…", line="(채찍)", eff="격파피해 +10"),
    dict(id="scythe", name="낫으로… 누군가처럼 공간을 따라 베어내야 할 때는…", line="(낫)", eff="피해량 ×1.3 후 +10"),
]
ORACLE_BY_ID = dict((w["id"], w) for w in ORACLE_WEAPONS)
ORACLE_H_SKILLS = [
    dict(name="얼어붙은 피를 삼백삼십 휘감아", cost=OR_COSTS[0], kind="or_s1", target="enemy", dmg=20,
         desc="지정한 대상에게 20 피해 · 신탁 단말기 발동"),
    dict(name="소리 없이 손뼉을 쳐", cost=OR_COSTS[1], kind="or_s2", target="enemy", dmg=45,
         full="소리 없이 손뼉을 쳐 즐기고, 목소리 없이 슬피 꿰뚫어",
         desc="소리 없이 손뼉을 쳐 즐기고, 목소리 없이 슬피 꿰뚫어 / 지정한 대상에게 45 피해 · 신탁 단말기 발동"),
    dict(name="날 세워 칼날을 웃거라", cost=OR_COSTS[2], kind="or_s3", target="enemy", dmg=65,
         full="날 세워 칼날을 웃거라, 낙옆향 나듯 폭포를 울거라",
         desc="날 세워 칼날을 웃거라, 낙옆향 나듯 폭포를 울거라 / 지정한 대상에게 65 피해 · 가호 1 · 신탁 단말기 발동"),
]
OR_SKILL_FURIOSO = dict(
    name="Furioso-Replica", cost=0, kind="or_furioso", target="enemy", dmg=35,
    desc="SP 소모/회복 없음 · 방어행동 무시 · 총 9회 적중 (적중마다 35 피해 + 신탁 단말기) / "
         "모든 적을 무작위 공격 · 첫 타격과 마지막 타격은 지정 대상 · 9번째는 (낫) 고정")
ORACLE_ASPECT = dict(id="h_oracle", char="H", title="신탁 대행자/H", star=3,
                     desc="특별해석 {거미집} 전용 형상", skills=ORACLE_H_SKILLS, theme="web")

# ---- 환상(幻想) — 궁극기 ----
ROSE_D = "#A3124A"           # 로즈 오브 샤론 — 짙은 장미
ROSE_L = "#FFC2E2"           # 로즈 오브 샤론 — 밝은 분홍
ULT_GAIN_PER_SP = 5          # 스킬 포인트 1 소비당 환상도 +5%
ULT_COOLDOWN = 4             # 사용 후 이 턴 수 동안 사용 불가
ULT_BLOOM_MULT = 1.2         # 개화 — 받는 피해 +20%
ULT_PORTRAITS = {"N": "N_Ult_Cutin.png"}    # 컷인 이미지 (없으면 자리표시)
# 지금은 N 만. 다른 캐릭터는 같은 형식으로 항목을 추가하면 [환상] 버튼이 열린다.
ULTIMATES = {
    "N": dict(name="로즈 오브 샤론", title_en="ROSE OF SHARON", cost=30, brk=15, dmg=80, bloom=3,
              color=ROSE, color_d=ROSE_D, color_l=ROSE_L,
              desc="지정한 대상에게 80의 피해 / 이후 개화 3 부여"),
}

GACHA_COST_SINGLE = 10     # 1회 해석 조각
GACHA_COST_TEN = 100       # 10회 비용으로 11회 해석 (+1 보너스)
GACHA_PITY_TIER2 = 200     # 형상파편 200 — ★★ 확정 교환
GACHA_PITY_TIER3 = 350     # 형상파편 350 — ★★★ 선택 교환

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


# ----------------------------------------------------------------------------
# 전투효과 도감 데이터 (F 키) — 카테고리 순서대로 표시된다.
#  · desc 의 ' / ' 는 줄바꿈이다.
# ----------------------------------------------------------------------------
EFFECT_CATS = [
    ("buff", "버프 (공통)", HEAL),
    ("debuff", "디버프 (공통)", CURSE),
    ("aspect", "형상 고유 효과", SHLD),
]
EFFECTS = [
    # ---- 버프 ----
    dict(id="guard", cat="buff", name="방어", color=HEAL, scope="공통 · 태세",
         desc="지정 즉시 태세를 취한다 (속도 무관) / 피격 시 주사위 1~5 → 그 값×10% 피해 감소, 6 → 80% 감소 / "
              "SP +2 · 1회 피격으로 소모 · 라운드 시작 시 해제"),
    dict(id="evade", cat="buff", name="회피", color=SPC, scope="공통 · 태세",
         desc="지정 즉시 태세를 취한다 (속도 무관) / 피격 시 양측 주사위 대결 — 내 값이 상대와 같거나 더 크면 피해 0 / "
              "SP +2 · 1회 피격으로 소모 · 라운드 시작 시 해제"),
    dict(id="shield", cat="buff", name="보호막", color=SHLD, scope="공통 · 수치형",
         desc="체력보다 먼저 피해를 흡수한다 (잔여량이 배지에 표시) / "
              "보통 최대체력을 초과해 생성될 수 없다 (HERO/H 영웅 버프 중에는 제한 해제)"),
    dict(id="focus", cat="buff", name="집중", color=SPC, scope="검사 N · 집중 참격",
         desc="이번 라운드에 집중 상태 진입 → 다음 라운드에 지정했던 대상에게 50 피해 / "
              "그 사이 격파당하면 집중이 끊긴다"),
    dict(id="undying", cat="buff", name="불사", color=HEAL, scope="보스 증강 · 불사의 가호",
         desc="전투당 1회, 사망 직전 체력 1로 버티며 불사 상태(2턴)에 진입 / "
              "불사 중에는 체력이 1 밑으로 내려가지 않는다 (배지 숫자 = 남은 턴)"),
    # ---- 디버프 ----
    dict(id="broken", cat="debuff", name="격파", color=BRKC, scope="공통 · 격파체력 0",
         desc="격파체력이 0이 되면 발동 / 다음 행동 1회 불가 · 받는 피해 ×1.5 / "
              "격파체력 회복 무효 · 집중·잔상보가 중단된다 / 해제되면 격파체력이 최대치로 회복"),
    dict(id="curse", cat="debuff", name="저주", color=CURSE, scope="예언 · 파멸의 예연",
         desc="지정한 적이 3턴간 받는 피해 ×1.5 / 격파 상태와 곱연산으로 중첩 (최대 ×2.25) / "
              "배지 숫자 = 남은 턴"),
    dict(id="stun", cat="debuff", name="기절", color=CURSE, scope="카즈나 · 후라이팬 · 예열하기",
         desc="다음 행동 1회를 하지 못한다 / 후라이팬(물리)·예열하기는 20% 확률로 부여 / "
              "배지 숫자 = 남은 행동 불가 횟수"),
    dict(id="fate", cat="debuff", name="운명", color=STAR_COLOR[3], scope="Fate Lost/C · 운명",
         desc="라운드 시작마다 5 피해를 입는다 / 배지 숫자 = 남은 횟수 (부여 시 3)"),
    dict(id="speed_penalty", cat="debuff", name="속도 저하", color=CURSE, scope="예언자 C · 시간 예언",
         desc="다음 라운드 속도 주사위의 최대값이 감소한다 (최소 1) / 한 라운드만 적용되고 사라진다"),
    dict(id="speed_minus", cat="debuff", name="속도 감소", color=PAINT_BLUE, scope="화가 N · 블루",
         desc="다음 라운드 속도 판정 결과가 1 감소한다 (최소 1) / 한 라운드만 적용되고 사라진다"),
    dict(id="speed_fix", cat="debuff", name="속도 고정", color=CURSE, scope="분배자 C · 너희를 위한 게임",
         desc="다음 라운드 속도가 1로 고정된다 / 한 라운드만 적용되고 사라진다"),
    dict(id="bloom", cat="debuff", name="개화", color=ROSE, scope="N · 로즈 오브 샤론",
         desc="받는 피해가 20% 증가한다 (격파·저주와 곱연산) / 턴 종료시 1 감소 · 0이 되면 소멸 / "
              "배지 숫자 = 남은 턴"),
    # ---- 형상 고유 ----
    dict(id="paint", cat="aspect", name="물감", color=PAINT_RED, scope="화가 N",
         desc="화가 N이 피해를 입힐 때마다 대상에게 물감 +1 (최대 5) / 물감 3당 덧칠 피해 +5 (최대 30) / "
              "붓 털기: 대상 물감 3 이상이면 2 소모 후 재사용 / 트리플 아틀리에: 물감 5 이상이면 전부 소비하고 3색 모두 발동"),
    dict(id="fun", cat="aspect", name="재미난 장난", color=HEAL, scope="분배자 C",
         desc="라운드 시작마다 체력 10 회복 후 1 감소 / 배지 숫자 = 남은 횟수"),
    dict(id="danger", cat="aspect", name="위험한 장난", color=CURSE, scope="분배자 C",
         desc="공격력 +15 (전이 피해에는 적용되지 않음) / 라운드 종료 시 1 감소 / 배지 숫자 = 남은 횟수"),
    dict(id="necessity", cat="aspect", name="필연", color=STAR_COLOR[3], scope="Fate Lost/C",
         desc="체력 소비가 누적 100이 되면 획득 (배지 '필연 n/100' = 진행도) / "
              "필연 보유 중 스킬 3이 [운명]으로 변경 / [운명] 사용 시 필연을 소비"),
    dict(id="hero", cat="aspect", name="영웅", color=STAR_COLOR[3], scope="HERO/H",
         desc="HERO/H가 사망 시 전투당 1회 부활하며 획득 / 보호막이 최대체력을 초과해 쌓일 수 있다 / "
              "스킬 피해의 10%만큼 보호막 획득 / 스킬 3이 전투당 1회 [잔상보]로 변경"),
    dict(id="echo", cat="aspect", name="잔상보", color=STAR_COLOR[3], scope="HERO/H · 영웅 버프",
         desc="한 턴에 3회 공격 — 첫 타격은 지정 대상, 이후 2회는 무작위 적 / 기절·격파·사망 시 중단 / "
              "배지 숫자 = 남은 타격 수"),
    dict(id="prayer", cat="aspect", name="기도", color=HEAL, scope="Imperial/N",
         desc="수호령 사용 즉시 +20, 전이된 피해만큼 추가 획득 / 120에 도달하면 [왕녀] 상태로 전환 / "
              "배지 숫자 = 현재 기도량"),
    dict(id="guardian", cat="aspect", name="수호령", color=STAR_COLOR[3], scope="Imperial/N",
         desc="이번 라운드 동안 받는 피해의 절반을 무작위 아군에게 전이 / SP +2 회복 · 기도 +20"),
    dict(id="princess", cat="aspect", name="왕녀", color=STAR_COLOR[3], scope="Imperial/N",
         desc="기도 120 달성 시 진입 — SP 최대 · 매턴 체력 +10 · SP +4 / "
              "스킬 3이 [(관측불가) 섬멸 명령]으로 변경 / 전환 턴에는 체력·격파체력이 1 밑으로 내려가지 않는다"),
]


CHAR_IMG_BOX = 472   # 등장인물 도감 — 이미지 표시 상자 한 변(px)

# ----------------------------------------------------------------------------
# 등장인물 도감 데이터 (서재 → 등장인물 도감)
#  · images: [(캡션, 파일명), ...] — 항상 2칸. 파일명이 None 이면 '준비 중'으로 표시된다.
#  · 이미지는 NHC.py 와 같은 폴더(또는 images / assets 폴더)에서 찾는다.
# ----------------------------------------------------------------------------
CHARACTERS = [
    dict(id="N", color=ROSE, role="저격/근접 전환형",
         images=[("컨셉 아트", "N_SD_스텐딩일러.png"), ("SD", "N.png")],
         desc="핑크빛 머리를 길게 땋아 내리고, 토끼 모양 머리핀과 검은 리본을 단 소녀.\n"
              "분홍색 후드 재킷에 검은 플리츠 스커트, 두툼한 부츠 차림이며 평소에는 무기를 등에 멘다.\n"
              "무기는 형태를 바꾸는 변형 병기로, 검 형태와 저격총 형태를 오가며 싸운다.\n"
              "\n"
              "기본 스킬 — 조준 사격 · 관통 저격 · 진입 저지 저격 (분홍빛 섬광)"),
    dict(id="H", color=BLUE_H, role="전위 검사",
         images=[("컨셉 아트", "H_SD.png"), ("이미지", "H_치비")],
         desc="전위에서 검을 휘두르는 검사.\n"
              "\n"
              "기본 스킬 — 베기 · 연속 참격 · 진-걸착 (푸른 검광)\n"
              "컨셉 아트와 이미지는 준비 중이다."),
    dict(id="C", color=CURSE, role="후방 지원",
         images=[("컨셉 아트", "C_SD.png"), ("SD", "C_치비.png")],
         desc="후방에서 아군을 돕는 지원가.\n"
              "\n"
              "기본 스킬 — 응급 처치 · 정신 집중 · 파멸의 예연\n"
              "컨셉 아트와 이미지는 준비 중이다."),
    dict(id="D", color=DREAM_PUR, role="드리머",
             images=[("컨셉 아트", "D_SD.png"), ("SD", "준비중")],
             desc="꿈과 관련된 힘을 다루는 전설중 하나지만\n"
                  "나이가 조금 어린편이다\n"
                  "자기보다 한사이즈 큰 겉옷을 걸치고 있고\n"
                  "안엔 교복처럼 보이는 옷을 입고있으나 디자인이 다른듯 하다\n"
                  "권총 한자루만 휴대하는데 화력이 많이 이상한 특이한 무기다\n"
                  "기본 스킬 — 밀치기 · 별점사격 · 이터널 드림\n"
                  "컨셉 아트와 이미지는 준비 중이다."),
]


# Imperial/N 특별 일러스트 — 형상 'n_imperial' 을 획득해야 열린다.
next(_c for _c in CHARACTERS if _c["id"] == "N")["special"] = dict(
    aspect="n_imperial", title="Imperial/N 특별 일러스트",
    images=[("형상 폼", "N_Imperial_Chibi.png")],
    desc="N이 Imperial/N 형상을 장착했을 때의 모습.\n"
         "\n"
         "(관측불가)의 어느 세계선의 형상이 발현된 N의 모습.\n"
         "평화롭던, 평화롭지 않던 어느 세계의 N은 H와 만나지 못하였다.\n"
         "수많은 굴레를 온몸으로 견뎠고, 잊혀졌어야 했던 기억들은 수많은 굴레 속에서\n"
         "변화에 적응하여 자신을 바꿔나갔고, 기억하길 포기하고 받아드리며 굴레 속의 과정이 잊혀지지 않았다.\n"
         "'정말 이것으로 족하겠습니까 (관측불가)님'\n"
         "'더 나아가봤자 뭐 달라진다고'\n"
         "그녀의 외침은 이미 이 상황을 몆번이나 겪었다는듯 말한다.\n" 
         "'그러면 돌아가겠..'\n" 
         "'아니. 난 여기 남는다'" 
         "'..혼자서 괜찮으시겠습니까'\n" \
         "'내가 알아서 하겠다. 어서 가라'\n" 
         "그녀를 따라왔던 대신이 떠나고, 그녀는 주머니에서 빛바랜 무언갈 꺼내든다\n" 
         "'끼이익..'\n"
         "'..하.'\n" 
         "문을 연 그녀는 앞으로 나아간다\n" 
         "그리고 눈앞에서. (관측불가)를 마주한다\n"
         "'제가 고통받아야 했던 이유가 대체 무엇입니까'\n" 
         "'..돌아가다오 딸.. 분명 이곳을 못오게 했을텐ㄷ..'\n" 
         "'제가 그것조차 눈치를 못챘을거라고 생각하신겁니까?'\n" 
         "그리곤 그녀는 자신의 무구를 들어올리며 말한다\n" 
         "'언제까지고 반복하실겁니까.\n" 
         "'...'" 
         "'답해주지 않으실거란거도 알고있습니다. 제가 이 상황을 한두번 본거도 아닙니다.'\n" 
         "'35억번째부턴 세는거도 포기했습니다.'\n" 
         "그녀는 이제 지쳤다는듯이 총구를 겨눠\n" 
         "'그만두세요.'\n" 
         "**탕**\n" 
         "공허 속에서 한발의 총성이 울렸다.\n" 
         "쓰러진 (관측불가)를 지나쳐 (관측불가)가 앉아있던 왕좌에 그녀가 앉아.\n"
         "'..거 아무도 없느냐.'\n" 
         "고요 속에서 그녀가 외치지만. 아무도 답하지도,답해주지도 못해\n" 
         "'끝났나.'\n" 
         "'아무도 듣지 못하겠지만. 난 이제 이 왕국을 다시 새우겠다.\n" 
         "공주로써.. 아니. 왕녀로써 다시 만들어나가겠다.\n" 
         "그러곤. 자신이 멈추려 했던 굴레를 스스로 다시 시작해\n" 
         "'왕? 아버지? 당신은 그렇게 불릴 자격도 없었어. 내가 다시 바로잡겠다'\n")


# Fate Lost/C 특별 일러스트 — 형상 'c_fate_lost' 를 획득해야 열린다.
#  · story 에 스토리를 채워 넣는다. 길면 따옴표 3개(""")로 여러 줄을 한 번에 적어도 된다.
next(_c for _c in CHARACTERS if _c["id"] == "C")["special"] = dict(
    aspect="c_fate_lost", title="Fate Lost/C 특별 일러스트",
    images=[("형상 폼", "C_FateLost_Chibi.png")],
    desc="C가 Fate Lost/C 형상을 장착했을 때의 모습.\n"
         "\n"
         "체력을 대가로 싸우는 형상. 체력 소비가 누적 100이 되면 필연을 얻고, "
         "적을 쓰러뜨리면 체력 30을 회복한다.",
        story="""
        (관측불가)를 눈앞에서 놓친 뒤 약속을 지키지 못했다는 죄책감으로
        봉인석을 부수고 눈앞의 모든걸 파괴하는 어느 세계선의 N의 형상
        '어디로 간거지'
        자신이 전부 무너트린 곳을 하염없이 방황하며 소녀는 외쳐
        '이렇게까지 했는데도 다시 돌아오지 않는거야?'
        '널 구하겠다고, 무슨 수를 써서도 널 지키겠다고 약속했는데..'
        덧없는 외마디를 외치고, 그녀는 조용히 마법을 영창해
        '신체 손상 80%이상 발생! 즉시 치료를 받으십시오!'
        **콰직**
        'ㅅ..ㅅ..시.ㄴ...'
        '닥쳐'
        자신에게 유일하게 말을 건내주던 기기를 부시고 그녀는 어디론가 나아가
        '얼마나.. 얼마나 더 내가..'
        말을 이어가려다가 고통스러운지 멈춰
        '..ㅎ..하..아니야'
        '여기까지 온 이상 난 끝을 봐야겠어'
        그러곤 또 다시 어느 도시, 마을, 골목으로 떠나가
        돌아오지 않는단걸 알고있지만 눈 먼 분노는 끝내 목적을 잃고 스스로 죽어가며 세상을 죽이게 돼
        '난.. 이 지옥에 홀로 살아갈 수 없어..'
        ..그 아이가 돌아올 수 있다면.. 부디 만날 수 있길.
        """)


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


# =============================================================================
# ★★★ Orchestra/D  (오케스트라 패치)
# =============================================================================
ORCH_IV = "#FFF4D6"          # 악보 — 아이보리
ORCH_GOLD = "#E8C468"        # 금빛 음표
ORCH_RED = "#B0263A"         # 피날레 — 와인색
ORCH_AUD_MAX = 20            # 관객 최대치
ORCH_REQ = {"orch_s1b": 5, "orch_s2b": 8, "orch_s3b": 10}   # 변형 스킬이 열리는 관객 수
ORCH_FINALE_TURNS = 4        # 피날레 진입 후 이 턴이 지나면 전투불능 (진입 다음 턴부터 3턴 사용 가능)
ORCH_S3_BASE = 30            # 포르티시모 기본 피해
ORCH_S3_PER_SP = 10          # 소모 SP 1 증가당 추가 피해 (1SP = 기본 피해)
ORCH_S1 = dict(name="연주 준비", cost=1, kind="orch_s1", target="enemy", dmg=20, aud=0.5,
               desc="지정한 대상에게 지휘하며 20의 피해 · 관객 +0.5 (SP 소비량/2)")
ORCH_S1B = dict(name="레가토", cost=1, kind="orch_s1b", target="enemy", dmg=35, aud=1, sp_back=1,
                desc="사용시 SP 1 회복 · 관객 1 획득 / 관객 5 이상일 때만 (스킬 1 대신) / "
                     "지정한 대상에게 원형으로 회전하는 악보를 순환시켜 35의 피해")
ORCH_S2 = dict(name="지휘", cost=2, kind="orch_s2", target="enemy", dmg=30, splash=15, aud=1,
               desc="지정한 적에게 악보의 파도를 날려 30의 피해 / 그 후 양 옆 적에게 절반의 피해 · 관객 +1")
ORCH_S2B = dict(name="포르테", cost=3, kind="orch_s2b", target="enemy", dmg=45, splash=22, aud=3, sp_back=2,
                desc="사용시 SP 2 회복 · 관객 3 획득 / 관객 8 이상일 때만 (스킬 2 대신) / "
                     "지정한 적에게 45의 피해 · 양 옆 적에게 절반의 피해 (피해량은 임시값)")
ORCH_S3 = dict(name="포르티시모", cost=1, kind="orch_s3", target="enemy", dmg=ORCH_S3_BASE, aud=None,
               desc="사용 전 이 버튼을 연타해 소모 SP 를 1~6 으로 늘릴 수 있다 / "
                    "지정한 적에게 30의 피해, 소모 SP 1 증가당 피해 10 증가 / "
                    "소모한 SP 만큼 관객 획득 · 소모 SP 3 이상이면 모든 적을 공격")
ORCH_S3B = dict(name="다카포 알 피네", cost=6, kind="orch_s3b", target="all_enemies", dmg=65, brk=25,
                aud=4, sp_back=3,
                desc="사용시 SP 3 회복 · 관객 4 획득 / 관객 10 이상일 때만 (스킬 3 대신) / "
                     "모든 적에게 65의 피해 · 이후 25의 고정 격파피해 / 다음 턴 적중한 모든 적 속도 감소 1")
ORCH_FINALE = dict(name="피날레", cost=0, kind="orch_finale", target="all_enemies",
                   desc="피날레 상태에서 스킬 3 을 대신함 · SP 소모/획득 없음 · 방어행동 무시 / "
                        "1회: 자신의 체력·격파체력 최대 회복 (ONE MOVEMENT) / "
                        "2회: 모든 적에게 체력·격파체력 50 고정피해 (TWO MOVEMENT) / "
                        "3회: 모든 적과 아군에게 100 고정피해 (FINALE)")
ORCH_SKILLS = [ORCH_S1, ORCH_S2, ORCH_S3]
ASPECTS.append(dict(
    id="d_orchestra", char="D", title="Orchestra/D", star=3,
    desc="기본효과: 스킬 포인트 소비량/2 만큼 관객 획득 (최대 20) · 관객 수치에 따라 스킬 1/2/3 이 "
         "1-2 레가토(5+) / 2-2 포르테(8+) / 3-2 다카포 알 피네(10+)로 변경 / "
         "패시브: 전투불능에 이르는 피해를 받을 때 관객이 20이면 [피날레] 진입 — 전투불능 되지 않음 / "
         "피날레: 격파 상태 해제 + 이번 전투 격파 면역 · 피날레 스킬 외 사용 불가 · "
         "피날레 스킬 3번 사용 또는 4턴 경과시 전투불능",
    skills=ORCH_SKILLS))
# 오케스트라를 장착한 뒤 되돌릴 수 있도록 기본 D 형상(★1)을 추가한다.
if not any(_a["id"] == "d_base" for _a in ASPECTS):
    _ci = next((i for i, _a in enumerate(ASPECTS) if _a["id"] == "c_base"), len(ASPECTS) - 1)
    ASPECTS.insert(_ci + 1, dict(id="d_base", char="D", title="기본 D", star=1,
                                 desc="꽝(기본 장착 형상)", skills=D_SKILLS))
# 가챠 확률 재계산: ★ 69.3%, ★★ 29.7%, ★★★ 1% (등급 안에서 균등)
for _star, _total in ((1, 69.3), (2, 29.7), (3, 1.0)):
    _grp = [_a for _a in ASPECTS if _a["star"] == _star]
    for _a in _grp:
        _a["w"] = _total / len(_grp)
if "GACHA_POOL" in globals() and GACHA_POOL is not ASPECTS:
    GACHA_POOL[:] = ASPECTS


# =============================================================================
# 특별해석 {거미집}  (픽업 해석 테마)
#  · ★★★ 은 거미집 4종만 나온다 (기존 ★★★ 형상은 이 테마에서 제외).
#  · ★ / ★★ 형상과 확률(★ 69.3% · ★★ 29.7% · ★★★ 1%)은 일반 해석과 같다.
# =============================================================================
WEB_COLOR = UB_RED
SPIDER_ASPECTS = [UNDERBOSS_ASPECT, MAESTRO_ASPECT, BIGSIS_ASPECT, ORACLE_ASPECT]
ALL_ASPECTS = ASPECTS + SPIDER_ASPECTS
WAL_COLOR = "#3FD17A"        # {발푸르기스의 밤} — 초록 톤
GACHA_BANNERS = [
    dict(id="normal", name="일반 해석", color=SHLD, sub="조각으로 형상을 해석한다"),
    dict(id="web", name="특별해석 {거미집}", color=WEB_COLOR,
         sub="★★★ 은 거미집 형상 4종만 등장한다"),
    dict(id="wal", name="특별해석 {발푸르기스의 밤}", color=WAL_COLOR,
         sub="임시 배너 · ★★★ 은 나오지 않는다"),
]
BANNER_IDS = [b["id"] for b in GACHA_BANNERS]

# 테마 전용 도감 (서재 2페이지~). aspects: 그 테마에서만 나오는 형상 / effects: 전용 전투효과
THEMES = {
    "web": dict(label="거미집", color=WEB_COLOR, aspects=SPIDER_ASPECTS),
    "wal": dict(label="발푸르기스의 밤", color=WAL_COLOR, aspects=[]),
}


def banner_aspects(banner):
    """이 해석 테마에서 나올 수 있는 형상 전체."""
    if banner == "normal":
        return list(ASPECTS)
    base = [a for a in ASPECTS if a["star"] <= 2]
    return base + (SPIDER_ASPECTS if banner == "web" else [])


def banner_rates(banner):
    """등급별 확률(%) — 이 테마에 없는 등급은 빠지고 나머지가 100%가 되도록 맞춘다."""
    pool = banner_aspects(banner)
    base = {1: 69.3, 2: 29.7, 3: 1.0}
    have = {st: v for st, v in base.items() if any(a["star"] == st for a in pool)}
    tot = sum(have.values())
    return {st: v * 100.0 / tot for st, v in have.items()}


def banner_pool(banner):
    """(형상, 가중치) 목록. 등급 안에서는 균등하다."""
    pool = banner_aspects(banner)
    out = []
    for star, total in banner_rates(banner).items():
        grp = [a for a in pool if a["star"] == star]
        out.extend((a, total / len(grp)) for a in grp)
    return out


WEB_EFFECT_CATS = [
    ("buff", "버프 (거미집 전용)", HEAL),
    ("debuff", "디버프 (거미집 전용)", CURSE),
    ("gauge", "형상 고유 수치 (거미집 전용)", SHLD),
]
WEB_EFFECTS = [
    # ---- 버프 ----
    dict(id="w_foresight", cat="buff", name="예지", color=UB_RED, scope="언더보스/C · 불완전한 예지안",
         desc="공격당할 때 예지에 따라 주사위로 자동 회피 / 30~25: 5~6 · 24~19: 4~5 · 18~13: 3~4 · 12 이하: 1~3 / "
              "회피 성공 시 예지 -3 · 턴 종료마다 -2 / 0이 되면 예지안 과열 / 배지 숫자 = 현재 예지"),
    dict(id="w_ammo", cat="buff", name="가속탄", color=SPC, scope="언더보스/C",
         desc="스킬 1/2/3 사용 시 1/2/3 소비 (최대 10) / 부족하면 추가 격파 고정피해가 발동하지 않는다 / "
              "부족 시 스킬 2가 [세치오나투라 디 체르보]로 변경, 재장전되면 복귀 / [처분] 사용 시 10 획득"),
    dict(id="w_masterpiece", cat="buff", name="걸작", color=SPC, scope="마에스트로/H · 일생의 작품",
         desc="생체재료가 10에 도달하면 전부 소비하고 이번 전투 동안 획득 / 공격력 +5 / "
              "티비아의 멜로디가 양 옆 대상에게도 피해를 준다"),
    dict(id="w_melody", cat="buff", name="선율", color=MA_BONE, scope="마에스트로/H · 폐장",
         desc="[폐장] 사용 시 아군이 획득 (이번 전투 동안) / 속도 +1 (최대 6) · 공격력 +5"),
    dict(id="w_leva", cat="buff", name="레바테인", color=UB_RED, scope="큰누님/N · 봉인된 검",
         desc="포장이 0이 되면 개방 / 공격력 +5 · 모든 스킬이 레바테인 전용 스킬로 변경 / "
              "스킬이 적중하면 화상 5 부여 / 달아오르는 재미가 제거된다"),
    dict(id="w_counter", cat="buff", name="반격", color=DMG, scope="큰누님/N · 방어행동",
         desc="방어 행동이 방어 → 반격으로 변경 / 사용 턴 동안 받는 피해 40% 감소, 이후 받은 피해량의 50%를 반격 (처치 불가) / "
              "반격 2회 사용마다 달아오르는 재미 -1"),
    dict(id="w_unlock", cat="buff", name="해금", color=OR_GOLD, scope="신탁 대행자/H",
         desc="전투 시작 시 해금 I / II: 속도 최소값 +1 / III: 속도 최소값 +1 · 공격력 +5 / "
              "IV: 속도 최소값 +2 · 공격력 +5 (중첩되지 않음) / 가호가 2 이상이면 한 단계 상승"),
    # ---- 디버프 ----
    dict(id="w_rib", cat="debuff", name="간이늑골", color=MA_BONE, scope="마에스트로/H · 설치 미술 제 3호",
         desc="대상의 속도 주사위 최대값이 절반 감소한다 / 매 턴 1 감소 · 0이 되면 소멸 / "
              "[폐장]은 모든 적에게 3을 부여한다"),
    dict(id="w_burn", cat="debuff", name="화상", color=BS_FIRE, scope="큰누님/N · 레바테인",
         desc="라운드 시작 시 수치만큼 피해를 입고 전부 제거된다 / 레바테인 상태에서 스킬이 적중하면 5 부여 / "
              "배지 숫자 = 화상 수치"),
    # ---- 형상 고유 수치 ----
    dict(id="w_overheat", cat="gauge", name="예지안 과열", color=UB_RED, scope="언더보스/C",
         desc="예지가 0이 되면 시작 / 매 턴 +10 · 30이 되면 예지 30으로 복귀 / "
              "과열 중에는 자동 회피 불가 · 스킬 3이 [처분]으로 변경 (한 번 쓰면 스킬 3으로 복귀)"),
    dict(id="w_view", cat="gauge", name="조망", color=UB_RED, scope="마에스트로/H",
         desc="전투 시작 시 21 · 턴 시작 시 -2 · 아군이 수비 행동 외 행동 시 -1 (턴당 최대 -4) / "
              "0이 되면 스킬 3이 [폐장]으로 변경 (전투당 1회) / 조망 자체는 효과가 없다"),
    dict(id="w_material", cat="gauge", name="생체재료", color=MA_BONE, scope="마에스트로/H",
         desc="전투 시작 시 1 · 스킬 1/2/3 사용마다 +1/+2/+3 / 10에 도달하면 전부 소비하고 걸작 획득"),
    dict(id="w_wrap", cat="gauge", name="포장", color=BS_FIRE, scope="큰누님/N",
         desc="전투 시작 시 3 / 포장 1당 스킬 피해 5 감소 / 0이 되면 [레바테인] 개방 / "
              "{포장을 벗겨볼까}로도 소모된다"),
    dict(id="w_fun", cat="gauge", name="달아오르는 재미", color=SPC, scope="큰누님/N",
         desc="전투 시작 시 2 · 스킬 2/3 사용 시 -1 / 0이 되면 {포장을 벗겨볼까} 사용 가능 / "
              "{포장을 벗겨볼까} 사용 후 2 획득 · 레바테인 개방 시 제거"),
    dict(id="w_hermes", cat="gauge", name="헤르메스", color=OR_GOLD, scope="신탁 대행자/H · 모조된 삶",
         desc="안 쓴 무기로 스킬을 사용하면 +1 (턴당 3회) · 해금 IV 도달 시 7 이하면 +2 (전투당 1회) / "
              "9가 되면 전부 제거 · SP 6까지 회복 · 스킬 3이 [Furioso-Replica]로 변경"),
    dict(id="w_grace", cat="gauge", name="가호", color=OR_SKY, scope="신탁 대행자/H · 지령",
         desc="적 처치 / 한 턴에 40 이상 피해 / 공격 회피 시 +1 (턴당 1회) · 스킬 3 사용 시 +1 / "
              "2 이상이면 해금 단계 상승 후 초기화 (가호는 로그에만 표시)"),
    dict(id="w_terminal", cat="gauge", name="신탁 단말기", color=OR_SKY, scope="신탁 대행자/H",
         desc="스킬을 사용할 때마다 무기 9종 중 하나의 효과가 발동 / 손도끼·스틸레토·바스타드 소드: 없음 / "
              "레이피어·랜스: 속도 감소 1·2 / 망치·채찍: 격파피해 +5·+10 / 검: 피해 +5 / 낫: 피해 ×1.3 후 +10"),
]
THEMES["web"].update(effects=WEB_EFFECTS, cats=WEB_EFFECT_CATS)
THEMES["wal"].update(effects=[], cats=[])
MENU_PAGES = ["menu"] + ["menu_" + _k for _k in THEMES]    # 서재 페이지 순서 (← →)

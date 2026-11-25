# -*- coding: utf-8 -*-
"""형상해석(가챠) · 형상 장착 · 형상 툴팁"""
import math
import os
import random
import threading
import time
import tkinter as tk
import tkinter.font as tkfont

from nhc_data import *


class GachaMixin:
    """NHCBattle 에 섞여 들어가는 기능 묶음 (self 는 NHCBattle)."""

    # ================================================================
    # 형상해석(가챠) 창 — E 키로 열고 닫으며, 보유 형상을 클릭해 장착한다.
    # ================================================================
    def toggle_gacha(self):
        if self.gacha_open:
            self.close_gacha()
            return
        if self.admin or self.modal or self.codex_open or self.state == "augment_pick":
            return
        self.gacha_open = True
        self.render()

    def close_gacha(self):
        self.gacha_open = False
        self.pity_choice_open = False
        self.pity_choice_tier = 0
        if self.gacha_reveal:
            self.gacha_reveal = None
        self.render()

    def equip_aspect(self, aspect_id):
        aspect = next((item for item in ALL_ASPECTS if item["id"] == aspect_id), None)
        if not aspect or aspect_id not in self.owned_aspects:
            return
        unit = self.roster.get(aspect["char"])
        if not unit or unit.side != "ally":
            return
        if unit.aspect_id != aspect_id:
            unit.fate_hp_spent = 0
            unit.fate_ready = False
            unit.hero_buff = False
            unit.hero_revive_used = False
            unit.hero_passive_shield_gained = 0
            unit.hero_echo_used = False
            unit.hero_echo_channel = None
            unit.imperial_prayer = 0
            unit.imperial_princess = False
            unit.imperial_command_used = False
            unit.imperial_hope_cooldown = 0
            unit.imperial_guardian_round = None
            unit.imperial_guardian_empty_reward_round = None
            unit.imperial_safety_round = None
            unit.imperial_safety_used = False
            unit.imperial_guardian_target = None
            if self.is_bigsis(unit):
                self.bs_clear(unit)
        unit.aspect_id = aspect_id
        self.__dict__.setdefault("equipped", {})[aspect["char"]] = aspect_id
        unit.skills = aspect["skills"]
        unit.max_sp = 10 if aspect_id == "n_imperial" else MAX_SP
        unit.sp = min(unit.sp, unit.max_sp)
        if aspect_id == "c_underboss":
            self.ub_reset(unit)
        elif aspect_id == "h_maestro":
            self.ma_reset(unit)
        elif aspect_id == "n_bigsis":
            self.bs_reset(unit)
        elif aspect_id == "h_oracle":
            self.or_reset(unit)
        self.gacha_notice = "%s 장착 완료." % aspect["title"]
        self.log("%s에게 [%s] 형상을 장착했다." % (unit.name, aspect["title"]), STAR_COLOR[aspect["star"]])
        self.render()

    def gacha_draw(self, count, cost):
        if self.aspect_shards < cost:
            return
        self.aspect_shards -= cost
        pool = banner_pool(self.gacha_banner)
        total = sum(w for _, w in pool)
        results = []
        for _ in range(count):
            r = random.random() * total
            pick = pool[-1][0]
            for a, w in pool:
                if r < w:
                    pick = a
                    break
                r -= w
            results.append((pick, pick["id"] not in self.owned_aspects))
            self.owned_aspects.add(pick["id"])
        self.aspect_pity += count
        self.gacha_results = results
        self.gacha_notice = ""
        self.gacha_reveal = {"revealed": 0, "index": 0, "frame": 0}
        self.log("%s %d회 (조각 -%d) — ★★ %d개" %
                 (self.banner_info()["name"], count, cost, sum(1 for a, _ in results if a["star"] >= 2)), SPC)
        beep([(880, 50), (1046, 60), (1318, 90)], self.sound)
        self.render()
        self.schedule(28, self.gacha_reveal_step)

    def gacha_reveal_step(self):
        reveal = self.gacha_reveal
        if not self.gacha_open or not reveal:
            return
        pause_ms = 28
        reveal["frame"] += 1
        if reveal["frame"] >= 8:
            result_index = reveal["revealed"]
            pick = self.gacha_results[result_index][0]
            reveal["revealed"] += 1
            reveal["index"] += 1
            reveal["frame"] = 0
            if pick["star"] == 3:
                self.gacha_notice = "★★★ 형상 등장! %s" % pick["title"]
                self.log("★★★ 형상 등장! [%s]" % pick["title"], STAR_COLOR[3])
                self.fx_gacha_rare(result_index, pick)
                beep([(523, 80), (784, 90), (1046, 100), (1568, 240)], self.sound)
                pause_ms = 1250
            if reveal["revealed"] >= len(self.gacha_results):
                self.gacha_reveal = None
            elif pause_ms == 28:
                beep([(523, 25), (784, 40)], self.sound)
        self.render()
        if self.gacha_reveal:
            self.schedule(pause_ms, self.gacha_reveal_step)

    def skip_gacha_reveal(self):
        if not self.gacha_reveal:
            return
        self.gacha_reveal = None
        self.render()

    def gacha_pity_exchange(self, tier):
        if tier not in (2, 3):
            return
        threshold = GACHA_PITY_TIER2 if tier == 2 else GACHA_PITY_TIER3
        options = self.unowned_tier_aspects(tier)
        if tier == 2 and self.pity_tier2_claimed:
            self.gacha_notice = "★★ 천장은 이미 수령했다. 형상파편 스택은 유지 중이다."
        elif self.aspect_pity < threshold:
            self.gacha_notice = "형상파편 %d개가 필요하다." % threshold
        elif not options:
            self.gacha_notice = "보유하지 않은 %s 형상이 없어 선택할 수 없다." % ("★★" if tier == 2 else "★★★")
        else:
            self.pity_choice_open = True
            self.pity_choice_tier = tier
            self.gacha_notice = ""
        self.render()

    def unowned_tier_aspects(self, tier):
        return [aspect for aspect in banner_aspects(self.gacha_banner)
                if aspect["star"] == tier and aspect["id"] not in self.owned_aspects]

    def banner_info(self):
        return next(b for b in GACHA_BANNERS if b["id"] == self.gacha_banner)

    def set_gacha_banner(self, banner):
        if banner == self.gacha_banner or self.gacha_reveal or self.pity_choice_open:
            return
        self.gacha_banner = banner
        self.gacha_notice = ""
        self.gacha_results = []
        self.render()

    def draw_theme_arrows(self, x_left, x_right, y, h, can_left, can_right, color, cb_left, cb_right,
                          idx_left, idx_right):
        """패널 양옆의 ◀ ▶ 넘김 버튼."""
        for x, label, ok, cb, idx in ((x_left, "◀", can_left, cb_left, idx_left),
                                      (x_right, "▶", can_right, cb_right, idx_right)):
            hov = ok and self.hover == ("gch", idx)
            self.canvas.create_rectangle(x, y, x + 40, y + h, fill=PANEL2 if hov else PANEL,
                                         outline=color if ok else BRD, width=2 if hov else 1, tags="ui")
            self.txt(x + 20, y + h / 2, label, 20, color if ok else BRD, bold=True, anchor="center")
            self.buttons.append(dict(x=x, y=y, w=40, h=h, key=("gch", idx),
                                     cb=(cb if ok else (lambda: None))))

    def unowned_tier2_aspects(self):
        return self.unowned_tier_aspects(2)

    def gacha_claim_pity_aspect(self, aspect_id):
        tier = self.pity_choice_tier
        if tier not in (2, 3):
            return
        threshold = GACHA_PITY_TIER2 if tier == 2 else GACHA_PITY_TIER3
        aspect = next((item for item in self.unowned_tier_aspects(tier)
                       if item["id"] == aspect_id), None)
        if (not self.pity_choice_open or tier not in (2, 3)
                or (tier == 2 and self.pity_tier2_claimed)
                or self.aspect_pity < threshold or not aspect):
            return
        self.owned_aspects.add(aspect_id)
        if tier == 2:
            self.pity_tier2_claimed = True
            self.gacha_notice = "★★ 천장 수령 완료: %s · 형상파편 %d개 유지" % (
                aspect["title"], self.aspect_pity)
            self.log("★★ 천장으로 [%s] 형상을 선택했다. 형상파편 스택 %d 유지." %
                     (aspect["title"], self.aspect_pity), STAR_COLOR[2])
        else:
            self.aspect_pity = 0
            self.pity_tier2_claimed = False
            self.gacha_notice = "★★★ 천장 수령: %s · 형상파편 스택 초기화" % aspect["title"]
            self.log("★★★ 천장으로 [%s] 형상을 선택했다. 형상파편 스택 초기화." %
                     aspect["title"], STAR_COLOR[3])
        self.pity_choice_open = False
        self.pity_choice_tier = 0
        self.gacha_results = [(aspect, True)]
        beep([(784, 60), (1046, 70), (1318, 120)], self.sound)
        self.render()

    def close_pity_choice(self):
        self.pity_choice_open = False
        self.pity_choice_tier = 0
        self.render()

    def render_pity_choice(self):
        tier = self.pity_choice_tier
        options = self.unowned_tier_aspects(tier)
        star_text = "★★" if tier == 2 else "★★★"
        threshold = GACHA_PITY_TIER2 if tier == 2 else GACHA_PITY_TIER3
        star_color = STAR_COLOR[tier]
        self.buttons = []
        self.canvas.create_rectangle(0, 0, WIN_W, WIN_H, fill="#000000", outline="",
                                     stipple="gray50", tags="ui")
        bx, by, bw, bh = WIN_W / 2 - 390, 190, 780, 430
        self.canvas.create_rectangle(bx, by, bx + bw, by + bh, fill=PANEL,
                                     outline=star_color, width=2, tags="ui")
        self.txt(WIN_W / 2, by + 28, star_text + " 천장 형상 선택", 24, star_color,
                 bold=True, anchor="center")
        stack_note = "형상파편 %d개 유지" % self.aspect_pity if tier == 2 \
            else "선택하면 형상파편 스택이 0으로 초기화됩니다"
        self.txt(WIN_W / 2, by + 60, "미보유 형상 중 하나를 선택하세요 · " + stack_note,
                 12, MUT, mono=True, anchor="center")
        gap = 12
        option_w = (bw - 48 - gap * 2) / 3
        option_y = by + 95
        for index, aspect in enumerate(options):
            option_x = bx + 24 + (index % 3) * (option_w + gap)
            option_row_y = option_y + (index // 3) * 112
            self.gbtn(option_x, option_row_y, option_w, 100,
                      star_text + "  " + aspect["title"], "캐릭터 " + aspect["char"],
                      lambda aid=aspect["id"]: self.gacha_claim_pity_aspect(aid),
                      star_color, True, 10 + index)
        if not options:
            self.txt(WIN_W / 2, option_y + 52, "선택 가능한 " + star_text + " 형상이 없습니다.",
                     14, MUT, anchor="center")
        self.gbtn(WIN_W / 2 - 70, by + bh - 52, 140, 34,
                  "취소", None, self.close_pity_choice, MUT, True, 19)

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
        if a["id"] == "c_underboss":
            return self.underboss_tip_lines()
        if a["id"] == "h_maestro":
            return self.maestro_tip_lines()
        if a["id"] == "n_bigsis":
            return self.bigsis_tip_lines()
        if a["id"] == "h_oracle":
            return self.oracle_tip_lines()
        lines = []
        if a.get("desc"):
            lines.append(a["desc"])
        if a["id"] == "c_fate_lost":
            lines.append("패시브: 적 처치 시 체력 30 회복 · 체력 소비 100마다 필연 획득")
            lines.append("필연 보유 시 스킬 3이 [운명]으로 변경(전투당 1회):")
            lines.append("기본 공격·방어·회피·라운드 시작 SP 회복 불가")
            lines.append("스킬 3-2:[운명] 이 스킬은 사용시 스킬포인트를 소모하지 않음,모든 대상에게 80 피해, 운명 3 부여")
        elif a["id"] == "h_hero":
            lines.append("피해의 10%만큼 보호막 획득 (이 효과로 최대 체력의 50% 까지만 획득)")
            lines.append("사망 시 최대 체력으로 부활(전투 당 1회) · 영웅 버프 획득")
            lines.append("영웅: 보호막이 최대체력을 초과하여 부여될 수 있음 · 스킬 피해의 10% 보호막 획득")
            lines.append("영웅 버프 중 스킬 3이 [잔상보]로 변경(전투당 1회)")
            lines.append("잔상보: 한 턴 3회 공격 · 첫 타격은 지정 대상, 다음 2회는 무작위 적 · 총 최대 180 피해")
            lines.append("잔상보 시전 중 기절/격파/사망하면 중단")
        elif a["id"] == "n_imperial":
            lines.append("패시브: 기본 SP 10 · 외부 효과로 SP 증가 불가 (수호령 사용시 2 획득)")
            lines.append("수호령 사용 즉시 기도 +20 · 전이된 피해만큼 기도 추가 획득")
            lines.append("왕녀 상태가 아니면 일반 공격(수호령)·방어·회피 외 행동 불가")
            lines.append("기도 120 → 왕녀: SP 최대 · 매턴 체력 +10 · SP +4 · 해당 턴동안 사망하지 않음")
            lines.append("왕녀 상태에서 스킬 3이 [(관측불가) 섬멸 명령]으로 변경(전투당 1회)")
            lines.append("스킬 3-2 [(관측불가) 섬멸 명령]-모든 적에게 100 고정 피해(방어 행동을 무시함)")
        for i, sk in enumerate(a["skills"], 1):
            if sk.get("shield_cost"):
                cost = "보호막 %d + SP %d" % (sk["shield_cost"], sk["cost"])
            elif sk.get("hp_cost"):
                cost = "체력 %d 소비" % sk["hp_cost"]
            elif sk["kind"] == "fate_ultimate":
                cost = "필연 소비"
            elif sk["kind"] == "hero_echo":
                cost = "자원 없음"
            else:
                cost = "%d포인트 소비" % sk["cost"]
            lines.append("스킬 %d: %s [%s]" % (i, sk["name"], cost))
            for part in sk["desc"].split(" / "):
                lines.append("   " + part)
        return lines

    def draw_aspect_tip(self, a):
        c = STAR_COLOR.get(a["star"], TXT)
        title = "%s  %s" % ("★" * a["star"], a["title"])
        lines = self.aspect_tip_lines(a)
        tf, lf = self.font(15, bold=True), self.font(11, mono=True)
        lines = self.wrap_lines(lines, lf, 560)
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
        pw, ph = 900, 660
        px, py = (WIN_W - pw) / 2, 30
        self.canvas.create_rectangle(px + 5, py + 5, px + pw + 5, py + ph + 5,
                                     fill="#05070A", outline="", stipple="gray50", tags="ui")
        banner = self.banner_info()
        bcol = banner["color"]
        bi = BANNER_IDS.index(self.gacha_banner)
        is_web = self.gacha_banner == "web"
        theme = THEMES.get(self.gacha_banner)
        self.canvas.create_rectangle(px, py, px + pw, py + ph, fill=PANEL, outline=bcol,
                                     width=2, tags="ui")
        self.canvas.create_rectangle(px, py, px + pw, py + 5, fill=bcol, outline="", tags="ui")
        ix, iw = px + 24, pw - 48

        self.txt(ix, py + 14, "형상해석", 28, TXT, bold=True)
        self.txt(ix + 140, py + 16, banner["name"], 15, bcol, bold=True)
        self.txt(ix + 140, py + 40, banner["sub"], 11, MUT, mono=True)
        self.txt(px + pw - 24, py + 24, "[E] / [ESC] 닫기  ·  [← →] 테마", 11, MUT, mono=True, anchor="ne")
        self.draw_theme_arrows(px - 50, px + pw + 10, py + ph / 2 - 40, 80,
                               bi > 0, bi < len(BANNER_IDS) - 1,
                               bcol,
                               lambda: self.set_gacha_banner(BANNER_IDS[bi - 1]),
                               lambda: self.set_gacha_banner(BANNER_IDS[bi + 1]), 7, 8)

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
        rx = ix + 50
        for st, pct in banner_rates(self.gacha_banner).items():
            label = "%s  %s%%" % ("★" * st, ("%.1f" % pct).rstrip("0").rstrip("."))
            self.txt(rx, py + 127, label, 13, STAR_COLOR[st], bold=True)
            rx += 110 + 8 * st

        # 형상 도감으로 이동 (장착은 도감에서)
        self.gbtn(ix, py + 142, 230, 30, "형상 도감 열기 · 장착 ▶" if not theme else "%s 형상 도감 · 장착 ▶" % theme["label"],
                  None, self.open_aspect_codex, bcol, True, 6)
        if is_web:
            chip_w = (iw - 246 - 3 * 6) / 4.0
            for i, a in enumerate(SPIDER_ASPECTS):
                cx = ix + 246 + i * (chip_w + 6)
                owned = a["id"] in self.owned_aspects
                hov = self.hover == ("gsp", i)
                self.canvas.create_rectangle(cx, py + 142, cx + chip_w, py + 172,
                                             fill=PANEL2 if hov else PANEL,
                                             outline=bcol if owned else BRD, width=2 if hov else 1, tags="ui")
                self.txt(cx + chip_w / 2, py + 157, "★★★ " + a["title"], 11, TXT if owned else MUT,
                         bold=True, anchor="center")
                self.buttons.append(dict(x=cx, y=py + 142, w=chip_w, h=30, key=("gsp", i), cb=lambda: None))
        elif theme:
            self.txt(ix + 246, py + 150, "이 테마 전용 형상은 아직 없다 (임시)", 11, MUT, mono=True)
        else:
            self.txt(ix + 246, py + 150, "해석한 형상은 도감에서 장착한다", 11, MUT, mono=True)

        # 해석 버튼
        bw = (iw - 12) / 2
        can_draw = not self.gacha_reveal
        self.gbtn(ix, py + 180, bw, 66, "1회 해석", "조각 %d 소모" % GACHA_COST_SINGLE,
                  lambda: self.gacha_draw(1, GACHA_COST_SINGLE), SPC,
              self.aspect_shards >= GACHA_COST_SINGLE and can_draw, 0)
        self.gbtn(ix + bw + 12, py + 180, bw, 66, "10회 해석  (+1회 보너스)",
                  "조각 %d 소모 · 총 11회 해석" % GACHA_COST_TEN,
                  lambda: self.gacha_draw(11, GACHA_COST_TEN), SPC,
              self.aspect_shards >= GACHA_COST_TEN and can_draw, 1)

        # 형상파편 진행도
        y0 = py + 268
        self.txt(ix, y0, "형상파편  (해석 1회당 +1 · ★★ 수령 시 스택 유지)", 12, TXT, bold=True)
        by = y0 + 26
        self.canvas.create_rectangle(ix, by, ix + iw, by + 16, fill=PANEL2, outline=BRD, tags="ui")
        ratio = min(1.0, self.aspect_pity / float(GACHA_PITY_TIER3))
        if ratio > 0:
            self.canvas.create_rectangle(ix + 1, by + 1, ix + 1 + (iw - 2) * ratio, by + 15,
                                         fill=SHLD, outline="", tags="ui")
        x200 = ix + iw * GACHA_PITY_TIER2 / float(GACHA_PITY_TIER3)
        self.canvas.create_line(x200, by - 4, x200, by + 20, fill=STAR_COLOR[2], width=2, tags="ui")
        tier2_label = "%d  ★★ 수령 완료" % GACHA_PITY_TIER2 if self.pity_tier2_claimed \
            else "%d  ★★ 선택 가능" % GACHA_PITY_TIER2
        self.txt(x200, by + 22, tier2_label, 10, STAR_COLOR[2],
                 mono=True, anchor="n")
        self.txt(ix + iw, by + 22, "%d  ★★★ 선택" % GACHA_PITY_TIER3, 10, STAR_COLOR[3],
                 mono=True, anchor="ne")

        ey = y0 + 68
        tier2_options = self.unowned_tier2_aspects()
        if self.pity_tier2_claimed:
            tier2_button = "★★ 천장 수령 완료"
        elif not tier2_options:
            tier2_button = "★★ 형상 보유 완료"
        else:
            tier2_button = "★★ 원하는 형상 선택  (%d)" % GACHA_PITY_TIER2
        self.gbtn(ix, ey, bw, 42, tier2_button, None,
                  lambda: self.gacha_pity_exchange(2), STAR_COLOR[2],
                  self.aspect_pity >= GACHA_PITY_TIER2 and can_draw
                  and not self.pity_tier2_claimed and bool(tier2_options), 2)
        self.gbtn(ix + bw + 12, ey, bw, 42,
                  "★★★ 원하는 형상 선택  (%d)" % GACHA_PITY_TIER3, None,
                  lambda: self.gacha_pity_exchange(3), STAR_COLOR[3],
                  self.aspect_pity >= GACHA_PITY_TIER3 and can_draw
                  and bool(self.unowned_tier_aspects(3)), 3)
        if self.gacha_notice:
            self.txt(ix, ey + 50, self.gacha_notice, 11, SPC, mono=True)

        # 해석 결과 (카드에 마우스를 올리면 스킬 확인)
        y1 = py + 414
        self.txt(ix, y1, "해석 결과", 12, TXT, bold=True)
        if self.gacha_reveal:
            self.gbtn(ix + iw - 116, y1 - 6, 116, 26, "연출 스킵", None,
                      self.skip_gacha_reveal, SPC, True, 5)
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
                    unit = self.roster.get(pick["char"])
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
             "※ 해석 결과에서 보유 형상을 클릭하면 장착할 수 있다. (도감은 F 키 → 서재)",
             10, MUT, mono=True, anchor="center")

        h = self.hover
        if isinstance(h, tuple):
            if h[0] == "gdex" and h[1] < len(ASPECTS):
                self.draw_aspect_tip(ASPECTS[h[1]])
            elif h[0] == "gsp" and h[1] < len(SPIDER_ASPECTS):
                self.draw_aspect_tip(SPIDER_ASPECTS[h[1]])
            elif h[0] == "gcard" and h[1] < len(self.gacha_results):
                self.draw_aspect_tip(self.gacha_results[h[1]][0])
        if self.pity_choice_open:
            self.render_pity_choice()

    def fx_gacha_rare(self, index, aspect):
        accent = WEB_COLOR if aspect.get("theme") == "web" else STAR_COLOR[3]
        cx, cy = WIN_W / 2, 332
        veil = self.canvas.create_rectangle(112, 202, WIN_W - 112, 456,
                                            fill="#160E20", outline=accent, width=2,
                                            stipple="gray50", tags="fx")
        rings = [self.canvas.create_oval(cx, cy, cx, cy, outline=accent, width=4, tags="fx")
                 for _ in range(3)]
        title = self.canvas.create_text(cx, cy - 20, text="★★★ 형상 등장!",
                                        fill=accent, font=(self.ff, -38, "bold"), tags="fx")
        subtitle = self.canvas.create_text(cx, cy + 28, text=aspect["title"],
                                           fill=WHITE, font=(self.ff, -22, "bold"), tags="fx")
        particles, velocities = [], []
        for _ in range(36):
            angle = random.random() * math.tau
            speed = 80 + random.random() * 210
            size = 3 + random.random() * 5
            item = self.canvas.create_polygon(cx, cy, cx + size, cy - size,
                                              cx, cy - size * 2, cx - size, cy - size,
                                              fill=SPC if random.random() < 0.35 else accent,
                                              outline="", tags="fx")
            particles.append((item, size))
            velocities.append((math.cos(angle) * speed, math.sin(angle) * speed))

        items = [veil] + rings + [title, subtitle] + [item for item, _ in particles]

        def up(p, effect):
            for ring_index, ring in enumerate(rings):
                progress = min(1.0, max(0.0, p * 1.35 - ring_index * 0.18))
                radius = 20 + 220 * progress
                self.canvas.coords(ring, cx - radius, cy - radius * 0.55,
                                   cx + radius, cy + radius * 0.55)
                self.canvas.itemconfig(ring, outline=lerp_color(accent, BG, progress),
                                       width=max(1, 5 - 4 * progress))
            self.canvas.coords(title, cx, cy - 20 - 18 * p)
            self.canvas.coords(subtitle, cx, cy + 28 - 10 * p)
            for (item, size), (vx, vy) in zip(particles, velocities):
                px = cx + vx * p
                py = cy + vy * p + 24 * p * p
                scale = size * (1 - p * 0.65)
                self.canvas.coords(item, px, py - scale, px + scale, py,
                                   px, py + scale, px - scale, py)
                self.canvas.itemconfig(item, fill=lerp_color(accent, BG, p))
            if p > 0.55:
                self.canvas.itemconfig(veil, stipple="gray25")

        self.add_fx(items, 1.15, up)

    def open_aspect_codex(self):
        """형상해석 창에서 바로 형상 도감(장착 화면)으로 넘어간다."""
        self.close_gacha()
        self.codex_open = True
        self.codex_page = ("aspect_" + self.gacha_banner) if self.gacha_banner != "normal" else "aspect"
        self.codex_sel = None
        self.render()

    def theme_arrow_key(self, ev):
        """← → 로 형상해석 테마 / 서재 페이지를 넘긴다."""
        if ev.keysym not in ("Left", "Right"):
            return False
        right = ev.keysym == "Right"
        if self.pity_choice_open:
            return False
        if self.gacha_open:
            i = BANNER_IDS.index(self.gacha_banner) + (1 if right else -1)
            if 0 <= i < len(BANNER_IDS):
                self.set_gacha_banner(BANNER_IDS[i])
            return True
        if self.codex_open and self.codex_page in MENU_PAGES:
            i = MENU_PAGES.index(self.codex_page) + (1 if right else -1)
            if 0 <= i < len(MENU_PAGES):
                self.codex_flip(MENU_PAGES[i])
            return True
        return False

    def lobby_aspect(self):
        self.gacha_open = True
        self.render()

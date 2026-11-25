# -*- coding: utf-8 -*-
"""★★★ 거미집 형상 — 언더보스/C · 마에스트로/H · 큰누님/N · 신탁 대행자/H"""
import math
import os
import random
import threading
import time
import tkinter as tk
import tkinter.font as tkfont

from nhc_data import *


class AdminAspectsMixin:
    """NHCBattle 에 섞여 들어가는 기능 묶음 (self 는 NHCBattle)."""

    # ================================================================
    # ★★★ 언더보스/C (거미집 형상 — 언더보스 패치)
    # ================================================================
    def is_underboss(self, unit):
        return unit.side == "ally" and unit.aspect_id == "c_underboss"

    def ub_reset(self, unit):
        unit.ub_foresight = 30
        unit.ub_overheat = -1
        unit.ub_ammo = UB_AMMO_MAX
        unit.ub_counter_round = None
        unit.ub_disposal_used = False
        unit.ub_refill_next = False
        unit.ub_refill_used = False

    def ub_range(self, unit):
        """예지 수치에 따른 회피 주사위 범위 (최소, 최대)."""
        f = unit.ub_foresight
        if unit.ub_overheat < 0 and f >= 25:
            return 5, 6
        if unit.ub_overheat < 0 and f >= 19:
            return 4, 5
        if unit.ub_overheat < 0 and f >= 13:
            return 3, 4
        return 1, 3

    def ub_shift(self, unit, delta):
        """예지 수치를 바꾼다. 0 이 되면 예지안 과열이 시작된다."""
        if unit.ub_overheat >= 0 or not unit.alive:
            return
        unit.ub_foresight = max(0, min(30, unit.ub_foresight + delta))
        self.fx_number(unit.id, "예지 %d" % unit.ub_foresight, UB_RED, 15, dy=-30)
        if unit.ub_foresight == 0:
            unit.ub_overheat = 0
            unit.ub_disposal_used = False
            self.log("%s의 예지가 바닥났다 — 예지안 과열 0. 스킬 3이 [처분]으로 변경." % unit.name, UB_RED)
            self.log("%s: '칫.. 얼마나 썻다고 벌써'" % unit.name, UB_RED)

    def ub_round_start(self, unit):
        if unit.ub_refill_next:
            unit.ub_refill_next = False
            unit.ub_disposal_used = False
            self.log("%s의 [처분]이 리필됐다." % unit.name, UB_RED)
            self.log("%s: '다음사람 나와, 뭐. 결과는 불보듯 뻔하겠지만'" % unit.name, UB_RED)
        if unit.ub_overheat >= 0:
            unit.ub_overheat += 10
            self.log("%s의 예지안 과열 +10 (%d/30)." % (unit.name, unit.ub_overheat), UB_RED)
            if unit.ub_overheat >= 30:
                unit.ub_overheat = -1
                unit.ub_foresight = 30
                unit.ub_disposal_used = False
                self.log("%s의 예지안 과열이 가라앉았다 — 예지 30 복귀. 스킬 3 복귀." % unit.name, UB_RED)

    def ub_passive_evade(self, attacker, target, raw, fx, cb, no_break, hp_floor):
        """불완전한 예지안 — 공격당할 때 예지에 따른 주사위로 자동 회피한다."""
        lo, hi = self.ub_range(target)
        a, b = random.randint(lo, hi), d6()
        target.status = None

        def after():
            dodged = a >= b                      # 동점이어도 회피 성공 (6 은 어떤 값과 겨뤄도 성공)
            self.log("%s의 불완전한 예지안 — 회피 판정 %d(%d~%d) vs %d → %s" %
                     (target.name, a, lo, hi, b, "완전 회피!" if dodged else "회피 실패"), UB_RED)
            if dodged:
                self.log("%s: '%s'" % (target.name, random.choice(UB_DODGE_LINES)), UB_RED)
                self.ub_shift(target, -3)             # 회피 성공시 예지 -3
                self.finalize(attacker, target, 0, "dodge",
                              lambda d: self.ub_counter(target, attacker, cb, d),
                              no_break=no_break, hp_floor=hp_floor)
            else:
                self.finalize(attacker, target, raw, fx, cb, no_break=no_break, hp_floor=hp_floor)

        self.dice_judge_overlay([("회피측", a), ("공격측", b)], after)

    def ub_counter(self, unit, attacker, cb, d=0):
        """회피 성공 — 1-2스킬 세치오나투라 디 코닐리오 (턴당 1회, 공격한 적에게 10 피해)."""
        if (attacker is None or attacker.side != "enemy" or not attacker.alive or not unit.alive
                or unit.ub_counter_round == self.round):
            cb(d)
            return
        unit.ub_counter_round = self.round
        self.log("%s: '하, 내 차례네?'" % unit.name, UB_RED)
        self.log("%s의 [세치오나투라 디 코닐리오]! %s에게 반격한다." % (unit.name, attacker.name), UB_RED)
        self.fx_ub_lance(unit.id, attacker.id, ext=260)
        self.schedule(230, lambda: self.apply_damage(
            unit, attacker, 10, "hit",
            lambda dd: (self.log("   └ %s에게 %d 피해." % (attacker.name, dd), DMG), cb(d))))

    def ub_break_fixed(self, t, amount, name):
        """추가 격파 고정피해 — 격파체력을 직접 깎는다."""
        if amount <= 0 or not t.alive or t.broken:
            return
        t.brk = max(0, t.brk - amount)
        self.fx_number(t.id, "격파 -%d" % amount, BRKC, 16, dy=-30)
        self.log("[%s] 추가 격파 고정피해 %d." % (name, amount), BRKC)
        if t.brk == 0:
            t.broken = True
            t.broken_skips = 1
            self.log("💥 %s의 격파체력이 소진됐다 — 격파!" % t.name, BRKC)
            self.fx_break(t.id)

    def fx_ub_spin(self, uid, turns=2, gap=110, scale=1.0):
        """회전 베기 — 황금/진홍 곡선이 번갈아 대상 주위를 휘감는다. 끝나는 시각(ms)을 돌려준다."""
        cx, cy = self.center_of(uid)
        for i in range(turns):
            def one(i=i):
                base = random.uniform(0, math.tau)
                tilt = random.uniform(-0.45, 0.45)
                gold = (i % 2 == 0)
                main, glow = (UB_GOLD_L, UB_GOLD) if gold else (UB_CRIM, UB_CRIM_D)
                r = random.uniform(95, 125) * scale
                self._ub_crescent(cx, cy, r, r * 0.55, base, math.radians(300), tilt,
                                  main, glow, dur=0.3)
                self._ub_crescent(cx, cy, r * 0.7, r * 0.4, base + math.pi, math.radians(260),
                                  tilt + 0.2,
                                  UB_CRIM if gold else UB_GOLD_L, UB_CRIM_D if gold else UB_GOLD,
                                  dur=0.26)
                self.fx_flash(uid, UB_GOLD if gold else UB_CRIM, "gray25")
                self.fx_particles(uid, main, n=6, spread=90 * scale, dur=0.35, size=3)
                self.shakes[uid] = 0.18
                beep([(random.randint(220, 340), 18)], self.sound)

            self.root.after(int(i * gap), one)
        return int((turns - 1) * gap + 220)

    def fx_ub_lance(self, src_uid, tgt_uid, ext=320, jitter=0.0, thick=1.0, dur=0.32):
        """찌르기 — 창끝이 대상을 꿰뚫고 그 너머까지 지나간다."""
        cv = self.canvas
        sx, sy = self.center_of(src_uid)
        tx, ty = self.center_of(tgt_uid)
        tx += random.uniform(-1, 1) * 30 * jitter
        ty += random.uniform(-1, 1) * 22 * jitter
        dx, dy = tx - sx, ty - sy
        ln = max(1.0, math.hypot(dx, dy))
        ux, uy = dx / ln, dy / ln
        px_, py_ = -uy, ux
        total = ln + ext

        def mk(col, w):
            return cv.create_line(sx, sy, sx, sy, fill=col, width=w * thick, capstyle="round",
                                  tags="fx")

        glow, mid, core = mk(UB_GOLD, 18), mk(UB_CRIM, 8), mk(WHITE, 3)
        side1, side2 = mk(UB_CRIM_D, 2), mk(UB_GOLD, 2)
        tip = cv.create_polygon(sx, sy, sx, sy, sx, sy, fill=UB_GOLD_L, outline=UB_GOLD,
                                width=1, tags="fx")

        def pos(d):
            return sx + ux * d, sy + uy * d

        def up(p, e):
            head = total * min(1.0, p * 2.2)
            fade = max(0.0, (p - 0.5) / 0.5)
            tail = max(0.0, head - 250) if p < 0.5 else max(0.0, total - 250) + 250 * fade
            tail = min(tail, head)
            (hx, hy), (qx, qy) = pos(head), pos(tail)
            for it in (glow, mid, core):
                cv.coords(it, qx, qy, hx, hy)
            cv.coords(side1, qx + px_ * 9, qy + py_ * 9, hx + px_ * 9, hy + py_ * 9)
            cv.coords(side2, qx - px_ * 9, qy - py_ * 9, hx - px_ * 9, hy - py_ * 9)
            cv.coords(tip, hx + ux * 22, hy + uy * 22, hx - ux * 8 + px_ * 8, hy - uy * 8 + py_ * 8,
                      hx - ux * 8 - px_ * 8, hy - uy * 8 - py_ * 8)
            for it, col in ((glow, UB_GOLD), (mid, UB_CRIM), (core, WHITE),
                            (side1, UB_CRIM_D), (side2, UB_GOLD)):
                cv.itemconfig(it, fill=lerp_color(col, BG, fade))
            cv.itemconfig(tip, state="hidden" if fade > 0.3 else "normal")

        self.add_fx([glow, mid, core, side1, side2, tip], dur, up)

        def hit():
            self.fx_flash(tgt_uid, UB_GOLD, "gray50")
            self.fx_particles(tgt_uid, UB_CRIM, n=12, spread=110, dur=0.45, size=3)
            self._ub_sparkle(tx, ty, n=4, spread=60, size=(6, 11), dur=0.45)
            self.shakes[tgt_uid] = 0.22
            beep([(random.randint(160, 240), 24)], self.sound)

        self.root.after(int(max(0.0, ln / total / 2.2) * dur * 1000), hit)

    def fx_ub_downslash(self, uid):
        """위에서 아래로 베며 지나간다."""
        cx, cy = self.center_of(uid)
        p0, p1, p2 = (cx - 90, cy - 185), (cx + 55, cy - 20), (cx + 75, cy + 205)
        path = []
        for i in range(21):
            q = i / 20.0
            path.append(((1 - q) ** 2 * p0[0] + 2 * (1 - q) * q * p1[0] + q * q * p2[0],
                         (1 - q) ** 2 * p0[1] + 2 * (1 - q) * q * p1[1] + q * q * p2[1]))
        self._ub_stroke(path, UB_GOLD_L, UB_CRIM, dur=0.36, width=1.3)
        side = [(x + 26, y - 10) for x, y in path]
        self._ub_stroke(side, UB_CRIM, UB_CRIM_D, dur=0.32, width=0.8)

        def impact():
            self.fx_flash(uid, UB_CRIM, "gray50")
            self.fx_particles(uid, UB_GOLD, n=16, spread=130, dur=0.5, size=4)
            self._ub_sparkle(cx, cy, n=6, spread=90, dur=0.55)
            self.shakes[uid] = 0.35
            beep([(180, 40), (110, 70)], self.sound)

        self.root.after(130, impact)

    def fx_ub_bigsweep(self, uid):
        """진홍색 대형 회전 베기 (영상 도입부)."""
        cx, cy = self.center_of(uid)
        self._ub_crescent(cx, cy, 190, 118, math.radians(200), math.radians(250), -0.35,
                          UB_CRIM, UB_CRIM_D, dur=0.5, width=1.7)
        self._ub_crescent(cx, cy, 150, 90, math.radians(30), math.radians(220), 0.3,
                          UB_GOLD_L, UB_GOLD, dur=0.42, width=1.2)
        self.fx_particles(uid, UB_CRIM, n=22, spread=170, dur=0.7, size=4)
        self.fx_flash(uid, UB_CRIM, "gray50")
        self.shakes[uid] = 0.3
        beep([(150, 50), (100, 90)], self.sound)

    def fx_ub_goldveil(self, uid, dur=0.9):
        """황금 빛무리 — 대상 주위가 주황빛으로 물든다."""
        cv = self.canvas
        cx, cy = self.center_of(uid)
        veil = cv.create_oval(cx, cy, cx, cy, fill=lerp_color(BG, UB_GOLD, 0.45), outline="",
                              stipple="gray25", tags="fx")
        ring = cv.create_oval(cx, cy, cx, cy, outline=UB_GOLD, width=4, tags="fx")
        ring2 = cv.create_oval(cx, cy, cx, cy, outline=UB_GOLD_L, width=2, tags="fx")

        def up(p, e):
            grow = min(1.0, p * 3.0)
            r = 40 + 150 * grow + 6 * math.sin(p * 18)
            fade = max(0.0, (p - 0.6) / 0.4)
            cv.coords(veil, cx - r * 1.25, cy - r * 0.8, cx + r * 1.25, cy + r * 0.8)
            cv.itemconfig(veil, fill=lerp_color(BG, UB_GOLD, 0.45 * (1 - fade)))
            cv.coords(ring, cx - r, cy - r * 0.62, cx + r, cy + r * 0.62)
            cv.coords(ring2, cx - r * 0.72, cy - r * 0.45, cx + r * 0.72, cy + r * 0.45)
            cv.itemconfig(ring, outline=lerp_color(UB_GOLD, BG, fade))
            cv.itemconfig(ring2, outline=lerp_color(UB_GOLD_L, BG, fade))

        self.add_fx([veil, ring, ring2], dur, up)

    def fx_ub_beam(self, uid):
        """화면을 가로지르는 붉은 관통선 + X자 참격 (영상 마지막 장면)."""
        cv = self.canvas
        tx, ty = self.center_of(uid)
        dur = 1.0

        def ln(col, w, y=ty):
            return cv.create_line(0, y, 0, y, fill=col, width=w, capstyle="round", tags="fx")

        glow, mid = ln(UB_CRIM_D, 34), ln(UB_CRIM, 16)
        core, white = ln(UB_GOLD_L, 6), ln(WHITE, 2)
        offs = [(ln(col, w, ty + dy), dy, col, w)
                for dy, col, w in ((-17, UB_CRIM, 3), (14, UB_GOLD, 3),
                                   (-31, UB_CRIM_D, 2), (28, UB_CRIM, 2))]
        xs = []
        for sgn in (1, -1):
            a = cv.create_line(tx, ty, tx, ty, fill=UB_CRIM, width=7, capstyle="round",
                               state="hidden", tags="fx")
            b = cv.create_line(tx, ty, tx, ty, fill=WHITE, width=2, capstyle="round",
                               state="hidden", tags="fx")
            xs.append((a, b, sgn))
        items = [glow, mid, core, white] + [o[0] for o in offs] + [i for x in xs for i in x[:2]]

        def up(p, e):
            head = WIN_W * min(1.0, p * 3.5)
            fade = max(0.0, (p - 0.55) / 0.45)
            for it in (glow, mid, core, white):
                cv.coords(it, 0, ty, head, ty)
            for it, dy, col, w in offs:
                cv.coords(it, head * 0.12, ty + dy, head, ty + dy)
                cv.itemconfig(it, fill=lerp_color(col, BG, fade))
            for it, col, w in ((glow, UB_CRIM_D, 34), (mid, UB_CRIM, 16),
                               (core, UB_GOLD_L, 6), (white, WHITE, 2)):
                cv.itemconfig(it, fill=lerp_color(col, BG, fade), width=max(1, w * (1 - 0.85 * fade)))
            q = max(0.0, min(1.0, (p - 0.12) / 0.2))
            for a, b, sgn in xs:
                if q <= 0:
                    continue
                for it in (a, b):
                    cv.coords(it, tx - sgn * 90 * q, ty - 170 * q, tx + sgn * 90 * q, ty + 170 * q)
                    cv.itemconfig(it, state="normal")
                cv.itemconfig(a, fill=lerp_color(UB_CRIM, BG, fade))
                cv.itemconfig(b, fill=lerp_color(WHITE, BG, fade))

        self.add_fx(items, dur, up)

        def impact():
            self.fx_flash(uid, WHITE, "gray50")
            self.fx_particles(uid, UB_CRIM, n=26, spread=190, dur=0.7, size=4)
            self.fx_particles(uid, UB_GOLD, n=12, spread=120, dur=0.6, size=3)
            self._ub_sparkle(tx, ty, n=9, spread=150, dur=0.8)
            self.shakes[uid] = 0.5
            beep([(200, 60), (120, 120)], self.sound)

        self.root.after(int(tx / float(WIN_W) / 3.5 * dur * 1000), impact)
        self.root.after(520, lambda: self._ub_sparkle(tx, ty, n=7, spread=200, dur=0.8))

    def fx_ub_skill(self, kind, src, tgt):
        """스킬별 이펙트를 시작하고, 피해가 들어갈 시점(ms)을 돌려준다."""
        if kind == "ub_colpi":                                   # 스킬 1 — 회전 베기 2연속
            return self.fx_ub_spin(tgt, 2, 110)
        if kind == "ub_pierce":                                  # 스킬 2 — 5연속 찌르기 → 내려베기
            for i in range(5):
                self.root.after(i * 85, lambda: self.fx_ub_lance(
                    src, tgt, ext=240, jitter=1.0, thick=0.8, dur=0.26))
            self.root.after(5 * 85 + 40, lambda: self.fx_ub_downslash(tgt))
            return 5 * 85 + 40 + 150
        if kind == "ub_cervo":                                   # 스킬 2-2 — 더 길게 회전 베기
            return self.fx_ub_spin(tgt, 6, 90, 1.1)
        if kind == "ub_elephant":                                # 스킬 3 — 관통 → 8연속 회전 베기
            self.fx_ub_lance(src, tgt, ext=340, thick=1.4, dur=0.34)
            self.root.after(380, lambda: self.fx_ub_spin(tgt, 8, 75, 1.1))
            return 380 + 7 * 75 + 220
        if kind == "ub_disposal":                                # 스킬 3-2 — 영상 재현
            self.fx_ub_bigsweep(tgt)
            self.root.after(300, lambda: (self.fx_ub_goldveil(tgt), self.fx_ub_spin(tgt, 3, 150, 1.5),
                                          self._ub_sparkle(*self.center_of(tgt), n=8, spread=170)))
            self.root.after(900, lambda: self.fx_ub_spin(tgt, 4, 85, 1.25))
            self.root.after(1350, lambda: self.fx_ub_beam(tgt))
            return 1500
        self.fx_ub_lance(src, tgt)
        return 300

    def execute_underboss(self, u, sk, plan, done):
        t = self.valid_target(u, plan, "enemy")
        if not t or t.side != "enemy":
            self.schedule(300, done)
            return
        kind = sk["kind"]
        if kind == "ub_disposal":                        # 사용시 가속탄 10 획득
            before = u.ub_ammo
            u.ub_ammo = min(UB_AMMO_MAX, u.ub_ammo + 10)
            u.ub_disposal_used = True
            self.log("[처분] 가속탄 재장전 (%d → %d)." % (before, u.ub_ammo), SPC)
        ammo_ok = False
        need = sk.get("ammo", 0)
        if need:
            if u.ub_ammo >= need:
                u.ub_ammo -= need
                ammo_ok = True
                self.fx_number(u.id, "가속탄 %d" % u.ub_ammo, SPC, 14, dy=-26)
            else:
                self.log("가속탄이 부족하다 — 추가효과가 발동하지 않는다.", MUT)
        dmg = sk["dmg"]
        doubled = False
        if kind == "ub_elephant":                        # ub_foresight_cost: 스킬 3 — 예지 -5, 소비한 가속탄만큼 추가 감소 (최대 10)
            _spent = need if ammo_ok else 0
            _drop = min(10, 5 + _spent)
            self.log("[%s] 예지 -%d (기본 5 + 가속탄 소비 %d)." % (sk["name"], _drop, _spent), UB_RED)
            self.ub_shift(u, -_drop)
        if kind == "ub_disposal" and t.hp <= t.max_hp * 0.5:
            dmg *= 2
            doubled = True
        if sk.get("line"):
            self.log("%s: %s" % (u.name, sk["line"]), UB_RED)

        def after(dealt):
            self.log("%s의 [%s]! %s에게 %d 피해%s." %
                     (u.name, sk["name"], t.name, dealt, " (체력 50% 이하 — 피해 2배)" if doubled else ""),
                     UB_RED)

            def tail():
                if kind == "ub_disposal" and not t.alive and not u.ub_refill_used:
                    u.ub_refill_used = True
                    u.ub_refill_next = True
                    self.log("[처분]으로 적을 처치했다 — 다음 턴 [처분]이 리필된다.", UB_RED)
                done()

            if ammo_ok and sk.get("extra_brk"):
                self.ub_break_fixed(t, sk["extra_brk"], sk["name"])
            if sk.get("fixed_dmg") and t.alive:
                self.apply_damage(u, t, sk["fixed_dmg"], "fixed",
                                  lambda fd: (self.log("[%s] 고정피해 %d." % (sk["name"], fd), UB_RED),
                                              tail()), fixed=True)
            else:
                tail()

        fx = sk.get("fx", "bullet")
        heavy = fx in ("snipe", "frenzy") or kind in ("ub_pierce", "ub_elephant")

        def hit():
            self.apply_damage(u, t, dmg, "heavy" if heavy else "hit", after)

        self.schedule(self.fx_ub_skill(kind, u.id, t.id), hit)

    def admin_equip_underboss(self):
        unit = self.units.get("C")
        if not unit or unit.side != "ally":
            return
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
        unit.imperial_guardian_round = None
        unit.imperial_safety_round = None
        unit.aspect_id = UNDERBOSS_ASPECT["id"]
        unit.skills = UNDERBOSS_ASPECT["skills"]
        unit.max_sp = MAX_SP
        unit.sp = min(unit.sp, unit.max_sp)
        self.ub_reset(unit)
        self.log("[ADMIN] C에게 [언더보스/C] 형상을 장착했다. (이번 전투 한정)", UB_RED)
        self.fx_flash(unit.id, UB_RED, "gray50")
        beep([(220, 60), (330, 70), (440, 120)], self.sound)
        self.render()

    def admin_unequip_underboss(self):
        unit = self.units.get("C")
        if not unit or not self.is_underboss(unit):
            return
        aid = self.__dict__.get("equipped", {}).get("C", "c_base")
        self.equip_aspect(aid)
        self.log("[ADMIN] 언더보스/C 장착을 해제했다.", UB_RED)
        self.render()

    def underboss_tip_lines(self):
        return [
            "★★★ 특별해석 {거미집} 전용 형상 — 형상해석 [▶] 거미집 테마에서 얻는다",
            "패시브: 불완전한 예지안",
            "   전투 시작시 예지 30 · 가속탄 10 획득",
            "   공격당할 때 자동으로 회피 행동 (예지가 높을수록 주사위 최소값 증가)",
            "   예지안 과열 중에는 자동 회피 X · 방어/회피 행동을 취했다면 그 행동이 우선 발동",
            "   예지 30~25: 5~6 · 24~19: 4~5 · 18~13: 3~4 · 12 이하: 1~3",
            "   회피 성공시 1-2스킬 [세치오나투라 디 코닐리오] — 공격한 적에게 10 피해 (턴당 1회)",
            "   회피 성공시 예지 -3 · 턴 종료시마다 예지 -2",
            "   예지 0 → 예지안 과열 0 획득 · 스킬 3이 3-2 [처분]으로 변경",
            "   [처분]을 한 번 쓰면 다시 스킬 3으로 돌아온다",
            "   예지안 과열: 매턴 +10 · 30이 되면 예지(30)로 복귀",
            "가속탄: 스킬 1/2/3 사용시 1/2/3 소비 · 부족하면 추가효과 발동 안 함",
            "   가속탄 부족시 스킬 2가 2-2 [세치오나투라 디 체르보]로 변경 · 재장전되면 복귀",
            "스킬 1: 콜피 탈리오 [2포인트 소비]",
            "   지정한 적에게 25 피해 · 가속탄 소비시 10 추가 격파 고정피해",
            "스킬 2: 기꺼이 이 탄환으로 꿰뚫어주지 [4포인트 소비]",
            "   50 피해 · 가속탄 소비시 20 추가 격파 고정피해",
            "스킬 2-2: 세치오나투라 디 체르보 [4포인트 소비]",
            "   35 피해 이후 5 고정피해",
            "스킬 3: 세치오나투라 디 엘리판테 [6포인트 소비]",
            "   65 피해 · 가속탄 소비시 30 추가 격파 고정피해",
            "   사용 시 예지 -5 · 소비한 가속탄 수만큼 예지 추가 감소 (총 최대 -10)",
            "스킬 3-2: 처분 [포인트 소비/회복 없음]",
            "   가속탄 10 획득 · 70 피해 (대상 체력 50% 이하면 2배) · 가속탄 소비시 35 추가 격파 고정피해",
            "   [처분]으로 적을 처치하면 다음 턴 [처분]이 다시 3-2로 리필 (전투당 1회)",
        ]

    # ================================================================
    # ★★★ 마에스트로/H (거미집 형상 — 마에스트로 패치)
    # ================================================================
    def is_maestro(self, unit):
        return unit.side == "ally" and unit.aspect_id == "h_maestro"

    def ma_reset(self, unit):
        unit.ma_view = MA_VIEW_START
        unit.ma_view_dec = 0
        unit.ma_closing_used = False
        unit.ma_material = 1
        unit.ma_masterpiece = False

    def ma_view_drop(self, unit, n):
        """조망 감소 — 턴당 최대 MA_VIEW_DROP_CAP 까지."""
        if not unit.alive or unit.ma_view <= 0:
            return
        n = min(n, MA_VIEW_DROP_CAP - unit.ma_view_dec, unit.ma_view)
        if n <= 0:
            return
        unit.ma_view -= n
        unit.ma_view_dec += n
        self.fx_number(unit.id, "조망 %d" % unit.ma_view, MA_BONE, 15, dy=-30)
        if unit.ma_view == 0 and not unit.ma_closing_used:
            self.log("%s의 조망이 모두 사라졌다 — 스킬 3이 [폐장]으로 변경." % unit.name, UB_RED)

    def ma_round_start(self, unit):
        unit.ma_view_dec = 0
        self.ma_view_drop(unit, 2)

    def ma_gain_material(self, unit, n):
        """일생의 작품 — 생체재료가 10 이 되면 전부 소비하고 걸작을 얻는다."""
        if unit.ma_masterpiece or n <= 0:
            return
        unit.ma_material += n
        self.fx_number(unit.id, "생체재료 %d/10" % min(10, unit.ma_material), MA_BONE, 14, dy=-12)
        if unit.ma_material >= 10:
            unit.ma_material = 0
            unit.ma_masterpiece = True
            self.log("%s의 생체재료가 가득 찼다 — 일생의 작품 완성! 걸작 획득 (공격력 +5)." %
                     unit.name, SPC)
            self.fx_flash(unit.id, SPC, "gray50")
            self.fx_number(unit.id, "걸작", SPC, 22, dy=-34)

    def ma_rib(self, u, t, then):
        """2-2 설치 미술 제 3호 '간이늑골' — 5 피해, 간이늑골 2 부여 (SP 소모/획득 없음)."""
        self.log("%s: '거기서 지켜보시죠!'" % u.name, MA_BONE)
        self.fx_ma_bind(t.id)

        def after(d):
            if t.alive:
                t.rib_turns = max(t.rib_turns, 2)
                self.fx_number(t.id, "간이늑골 %d" % t.rib_turns, MA_BONE, 15, dy=-30)
            self.log("[간이늑골] %s에게 %d 피해 · 간이늑골 %d 부여." % (t.name, d, t.rib_turns), MA_BONE)
            then()

        self.schedule(760, lambda: self.apply_damage(u, t, 5, "hit", after))

    def execute_maestro(self, u, sk, plan, done):
        kind = sk["kind"]
        if kind == "ma_closing":
            self.ma_closing(u, sk, done)
            return
        t = self.valid_target(u, plan, "enemy")
        if not t or t.side != "enemy":
            self.schedule(300, done)
            return
        if sk.get("gain"):
            self.ma_gain_material(u, sk["gain"])
        if sk.get("line"):
            self.log("%s: %s" % (u.name, sk["line"]), MA_BONE)

        if kind == "ma_dismantle":
            def after_d(dealt):
                self.log("%s의 [%s]! %s에게 %d 피해." % (u.name, sk["name"], t.name, dealt), UB_RED)
                done()

            self.schedule(self.fx_ma_skill1(t.id),
                          lambda: self.apply_damage(u, t, sk["dmg"], "heavy", after_d))
            return

        if kind == "ma_material":
            def after_m(dealt):
                self.log("%s의 [%s]! %s에게 %d 피해." % (u.name, sk["name"], t.name, dealt), UB_RED)
                if t.alive and random.random() < 0.5:
                    self.log("50% — 설치 미술 제 3호 '간이늑골' 발동!", MA_BONE)
                    self.ma_rib(u, t, done)
                else:
                    done()

            self.schedule(self.fx_ma_skill2(t.id),
                          lambda: self.apply_damage(u, t, sk["dmg"], "heavy", after_m))
            return

        # ma_melody — 티비아의 멜로디
        hits = [(t, sk["dmg"])]
        if u.ma_masterpiece:                              # 걸작 보유 — 양 옆 대상에게도
            enemies = self.enemies()
            if t in enemies:
                index = enemies.index(t)
                for ni in (index - 1, index + 1):
                    if 0 <= ni < len(enemies) and enemies[ni].alive:
                        hits.append((enemies[ni], sk["splash"]))

        def step(i):
            if i >= len(hits):
                done()
                return
            target, amount = hits[i]
            if not target.alive:
                step(i + 1)
                return
            self.apply_damage(u, target, amount, "heavy",
                              lambda dealt, target=target, i=i:
                              (self.log("[%s] %s에게 %d 피해." % (sk["name"], target.name, dealt), UB_RED),
                               step(i + 1)))

        self.schedule(self.fx_ma_melody([tg.id for tg, _ in hits]), lambda: step(0))

    def ma_closing(self, u, sk, done):
        """3-2 폐장 — 모든 적에게 120 고정피해(수비 무시) → 간이늑골 3 / 아군에게 선율."""
        targets = [e for e in self.enemies() if e.alive]
        u.ma_closing_used = True
        if not targets:
            done()
            return
        self.log("%s: %s" % (u.name, sk["line"]), MA_BONE)
        hp0 = dict((e.id, e.hp) for e in targets)
        total_ms = self.fx_ma_closing([e.id for e in targets])

        def finish():
            _per = [(e.id, max(0, hp0[e.id] - e.hp)) for e in targets]
            self.fx_ma_total(_per, sum(n for _, n in _per))
            for e in self.enemies():
                if e.alive:
                    e.rib_turns = max(e.rib_turns, 3)
                    self.fx_number(e.id, "간이늑골 %d" % e.rib_turns, MA_BONE, 15, dy=-30)
            for a in self.allies():
                if a.alive:
                    a.ma_melody = True
                    self.fx_number(a.id, "선율", MA_BONE, 16, dy=-30)
            self.log("모든 적에게 간이늑골 3 · 아군에게 선율 (속도 +1 · 공격력 +5).", MA_BONE)
            self.render()
            self.schedule(400, done)

        def step(i):
            if i >= len(targets):
                finish()
                return
            e = targets[i]
            self.apply_damage(u, e, sk["dmg"], "heavy",
                              lambda dealt, e=e:
                              (self.log("[폐장] %s에게 고정피해 %d." % (e.name, dealt), UB_RED),
                               step(i + 1)), fixed=True)

        self.schedule(total_ms, lambda: step(0))

    def fx_ribcage(self, uid):
        """간이늑골 — 척추에서 늑골이 뻗어나와 대상을 가둔다."""
        cv = self.canvas
        x, y, w, h = self.rect_of(uid)
        cx = x + w / 2
        R = min(w / 2 - 14, 120)
        n = 6
        ys = [y + 22 + i * (h - 44) / float(n - 1) for i in range(n)]
        spine = cv.create_line(cx, ys[0], cx, ys[0], fill=MA_BONE, width=5, capstyle="round", tags="fx")
        ribs = []
        for i, yi in enumerate(ys):
            for s in (-1, 1):
                pts = [(cx, yi), (cx + s * R * 0.35, yi - 10), (cx + s * R * 0.72, yi + 2),
                       (cx + s * R, yi + 16)]
                ln = cv.create_line(cx, yi, cx, yi, fill=MA_BONE, width=4, capstyle="round",
                                    smooth=True, tags="fx")
                ribs.append((ln, pts, i))
        items = [spine] + [r[0] for r in ribs]
        dur = 0.9

        def part(pts, q):
            n_ = len(pts) - 1
            f = max(0.0, min(1.0, q)) * n_
            k = int(f)
            out = list(pts[:k + 1])
            if k < n_:
                (ax, ay), (bx, by) = pts[k], pts[k + 1]
                r = f - k
                out.append((ax + (bx - ax) * r, ay + (by - ay) * r))
            if len(out) < 2:
                out = [out[0], out[0]]
            flat = []
            for px, py in out:
                flat.extend((px, py))
            return flat

        def up(p, e):
            col = lerp_color(MA_BONE, BG, max(0.0, (p - 0.7) / 0.3))
            q = min(1.0, p / 0.35)
            cv.coords(spine, cx, ys[0], cx, ys[0] + (ys[-1] - ys[0]) * q)
            cv.itemconfig(spine, fill=col)
            for ln, pts, i in ribs:
                rq = max(0.0, min(1.0, (p - 0.1 - i * 0.05) / 0.3))
                cv.coords(ln, *part(pts, rq))
                cv.itemconfig(ln, fill=col)

        self.add_fx(items, dur, up)
        self.fx_flash(uid, MA_BONE, "gray25")
        beep([(180, 40), (140, 60), (110, 90)], self.sound)

    def fx_curtain(self, target_ids):
        """폐장 — 막이 좌우에서 닫히고, 닫히는 순간 뼈와 살점이 흩뿌려진다."""
        cv = self.canvas
        y0, y1 = ENEMY_Y - 10, ENEMY_Y + CARD_H + 10
        left = cv.create_rectangle(0, y0, 0, y1, fill="#5A0F1C", outline=MA_BONE, width=3,
                                   stipple="gray50", tags="fx")
        right = cv.create_rectangle(WIN_W, y0, WIN_W, y1, fill="#5A0F1C", outline=MA_BONE, width=3,
                                    stipple="gray50", tags="fx")
        dur = 1.1

        def up(p, e):
            q = min(1.0, p / 0.6)
            half = WIN_W / 2 * (q * q * (3 - 2 * q))
            cv.coords(left, 0, y0, half, y1)
            cv.coords(right, WIN_W - half, y0, WIN_W, y1)
            fade = max(0.0, (p - 0.75) / 0.25)
            cv.itemconfig(left, outline=lerp_color(MA_BONE, BG, fade))
            cv.itemconfig(right, outline=lerp_color(MA_BONE, BG, fade))

        self.add_fx([left, right], dur, up)
        beep([(220, 80), (160, 100), (110, 160)], self.sound)

        def burst():
            for tid in target_ids:
                self.fx_flash(tid, UB_RED, "gray50")
                self.fx_particles(tid, MA_BONE, n=24, spread=170, dur=0.6, size=4)
                self.fx_particles(tid, "#B0192E", n=16, spread=140, dur=0.6, size=5)
                self.shakes[tid] = 0.5

        self.root.after(int(dur * 600), burst)

    # ================================================================
    # 마에스트로/H 스킬 이펙트 — 골도 티비아 (뼈 칼)
    # ================================================================
    def _ma_blade_make(self, length):
        """양끝이 뾰족한 뼈 칼. place(x, y, 각도(rad), fade, 보임) 으로 자세를 잡는다."""
        cv = self.canvas
        L = float(length)
        body_col = lerp_color(MA_BONE, MA_BLOOD, 0.3)
        body = cv.create_polygon(*([0] * 16), fill=body_col, outline=MA_BLOOD, width=2,
                                 state="hidden", tags="fx")
        teeth = [cv.create_polygon(*([0] * 6), fill=MA_BONE, outline=MA_BLOOD, width=1,
                                   state="hidden", tags="fx") for _ in range(4)]
        knobs = [cv.create_oval(0, 0, 0, 0, fill=MA_BONE, outline=MA_BLOOD, width=2,
                                state="hidden", tags="fx") for _ in range(2)]
        band = cv.create_line(0, 0, 0, 0, fill=MA_BLOOD, width=3, state="hidden", tags="fx")
        items = [body] + teeth + knobs + [band]

        def place(x, y, ang, fade, vis=True):
            st = "normal" if vis else "hidden"
            c, s = math.cos(ang), math.sin(ang)

            def T(lx, ly):
                return (x + lx * c - ly * s, y + lx * s + ly * c)

            w = L * 0.052
            pts = []
            for lx, ly in ((-.5, 0), (-.25, -.7), (0, -1), (.25, -.7),
                           (.5, 0), (.25, .7), (0, 1), (-.25, .7)):
                pts.extend(T(lx * L, ly * w))
            cv.coords(body, *pts)
            cv.itemconfig(body, state=st, fill=lerp_color(body_col, BG, fade),
                          outline=lerp_color(MA_BLOOD, BG, fade))
            for k, tooth in enumerate(teeth):              # 늑골 가시 (한쪽 날)
                lx = L * (-0.3 + 0.2 * k)
                edge = w * (1 - 1.2 * abs(lx) / L)
                a1 = T(lx - L * 0.035, -edge)
                a2 = T(lx + L * 0.03, -edge)
                a3 = T(lx - L * 0.02, -edge - L * 0.09)
                cv.coords(tooth, a1[0], a1[1], a2[0], a2[1], a3[0], a3[1])
                cv.itemconfig(tooth, state=st, fill=lerp_color(MA_BONE, BG, fade),
                              outline=lerp_color(MA_BLOOD, BG, fade))
            r = L * 0.04
            for k, kn in enumerate(knobs):                 # 마디
                kx, ky = T((-0.17 if k == 0 else 0.17) * L, 0)
                cv.coords(kn, kx - r, ky - r, kx + r, ky + r)
                cv.itemconfig(kn, state=st, fill=lerp_color(MA_BONE, BG, fade),
                              outline=lerp_color(MA_BLOOD, BG, fade))
            b1, b2 = T(0, -w * 1.25), T(0, w * 1.25)
            cv.coords(band, b1[0], b1[1], b2[0], b2[1])
            cv.itemconfig(band, state=st, fill=lerp_color(MA_BLOOD, BG, fade))

        return items, place

    def _ma_stroke(self, path, col_main, col_glow, dur=0.3, width=1.0):
        """path 를 따라 머리가 달리고 꼬리가 따라붙으며 사라지는 3겹 궤적."""
        cv = self.canvas
        x0, y0 = path[0]

        def mk(col, w):
            return cv.create_line(x0, y0, x0, y0, fill=col, width=w * width, capstyle="round",
                                  smooth=True, state="hidden", tags="fx")

        layers = [(mk(col_glow, 15), 0.75, col_glow), (mk(col_main, 7), 0.58, col_main),
                  (mk(WHITE, 2), 0.42, WHITE)]

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

    def _ma_move(self, p0, p1, dur, length=190, hit=None, hit_at=0.65, width=1.0):
        """뼈 칼이 p0 → p1 으로 휘둘러진다. p = (x, y, 각도°)  (각도: 오른쪽 0°, 아래 +90°)"""
        x0, y0, a0 = p0
        x1, y1, a1 = p1
        a0, a1 = math.radians(a0), math.radians(a1)
        items, place = self._ma_blade_make(length)

        def pose(q):
            e = q * q * (3 - 2 * q)
            return x0 + (x1 - x0) * e, y0 + (y1 - y0) * e, a0 + (a1 - a0) * e

        path = []
        for i in range(21):
            x, y, a = pose(i / 20.0)
            path.append((x + math.cos(a) * length / 2, y + math.sin(a) * length / 2))
        self._ma_stroke(path, MA_BONE, MA_BLOOD, dur / 0.58, width)
        hold = 0.14
        total = dur + hold

        def up(p, e):
            t = p * total
            x, y, a = pose(min(1.0, t / dur))
            place(x, y, a, max(0.0, (t - dur) / hold), True)

        self.add_fx(items, total, up)
        if hit:
            self.root.after(int(hit_at * dur * 1000), hit)

    def _ma_streak(self, x, y, ang_deg, length=240, dur=0.28):
        cv = self.canvas
        a = math.radians(ang_deg)
        dx, dy = math.cos(a) * length / 2, math.sin(a) * length / 2
        wide = cv.create_line(x - dx, y - dy, x + dx, y + dy, fill=UB_RED, width=7,
                              capstyle="round", tags="fx")
        thin = cv.create_line(x - dx, y - dy, x + dx, y + dy, fill=MA_BONE, width=3,
                              capstyle="round", tags="fx")

        def up(p, e):
            cv.itemconfig(wide, fill=lerp_color(UB_RED, BG, min(1.0, p * 1.4)),
                          width=max(1, 7 * (1 - p)))
            cv.itemconfig(thin, fill=lerp_color(MA_BONE, BG, p))

        self.add_fx([wide, thin], dur, up)

    def _ma_hit(self, uid, big=False, ang=0):
        cx, cy = self.center_of(uid)
        self.fx_flash(uid, MA_BONE, "gray50")
        self.fx_particles(uid, MA_BONE, n=24 if big else 14, spread=130, dur=0.45, size=3)
        self.fx_particles(uid, MA_BLOOD, n=10, spread=105, dur=0.5, size=4)
        self._ma_streak(cx, cy, ang, 300 if big else 230)
        self.shakes[uid] = 0.4 if big else 0.25
        beep([(random.randint(130, 210), 28)], self.sound)

    # ---- 스킬 1 : 위에서 아래로 정면 베기 ----
    def fx_ma_skill1(self, uid):
        cx, cy = self.center_of(uid)
        self._ma_move((cx + 14, cy - 190, -84), (cx - 8, cy + 150, 92), 0.2, length=210,
                      hit=lambda: self._ma_hit(uid, False, 90), hit_at=0.62)
        return 190

    # ---- 스킬 2 : 정면 찌르기 2번 → 좌우로 베기 ----
    def fx_ma_skill2(self, uid):
        cx, cy = self.center_of(uid)
        self._ma_move((cx, cy + 340, -90), (cx, cy - 10, -90), 0.17, length=200,
                      hit=lambda: self._ma_hit(uid, False, -90), hit_at=0.78)
        self.root.after(240, lambda: self._ma_move(
            (cx + 16, cy + 340, -90), (cx + 16, cy - 20, -90), 0.17, length=200,
            hit=lambda: self._ma_hit(uid, False, -90), hit_at=0.78))
        self.root.after(520, lambda: self._ma_move(
            (cx - 215, cy - 30, -70), (cx + 215, cy + 20, 70), 0.2, length=210,
            hit=lambda: self._ma_hit(uid, True, 20), hit_at=0.5))
        self.root.after(770, lambda: self._ma_move(
            (cx + 215, cy + 20, -110), (cx - 215, cy - 30, 110), 0.2, length=210,
            hit=lambda: self._ma_hit(uid, True, -20), hit_at=0.5))
        return 770 + 150

    # ---- 스킬 2-2 : 뼈가 휘감아 묶는다 ----
    def fx_ma_bind(self, uid):
        cv = self.canvas
        x, y, w, h = self.rect_of(uid)
        cx, cy = x + w / 2, y + h / 2
        R = min(w / 2 - 10, 120)
        dur = 1.2
        sp, items = [], []
        for s in (-1, 1):
            for k in range(3):
                S = (cx + s * (R + 40 + k * 14), y + h + 36)
                C = (cx + s * (R + 10 - k * 20), cy - 10 + k * 8)
                E = (cx - s * (10 + k * 26), cy - 70 + k * 34)
                path = []
                for i in range(25):
                    q = i / 24.0
                    path.append(((1 - q) ** 2 * S[0] + 2 * (1 - q) * q * C[0] + q * q * E[0],
                                 (1 - q) ** 2 * S[1] + 2 * (1 - q) * q * C[1] + q * q * E[1]))
                dark = cv.create_line(S[0], S[1], S[0], S[1], fill=MA_BLOOD, width=12,
                                      capstyle="round", smooth=True, state="hidden", tags="fx")
                bone = cv.create_line(S[0], S[1], S[0], S[1], fill=MA_BONE, width=6,
                                      capstyle="round", smooth=True, state="hidden", tags="fx")
                tip = cv.create_polygon(0, 0, 0, 0, 0, 0, fill=MA_BONE, outline=MA_BLOOD,
                                        state="hidden", tags="fx")
                sp.append(dict(path=path, dark=dark, bone=bone, tip=tip,
                               d=0.05 * k + (0.0 if s < 0 else 0.08)))
                items += [dark, bone, tip]
        rings = [cv.create_oval(cx, cy, cx, cy, outline=MA_BONE, width=4, state="hidden",
                                tags="fx") for _ in range(2)]
        items += rings

        def up(p, e):
            fade = max(0.0, (p - 0.8) / 0.2)
            for d in sp:
                q = max(0.0, min(1.0, (p - d["d"]) / 0.45))
                q = q * q * (3 - 2 * q)
                seg = self._fx_poly_slice(d["path"], 0.0, q)
                if not seg:
                    continue
                cv.coords(d["dark"], *seg)
                cv.coords(d["bone"], *seg)
                cv.itemconfig(d["dark"], state="normal", fill=lerp_color(MA_BLOOD, BG, fade))
                cv.itemconfig(d["bone"], state="normal", fill=lerp_color(MA_BONE, BG, fade))
                hx, hy = seg[-2], seg[-1]
                px, py = seg[-4], seg[-3]
                L = max(1.0, math.hypot(hx - px, hy - py))
                ux, uy = (hx - px) / L, (hy - py) / L
                cv.coords(d["tip"], hx + ux * 20, hy + uy * 20,
                          hx - ux * 4 - uy * 8, hy - uy * 4 + ux * 8,
                          hx - ux * 4 + uy * 8, hy - uy * 4 - ux * 8)
                cv.itemconfig(d["tip"], state="normal", fill=lerp_color(MA_BONE, BG, fade),
                              outline=lerp_color(MA_BLOOD, BG, fade))
            if p > 0.55:
                g = min(1.0, (p - 0.55) / 0.2)
                for i, rg in enumerate(rings):
                    rx = (R * 0.8 + i * 22) * (0.6 + 0.4 * g)
                    ry = rx * 0.38
                    yy = cy - 6 + i * 34
                    cv.coords(rg, cx - rx, yy - ry, cx + rx, yy + ry)
                    cv.itemconfig(rg, state="normal", outline=lerp_color(MA_BONE, BG, fade))

        self.add_fx(items, dur, up)

        def impact():
            self.fx_flash(uid, MA_BONE, "gray50")
            self.fx_particles(uid, MA_BONE, n=22, spread=120, dur=0.5, size=3)
            self.fx_particles(uid, MA_BLOOD, n=12, spread=100, dur=0.55, size=4)
            self.shakes[uid] = 0.35
            beep([(180, 40), (140, 60), (110, 90)], self.sound)

        self.root.after(int(0.55 * dur * 1000), impact)

    # ---- 스킬 3 : GIF 동작 (찌르기 2번 → 올려베기 → 내려찍기 → 낮게 휩쓸기) ----
    def _ma_gif_sequence(self, cx, cy, half, ids):
        main = ids[0]
        L = 200

        def hit(ang, big=False):
            return lambda: self._ma_hit(main, big, ang)

        self._ma_move((cx - 340, cy + 4, 0), (cx + 70, cy + 4, 0), 0.2, L, hit=hit(0), hit_at=0.72)
        self.root.after(270, lambda: self._ma_move(
            (cx - 340, cy - 10, 0), (cx + 80, cy - 10, 0), 0.2, L, hit=hit(0), hit_at=0.72))
        self.root.after(560, lambda: self._ma_move(
            (cx - 70, cy + 90, 40), (cx + 60, cy - 90, -70), 0.24, L, hit=hit(-60), hit_at=0.65))
        self.root.after(850, lambda: self._ma_move(
            (cx - 20, cy - 160, -80), (cx + 20, cy + 120, 70), 0.22, L + 20,
            hit=hit(90, True), hit_at=0.7))
        self.root.after(1130, lambda: self._ma_move(
            (cx - half - 230, cy + 50, 0), (cx + half + 230, cy + 50, 0), 0.3, L + 30,
            hit=lambda: [self._ma_hit(i, True, 0) for i in ids], hit_at=0.55, width=1.3))
        return 1130 + 300

    def fx_ma_melody(self, ids):
        cx, cy = self.center_of(ids[0])
        half = max([abs(self.center_of(i)[0] - cx) for i in ids] + [0])
        return self._ma_gif_sequence(cx, cy, half, ids)

    # ---- 스킬 3-2 : 같은 연출 → 어둠 속에서 뼈 창과 붉은 선이 사방에서 꽂힌다 ----
    def fx_ma_closing(self, ids):
        pts = [self.center_of(i) for i in ids]
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        half = max(abs(p[0] - cx) for p in pts)
        gif_ms = self._ma_gif_sequence(cx, cy, half, ids)
        start = gif_ms - 100
        self.root.after(start, lambda: self.fx_ma_finale(ids, cx, cy))
        return start + 820

    def fx_ma_finale(self, ids, cx, cy):
        cv = self.canvas
        dur = 1.5
        veil = cv.create_rectangle(0, 0, WIN_W, WIN_H, fill="#000000", outline="",
                                   stipple="gray50", tags="fx")
        reds = []
        for i in range(18):
            a = random.uniform(-0.5, 0.5) + (math.pi / 2 if i % 3 else 0.0)
            px = cx + random.uniform(-380, 380)
            py = cy + random.uniform(-120, 160)
            ln = cv.create_line(px, py, px, py, fill=UB_RED, width=random.choice((2, 2, 3)),
                                capstyle="round", state="hidden", tags="fx")
            reds.append((ln, px, py, a, random.uniform(0.0, 0.5)))
        spikes = []
        for i in range(16):
            tid = random.choice(ids)
            tx, ty = self.center_of(tid)
            tp = (tx + random.uniform(-70, 70), ty + random.uniform(-45, 45))
            ang = random.uniform(0, math.tau)
            u = (math.cos(ang), math.sin(ang))
            far = (tp[0] - u[0] * 560, tp[1] - u[1] * 560)
            poly = cv.create_polygon(*([0] * 22), fill=MA_BONE, outline=MA_BLOOD, width=1,
                                     state="hidden", tags="fx")
            spikes.append(dict(poly=poly, far=far, tp=tp, u=u, L=random.uniform(230, 330),
                               w=random.uniform(12, 17), d=random.uniform(0.08, 0.5)))
        items = [veil] + [r[0] for r in reds] + [s["poly"] for s in spikes]

        def up(p, e):
            fade = max(0.0, (p - 0.85) / 0.15)
            cv.itemconfig(veil, stipple=("gray50" if p < 0.12 else ("gray75" if p < 0.85 else "gray25")))
            for ln, px, py, a, d in reds:
                q = max(0.0, min(1.0, (p - d) / 0.15))
                if q <= 0:
                    continue
                hx, hy = math.cos(a) * 340 * q, math.sin(a) * 340 * q
                cv.coords(ln, px - hx, py - hy, px + hx, py + hy)
                cv.itemconfig(ln, state="normal", fill=lerp_color(UB_RED, BG, fade))
            for sk in spikes:
                q = max(0.0, min(1.0, (p - sk["d"]) / 0.14))
                if q <= 0:
                    continue
                q = q * q * (3 - 2 * q)
                ux, uy = sk["u"]
                tipx = sk["far"][0] + (sk["tp"][0] - sk["far"][0]) * q
                tipy = sk["far"][1] + (sk["tp"][1] - sk["far"][1]) * q
                nx, ny = -uy, ux
                pts = [tipx, tipy]
                right, left = [], []
                for k in range(1, 6):
                    s = sk["L"] * k / 5.0
                    base = (tipx - ux * s, tipy - uy * s)
                    hr = sk["w"] * (k / 5.0) ** 0.7 * (1.0 if k % 2 else 0.6)
                    hl = sk["w"] * (k / 5.0) ** 0.7 * (0.6 if k % 2 else 1.0)
                    right.extend((base[0] + nx * hr, base[1] + ny * hr))
                    left = [base[0] - nx * hl, base[1] - ny * hl] + left
                pts.extend(right)
                pts.extend(left)
                cv.coords(sk["poly"], *pts)
                cv.itemconfig(sk["poly"], state="normal", fill=lerp_color(MA_BONE, BG, fade),
                              outline=lerp_color(MA_BLOOD, BG, fade))

        self.add_fx(items, dur, up)
        beep([(110, 120), (90, 160)], self.sound)

        def slam():
            for tid in ids:
                self.fx_flash(tid, WHITE, "gray50")
                self.fx_particles(tid, MA_BONE, n=26, spread=190, dur=0.6, size=4)
                self.fx_particles(tid, MA_BLOOD, n=16, spread=150, dur=0.6, size=5)
                self.shakes[tid] = 0.5
            beep([(200, 60), (120, 120)], self.sound)

        self.root.after(int(0.55 * dur * 1000), slam)

    def fx_ma_total(self, per, total):
        """큼직한 황금 피해 숫자 + CRITICAL! + TOTAL."""
        cv = self.canvas
        entries, items = [], []
        for uid, n in per:
            if n <= 0:
                continue
            x, y = self.center_of(uid)
            back = cv.create_text(x + 3, y - 1, text=str(n), fill=MA_GOLD_D,
                                  font=(self.fm, 46, "bold"), tags="fx")
            fore = cv.create_text(x, y - 4, text=str(n), fill=MA_GOLD,
                                  font=(self.fm, 46, "bold"), tags="fx")
            sub = cv.create_text(x, y + 34, text="CRITICAL!", fill="#FF9A2E",
                                 font=(self.fm, 18, "bold"), tags="fx")
            entries.append((back, fore, sub, x, y))
            items += [back, fore, sub]
        tx, ty = WIN_W / 2, PANEL_Y + 8
        tb = cv.create_text(tx + 3, ty + 3, text="TOTAL  %d" % total, fill=MA_GOLD_D,
                            font=(self.fm, 40, "bold"), tags="fx")
        tf = cv.create_text(tx, ty, text="TOTAL  %d" % total, fill=MA_GOLD,
                            font=(self.fm, 40, "bold"), tags="fx")
        items += [tb, tf]

        def up(p, e):
            pop = min(1.0, p / 0.12)
            fade = max(0.0, (p - 0.7) / 0.3)
            rise = 24 * min(1.0, p * 0.6)
            size = int(46 * (0.6 + 0.4 * pop))
            for back, fore, sub, x, y in entries:
                cv.coords(back, x + 3, y - 1 - rise)
                cv.coords(fore, x, y - 4 - rise)
                cv.coords(sub, x, y + 34 - rise)
                cv.itemconfig(back, fill=lerp_color(MA_GOLD_D, BG, fade), font=(self.fm, size, "bold"))
                cv.itemconfig(fore, fill=lerp_color(MA_GOLD, BG, fade), font=(self.fm, size, "bold"))
                cv.itemconfig(sub, fill=lerp_color("#FF9A2E", BG, fade))
            cv.itemconfig(tb, fill=lerp_color(MA_GOLD_D, BG, fade))
            cv.itemconfig(tf, fill=lerp_color(MA_GOLD, BG, fade))

        self.add_fx(items, 1.8, up)
        beep([(660, 50), (880, 70), (1320, 120)], self.sound)

    def admin_equip_maestro(self):
        unit = self.units.get("H")
        if not unit or unit.side != "ally":
            return
        unit.fate_hp_spent = 0
        unit.fate_ready = False
        unit.hero_buff = False
        unit.hero_revive_used = False
        unit.hero_passive_shield_gained = 0
        unit.hero_echo_used = False
        unit.hero_echo_channel = None
        unit.aspect_id = MAESTRO_ASPECT["id"]
        unit.skills = MAESTRO_ASPECT["skills"]
        unit.max_sp = MAX_SP
        unit.sp = min(unit.sp, unit.max_sp)
        self.ma_reset(unit)
        self.log("[ADMIN] H에게 [마에스트로/H] 형상을 장착했다. (이번 전투 한정)", UB_RED)
        self.fx_flash(unit.id, UB_RED, "gray50")
        beep([(220, 60), (330, 70), (440, 120)], self.sound)
        self.render()

    def admin_unequip_maestro(self):
        unit = self.units.get("H")
        if not unit or not self.is_maestro(unit):
            return
        aid = self.__dict__.get("equipped", {}).get("H", "h_base")
        self.equip_aspect(aid)
        self.log("[ADMIN] 마에스트로/H 장착을 해제했다.", UB_RED)
        self.render()

    def maestro_tip_lines(self):
        c1, c2, c3 = MA_COSTS
        return [
            "★★★ 특별해석 {거미집} 전용 형상 — 형상해석 [▶] 거미집 테마에서 얻는다",
            "기본효과: 조망",
            "   전투 시작시 조망 21 · 턴 시작시 -2 · 아군이 수비 행동 외 행동시 -1 (턴당 최대 -4)",
            "   조망이 0이 되면 스킬 3 → 3-2 [폐장] (전투당 1회) · 조망 자체는 효과 없음",
            "패시브: 일생의 작품 (관측불가)",
            "   전투 시작시 생체재료 1 · 스킬 1/2/3 사용마다 +1/+2/+3",
            "   10 에 도달하면 전부 소비하고 이번 전투동안 걸작 획득 (자신의 공격력 +5)",
            "스킬 1: 해체 [%d포인트 소비]" % c1,
            "   지정한 적에게 20 피해",
            "스킬 2: 재료 획득-피로 목욕하는 오브제 [%d포인트 소비]" % c2,
            "   지정한 적에게 40 피해 · 50% 확률로 2-2 [간이늑골] 사용",
            "스킬 2-2: 설치 미술 제 3호 '간이늑골' [포인트 소모/획득 없음]",
            "   대상에게 5 피해 · 간이늑골 2 부여",
            "   간이늑골: 대상의 속도 주사위 최대값 절반 감소 · 매 턴 1 감소 · 0이 되면 소멸",
            "스킬 3: 티비아의 멜로디 - 해체된 것이 해체되지 않은 것을 해체하는 것 [%d포인트 소비]" % c3,
            "   지정한 대상에게 55 피해 · 걸작 보유시 양 옆 대상에게 45 피해",
            "스킬 3-2: 폐장 - 설치미술 제 1호 '여러분이 흩뿌린 살과 뼈가 객석이 되어' [포인트 소모/획득 없음]",
            "   수비 스킬 무시 · 모든 적에게 120 고정피해 · 모든 적에게 간이늑골 3 · 아군에게 선율",
            "   선율: 속도 +1 (최대 6) · 공격력 +5",
        ]

    # ================================================================
    # ★★★ 큰누님/N (거미집 형상 — 큰누님 패치)
    # ================================================================
    def is_bigsis(self, unit):
        return unit.side == "ally" and unit.aspect_id == "n_bigsis"

    def bs_reset(self, unit):
        unit.bs_wrap = BS_WRAP_START
        unit.bs_leva = False
        unit.bs_fun = BS_FUN_START
        unit.bs_counter_uses = 0

    def bs_clear(self, unit):
        unit.bs_wrap = 0
        unit.bs_leva = False
        unit.bs_fun = 0
        unit.bs_counter_uses = 0

    def bs_check_leva(self, unit):
        """포장이 0 이 되면 봉인된 검 [레바테인] 개방."""
        if unit.bs_wrap > 0 or unit.bs_leva or not unit.alive:
            return
        unit.bs_leva = True
        unit.bs_fun = 0                 # 레바테인 개방 — 달아오르는 재미 제거
        self.log("%s의 달아오르는 재미가 사라졌다 — [포장을 벗겨볼까]를 더 이상 사용할 수 없다." % unit.name, MUT)
        self.log("%s의 포장이 모두 벗겨졌다 — 봉인된 검 [레바테인] 개방! (공격력 +5 · 스킬이 전용 스킬로 변경)"
                 % unit.name, BS_FIRE)
        self.fx_flash(unit.id, BS_FIRE, "gray50")
        self.fx_number(unit.id, "레바테인", BS_FIRE, 22, dy=-34)
        self.fx_particles(unit.id, BS_FIRE, n=30, spread=170, dur=0.7, size=5)
        beep([(220, 60), (330, 70), (440, 90), (660, 140)], self.sound)

    def bs_burn_tick(self):
        """라운드 시작 — 화상 수치만큼 피해를 입고 화상은 전부 제거된다. 웨이브가 끝나면 True."""
        burned = [u for u in self.units.values() if u.alive and u.burn > 0]
        if not burned:
            return False
        for u in burned:
            n = u.burn
            u.burn = 0
            u.hp = max(0, u.hp - n)
            self.fx_number(u.id, "-%d" % n, BS_FIRE, 22)
            self.fx_particles(u.id, BS_FIRE, n=14, spread=90, dur=0.5, size=3)
            self.shakes[u.id] = 0.2
            self.log("[화상] %s이(가) 화상으로 %d 피해를 입었다. 화상이 사라졌다." % (u.name, n), BS_FIRE)
            if not u.alive:
                self.log("%s이(가) 전투불능 상태가 됐다." % u.name, TXT)
                if u.side == "enemy":
                    self.aspect_shards += 10
                    self.log("적 처치 보상: 조각 +10 (보유 %d개)" % self.aspect_shards, SPC)
                    queued = []
                    self.drop_loot(u, queued)
                    for msg, color in queued:
                        self.log(msg, color)
        self.render()
        return self.check_end()

    def bs_counter_hit(self, unit, attacker, cb, dealt):
        """반격 — 받은 피해량의 50% 를 되돌려준다 (이 피해로 적을 처치할 수 없다)."""
        if (dealt <= 0 or attacker is None or attacker.side != "enemy"
                or not attacker.alive or not unit.alive):
            cb(dealt)
            return
        back = min(round(dealt * 0.5), attacker.hp - 1)
        if back <= 0:
            cb(dealt)
            return
        attacker.hp -= back
        self.log("%s의 반격! '하하 이리와라!' %s에게 %d 피해 (처치 불가)." %
                 (unit.name, attacker.name, back), BS_FIRE)
        self.fx_hit(attacker.id)
        self.fx_number(attacker.id, "-%d" % back, BS_FIRE, 20)
        self.shakes[attacker.id] = 0.25
        self.render()
        cb(dealt)

    def bs_counter_upkeep(self, u, done):
        """반격 태세 해결 — 2회 사용마다 달아오르는 재미 -1, 0 이 되면 {포장을 벗겨볼까}."""
        u.bs_counter_uses += 1
        self.log("%s은 반격 태세를 유지한다." % u.name, BS_FIRE)
        if not u.bs_leva and u.bs_counter_uses % 2 == 0:
            u.bs_fun = max(0, u.bs_fun - 1)
            self.fx_number(u.id, "재미 %d" % u.bs_fun, SPC, 14, dy=-30)
            self.log("달아오르는 재미 -1 (남은 %d)." % u.bs_fun, SPC)
            if u.bs_fun <= 0:
                self.bs_unwrap(u, done)
                return
        self.schedule(320, done)

    def bs_unwrap(self, u, done):
        """{포장을 벗겨볼까} — SP 무관, 방어행동 무시. 무작위 적에게 30 피해, 포장 -1, 재미 +2."""
        if u.bs_leva:                  # 레바테인 — 달아오르는 재미가 없어 사용 불가
            done()
            return
        targets = [e for e in self.enemies() if e.alive]
        if not targets or not u.alive:
            u.bs_fun = max(u.bs_fun, BS_FUN_START)
            done()
            return
        t = random.choice(targets)
        quotes = {3: "그쯤 해줬으니 포장지 한번 벗겨야겠군!", 2: "하하하 재밌군!", 1: "두눈 크게 뜨고 잘 봐라!"}
        if quotes.get(u.bs_wrap):          # 남은 포장 수치에 맞는 대사 하나만 출력
            self.log("%s: '%s'" % (u.name, quotes[u.bs_wrap]), BS_FIRE)
        else:
            self.log("%s의 [포장을 벗겨볼까]!" % u.name, BS_FIRE)
        _bsx_ms = self.fx_bs_unwrap(u.id, t.id)

        def after(dealt):
            self.log("[포장을 벗겨볼까] %s에게 %d 피해 (방어행동 무시)." % (t.name, dealt), BS_FIRE)
            if dealt > 0 and t.alive and u.bs_leva:
                t.burn += BS_BURN
                self.fx_number(t.id, "화상 +%d" % BS_BURN, BS_FIRE, 15, dy=-30)
                self.log("[레바테인] %s에게 화상 %d 부여 (누적 %d)." % (t.name, BS_BURN, t.burn), BS_FIRE)
            u.bs_wrap = max(0, u.bs_wrap - 1)
            u.bs_fun += 2
            self.fx_number(u.id, "포장 %d" % u.bs_wrap, BS_FIRE, 16, dy=-30)
            self.log("%s의 포장 -1 (남은 %d) · 달아오르는 재미 +2 (%d)." %
                     (u.name, u.bs_wrap, u.bs_fun), BS_FIRE)
            self.bs_check_leva(u)
            done()

        self.schedule(_bsx_ms, lambda: self.apply_damage(u, t, 30, "heavy", after, skip_defense=True))

    def _bsx_rise(self, tid, dur=0.5):
        """아래에서 위로 치솟는 속도선 — 들어올리는 느낌."""
        cv = self.canvas
        x, y, w, h = self.rect_of(tid)
        items, data = [], []
        for _ in range(10):
            px = x + random.uniform(0.08, 0.92) * w
            col = random.choice((BSX_PUR_L, BSX_ORG_L, BSX_ORG, BSX_PUR))
            ln = cv.create_line(px, y + h, px, y + h, fill=col, width=random.choice((2, 3, 4)),
                                capstyle="round", tags="fx")
            items.append(ln)
            data.append((ln, px, random.uniform(70, 150), random.uniform(0, 0.3), col))

        def up(p, e):
            for ln, px, L, d0, col in data:
                q = (p - d0) / (1.0 - d0)
                if q <= 0:
                    continue
                head = y + h + 20 - (h + 120) * self._bsx_ease(q)
                cv.coords(ln, px, head + L * (1 - q * 0.6), px, head)
                cv.itemconfig(ln, fill=lerp_color(col, BG, q * q))

        self.add_fx(items, dur, up)

    def _bsx_dust(self, cx, cy, n=7, spread=90, dur=0.7, col="#CFC6E6"):
        cv = self.canvas
        items, data = [], []
        for _ in range(n):
            it = cv.create_oval(cx, cy, cx, cy, fill=col, outline="", stipple="gray25", tags="fx")
            items.append(it)
            data.append((it, random.uniform(-0.5, 0.5) * spread, random.uniform(-0.1, 0.2) * spread * 0.5,
                         random.uniform(14, 28), random.uniform(0.6, 1.4)))

        def up(p, e):
            for it, ox, oy, r, sp in data:
                rr = r * (0.5 + 1.1 * p)
                x = cx + ox * (0.4 + p * sp * 1.6)
                y = cy + oy - 26 * p * sp
                cv.coords(it, x - rr, y - rr * 0.7, x + rr, y + rr * 0.7)
                cv.itemconfig(it, fill=lerp_color(col, BG, min(1.0, p * 1.1)))

        self.add_fx(items, dur, up)

    def _bsx_cracks(self, cx, cy, n=9, length=120, dur=0.6):
        cv = self.canvas
        items, data = [], []
        for i in range(n):
            a = random.uniform(-0.25, 0.25) + (0.0 if i % 2 == 0 else math.pi)
            glow = cv.create_line(cx, cy, cx, cy, fill=BSX_ORG, width=5, capstyle="round", tags="fx")
            core = cv.create_line(cx, cy, cx, cy, fill=BSX_ORG_L, width=2, capstyle="round", tags="fx")
            items += [glow, core]
            data.append((glow, core, a, random.uniform(0.5, 1.0) * length, random.uniform(-14, 14)))

        def up(p, e):
            g = self._bsx_ease(p * 2.5)
            fade = max(0.0, (p - 0.5) / 0.5)
            for glow, core, a, L, dy in data:
                x1 = cx + math.cos(a) * L * g
                y1 = cy + math.sin(a) * L * g * 0.35 + dy * g
                for it in (glow, core):
                    cv.coords(it, cx, cy, (cx + x1) / 2, cy + (y1 - cy) * 0.4 + 6, x1, y1)
                cv.itemconfig(glow, fill=lerp_color(BSX_ORG, BG, fade))
                cv.itemconfig(core, fill=lerp_color(BSX_ORG_L, BG, fade))

        self.add_fx(items, dur, up)

    def _bsx_flame(self, uid, dur=0.9, scale=1.0):
        """시전자 주변에 치솟는 보라 불꽃 오라."""
        cv = self.canvas
        x, y, w, h = self.rect_of(uid)
        cx, base = x + w / 2, y + h - 6
        cols = (BSX_PUR_D, BSX_PUR, BSX_PUR_L, BSX_PUR, BSX_PUR_D)
        items, data = [], []
        for i in range(11):
            col = cols[i % 5]
            it = cv.create_polygon(cx, base, cx, base, cx, base, cx, base, cx, base,
                                   fill=col, outline="", tags="fx")
            items.append(it)
            data.append((it, (i - 5) * 13 * scale, col, random.uniform(0, 6.28),
                         random.uniform(0.6, 1.0) * (1 - abs(i - 5) * 0.09)))

        def up(p, e):
            grow = self._bsx_ease(p / 0.3)
            fade = max(0.0, (p - 0.72) / 0.28)
            for it, off, col, ph, k in data:
                H = (h + 80) * scale * k * grow * (1 - 0.85 * fade) * (0.85 + 0.15 * math.sin(p * 40 + ph))
                bx = cx + off
                sw = math.sin(p * 18 + ph) * 10 * scale
                cv.coords(it, bx - 14 * scale, base, bx - 9 * scale + sw * 0.4, base - H * 0.5,
                          bx + sw, base - H, bx + 9 * scale + sw * 0.4, base - H * 0.5,
                          bx + 14 * scale, base)
                cv.itemconfig(it, fill=lerp_color(col, BG, fade))

        self.add_fx(items, dur, up)
        self.fx_particles(uid, BSX_PUR_L, n=16, spread=110, dur=0.8, size=3)

    def _bsx_orb(self, uid, dur=0.8):
        """시전자 주위에 커지는 보라 구체."""
        cv = self.canvas
        cx, cy = self.center_of(uid)
        body = cv.create_oval(cx, cy, cx, cy, fill=lerp_color(BG, BSX_PUR, 0.5), outline="",
                              stipple="gray50", tags="fx")
        ring = cv.create_oval(cx, cy, cx, cy, outline=BSX_PUR, width=4, tags="fx")
        ring2 = cv.create_oval(cx, cy, cx, cy, outline=BSX_PUR_L, width=2, tags="fx")

        def up(p, e):
            r = 24 + 76 * self._bsx_ease(p / 0.7) + 4 * math.sin(p * 30)
            fade = max(0.0, (p - 0.8) / 0.2)
            cv.coords(body, cx - r, cy - r, cx + r, cy + r)
            cv.coords(ring, cx - r, cy - r, cx + r, cy + r)
            cv.coords(ring2, cx - r * 0.72, cy - r * 0.72, cx + r * 0.72, cy + r * 0.72)
            cv.itemconfig(body, fill=lerp_color(lerp_color(BG, BSX_PUR, 0.5), BG, fade))
            cv.itemconfig(ring, outline=lerp_color(BSX_PUR, BG, fade))
            cv.itemconfig(ring2, outline=lerp_color(BSX_PUR_L, BG, fade))

        self.add_fx([body, ring, ring2], dur, up)

    def _bsx_vortex(self, tid, dur=0.6):
        """보라 소용돌이 — 바깥에서 안쪽으로 말려 들어간다."""
        cv = self.canvas
        cx, cy = self.center_of(tid)
        arms = []
        for k in range(8):
            col = BSX_PUR_L if k % 3 == 0 else (BSX_ORG if k % 3 == 1 else BSX_PUR)
            ln = cv.create_line(cx, cy, cx, cy, cx, cy, fill=col, width=5 if k % 2 else 3,
                                capstyle="round", smooth=True, tags="fx")
            arms.append((ln, k * math.tau / 8, col))
        core = cv.create_oval(cx, cy, cx, cy, fill=BSX_PUR_L, outline=BSX_PUR, width=2, tags="fx")

        def up(p, e):
            fade = max(0.0, (p - 0.8) / 0.2)
            r = 200 * (1 - self._bsx_ease(p)) + 14
            for ln, base, col in arms:
                pts = []
                for j in range(7):
                    a = base + p * 9 + j * 0.16
                    rr = r * (1 - j * 0.06)
                    pts.extend((cx + math.cos(a) * rr, cy + math.sin(a) * rr * 0.65))
                cv.coords(ln, *pts)
                cv.itemconfig(ln, fill=lerp_color(col, BG, fade))
            cr = 6 + 26 * p
            cv.coords(core, cx - cr, cy - cr, cx + cr, cy + cr)
            cv.itemconfig(core, fill=lerp_color(BSX_PUR_L, BG, fade))

        self.add_fx([a[0] for a in arms] + [core], dur, up)

    def _bsx_hit(self, tid, big=False):
        cx, cy = self.center_of(tid)
        self.fx_flash(tid, BSX_ORG if big else BSX_PUR, "gray50")
        self.fx_particles(tid, BSX_ORG, n=20 if big else 12, spread=140 if big else 100, dur=0.5, size=4)
        self.fx_particles(tid, BSX_PUR_L, n=14 if big else 8, spread=120, dur=0.55, size=3)
        self._bsx_ring(cx, cy, BSX_ORG_L, 12, 130 if big else 90, 0.4, 4)
        self._ub_sparkle(cx, cy, n=5 if big else 3, spread=80, size=(6, 12), dur=0.5,
                         cols=(BSX_ORG_L, BSX_ORG, BSX_PUR_L))
        self.shakes[tid] = 0.4 if big else 0.24
        beep([(random.randint(120, 200), 26)], self.sound)

    def _bsx_swing(self, p0, p1, bend, main, glow, dur=0.28, width=1.2):
        """p0 → p1 을 잇는 휘어진 궤적 한 줄기 (발차기 · 들어올리기 궤적)."""
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = max(1.0, math.hypot(dx, dy))
        qx, qy = mx - dy / L * bend, my + dx / L * bend
        path = []
        for i in range(21):
            q = i / 20.0
            path.append(((1 - q) ** 2 * p0[0] + 2 * (1 - q) * q * qx + q * q * p1[0],
                         (1 - q) ** 2 * p0[1] + 2 * (1 - q) * q * qy + q * q * p1[1]))
        self._ub_stroke(path, main, glow, dur, width)

    def _bsx_kick(self, tid, delay=0):
        """발차기 — 아래쪽에서 대상을 쓸어 올리는 두 겹 궤적 + 충격파 + 먼지."""
        tx, ty = self.center_of(tid)

        def go():
            p0, p1 = (tx - 190, ty + 90), (tx + 190, ty - 40)
            self._bsx_swing(p0, p1, 55, BSX_PUR_L, BSX_PUR, 0.3, 1.5)
            self._bsx_swing((p0[0] + 14, p0[1] + 18), (p1[0] + 14, p1[1] + 18), 40,
                            BSX_ORG_L, BSX_ORG, 0.28, 1.0)
            self.root.after(110, lambda: (self._bsx_hit(tid, False),
                                          self._bsx_dust(tx, ty + 55),
                                          self._bsx_ring(tx, ty + 40, BSX_PUR_L, 10, 120, 0.4, 4, 0.35)))

        if delay:
            self.root.after(delay, go)
        else:
            go()

    def _bsx_slam(self, tid, delay=0, big=False):
        """위에서 아래로 내려찍기 — 충격파 + 바닥 균열 + 먼지."""
        tx, ty = self.center_of(tid)

        def go():
            path = []
            for i in range(21):
                q = i / 20.0
                path.append(((1 - q) ** 2 * (tx + 28) + 2 * (1 - q) * q * (tx + 36) + q * q * tx,
                             (1 - q) ** 2 * (ty - 210) + 2 * (1 - q) * q * (ty - 60) + q * q * (ty + 70)))
            self._ub_stroke(path, BSX_ORG_L, BSX_ORG, 0.26, 1.6)
            self._ub_stroke([(x - 24, y - 6) for x, y in path], BSX_PUR_L, BSX_PUR, 0.24, 1.0)

            def land():
                self._bsx_hit(tid, big)
                self._bsx_ring(tx, ty + 60, BSX_PUR_L, 10, 170 if big else 120, 0.45, 5, 0.3)
                self._bsx_cracks(tx, ty + 60)
                self._bsx_dust(tx, ty + 60, n=8, spread=150)

            self.root.after(130, land)

        if delay:
            self.root.after(delay, go)
        else:
            go()

    def _bsx_lift(self, tid, delay=0):
        """아래에서 위로 들어올리는 일격 — 상승 궤적 + 속도선."""
        tx, ty = self.center_of(tid)

        def go():
            self._bsx_swing((tx - 30, ty + 170), (tx + 20, ty - 200), 30, BSX_ORG_L, BSX_ORG, 0.3, 1.5)
            self._bsx_swing((tx + 22, ty + 170), (tx + 60, ty - 190), -26, BSX_PUR_L, BSX_PUR, 0.28, 1.1)
            self._bsx_rise(tid, 0.5)
            self.root.after(100, lambda: (self._bsx_hit(tid, True),
                                          self._bsx_ring(tx, ty + 50, BSX_PUR_L, 10, 150, 0.45, 5, 0.3)))

        if delay:
            self.root.after(delay, go)
        else:
            go()

    def _bsx_stab(self, src, tid, jit=1.0, ext=260, thick=1.0, dur=0.26, delay=0):
        """레바테인 찌르기 — 보라 광채 + 주황 심 + 흰 코어가 대상을 꿰뚫는다."""
        cv = self.canvas

        def go():
            sx, sy = self.center_of(src)
            tx, ty = self.center_of(tid)
            tx += random.uniform(-1, 1) * 34 * jit
            ty += random.uniform(-1, 1) * 30 * jit
            dx, dy = tx - sx, ty - sy
            ln = max(1.0, math.hypot(dx, dy))
            ux, uy = dx / ln, dy / ln
            total = ln + ext

            def mk(col, w):
                return cv.create_line(sx, sy, sx, sy, fill=col, width=w * thick, capstyle="round", tags="fx")

            glow, mid, core = mk(BSX_PUR, 18), mk(BSX_ORG, 8), mk(WHITE, 3)
            tip = cv.create_polygon(sx, sy, sx, sy, sx, sy, fill=BSX_ORG_L, outline=BSX_ORG, width=1, tags="fx")

            def up(p, e):
                head = total * min(1.0, p * 2.2)
                fade = max(0.0, (p - 0.5) / 0.5)
                tail = max(0.0, head - 250) if p < 0.5 else max(0.0, total - 250) + 250 * fade
                tail = min(tail, head)
                hx, hy = sx + ux * head, sy + uy * head
                qx, qy = sx + ux * tail, sy + uy * tail
                for it in (glow, mid, core):
                    cv.coords(it, qx, qy, hx, hy)
                cv.coords(tip, hx + ux * 22, hy + uy * 22, hx - ux * 8 - uy * 8, hy - uy * 8 + ux * 8,
                          hx - ux * 8 + uy * 8, hy - uy * 8 - ux * 8)
                for it, col in ((glow, BSX_PUR), (mid, BSX_ORG), (core, WHITE)):
                    cv.itemconfig(it, fill=lerp_color(col, BG, fade))
                cv.itemconfig(tip, state="hidden" if fade > 0.3 else "normal")

            self.add_fx([glow, mid, core, tip], dur, up)

            def hit():
                self.fx_flash(tid, BSX_ORG, "gray50")
                self.fx_particles(tid, BSX_ORG, n=10, spread=100, dur=0.45, size=3)
                self._ub_sparkle(tx, ty, n=3, spread=55, size=(6, 11), dur=0.45,
                                 cols=(BSX_ORG_L, BSX_ORG, BSX_PUR_L))
                self.shakes[tid] = 0.22
                beep([(random.randint(160, 260), 22)], self.sound)

            self.root.after(int(max(0.0, ln / total / 2.2) * dur * 1000), hit)

        if delay:
            self.root.after(delay, go)
        else:
            go()

    def _bsx_arc(self, tid, r, a0, span, tilt, main, glow, dur=0.34, wd=1.6):
        tx, ty = self.center_of(tid)
        self._ub_crescent(tx, ty, r, r * 0.6, math.radians(a0), math.radians(span), tilt,
                          main, glow, dur, wd)

    # ---------------- 스킬별 합성 ----------------
    def fx_bs_skill(self, kind, tid, src="N"):
        """스킬별 이펙트를 시작하고 피해가 들어갈 시점(ms)을 돌려준다."""
        tx, ty = self.center_of(tid)

        if kind == "bs_stomp":                       # 스킬 1 — 발차기
            self._bsx_kick(tid)
            return 230

        if kind == "bs_crush":                       # 스킬 2 — 아래로 2번 찍고 → 위로 들어올리기
            self._bsx_slam(tid, 0)
            self._bsx_slam(tid, 300)
            self._bsx_lift(tid, 640)
            return 640 + 260

        if kind == "bs_l_slash":                     # 스킬 2-레바테인 — 발차기 → 들어올리기 → 5번 찌르기
            self._bsx_kick(tid)
            self._bsx_lift(tid, 270)
            for i in range(5):
                self._bsx_stab(src, tid, jit=1.0, ext=240, thick=0.9, dur=0.26, delay=560 + i * 100)
            self.root.after(560 + 4 * 100 + 90, lambda: (self._bsx_hit(tid, True),
                                                         self._bsx_sunburst(tx, ty, (BSX_ORG, BSX_ORG_D),
                                                                            12, 20, 110, 0.4)))
            return 560 + 4 * 100 + 150

        if kind == "bs_stamp":                       # 스킬 3 — (3번 영상)
            self._bsx_flame(src, 0.95)
            sx, sy = self.center_of(src)
            self._bsx_ring(sx, sy + 40, BSX_PUR, 12, 160, 0.6, 5, 0.35)
            self._bsx_stab(src, tid, jit=0.0, ext=90, thick=1.5, dur=0.3, delay=420)
            for i, (r, a0, tilt) in enumerate(((165, 200, -0.4), (140, 20, 0.35), (185, 110, -0.1))):
                self.root.after(600 + i * 95, lambda r=r, a0=a0, tilt=tilt: (
                    self._bsx_arc(tid, r, a0, 270, tilt, "#F3E8FF", BSX_PUR, 0.32, 1.7),
                    self._bsx_dust(tx, ty + 30, n=5, spread=170),
                    self.fx_flash(tid, BSX_PUR_L, "gray25")))
            self.root.after(860, lambda: self._bsx_vortex(tid, 0.55))
            self._bsx_slam(tid, 1290, big=True)
            self.root.after(1290, lambda: self._bsx_veil(BSX_PUR, 0.5))
            return 1290 + 130 + 130

        if kind == "bs_l_execute":                   # 스킬 3-레바테인 — (4번 영상)
            self._bsx_orb(src, 0.8)
            self._bsx_flame(src, 0.8, 0.8)
            self.root.after(480, lambda: self._bsx_sunburst(tx, ty, (BSX_ORG, BSX_ORG_D, BSX_ORG_L),
                                                            16, 26, 170, 0.5))
            self.root.after(620, lambda: (self._bsx_arc(tid, 170, 200, 260, -0.35, BSX_ORG_L, BSX_ORG, 0.4, 1.8),
                                          self._bsx_hit(tid, False)))
            self.root.after(740, lambda: (self._bsx_arc(tid, 140, 25, 250, 0.3, BSX_PUR_L, BSX_PUR, 0.36, 1.4),
                                          self._bsx_hit(tid, False)))
            self.root.after(860, lambda: (self._bsx_arc(tid, 200, 130, 250, -0.2, BSX_ORG_L, BSX_ORG, 0.4, 2.0),
                                          self._bsx_hit(tid, False)))
            self.root.after(980, lambda: (self._bsx_veil(BSX_PUR, 0.45, "gray50"),
                                          self._bsx_arc(tid, 230, 205, 250, -0.3, WHITE, BSX_ORG_L, 0.5, 2.2),
                                          self._bsx_arc(tid, 180, 40, 230, 0.35, BSX_ORG_L, BSX_PUR, 0.42, 1.6)))
            self.root.after(1280, lambda: (self.fx_heavy(tid),
                                           self.fx_flash(tid, WHITE, "gray50"),
                                           self._bsx_sunburst(tx, ty, (BSX_ORG, BSX_PUR, BSX_ORG_L),
                                                              18, 30, 210, 0.6),
                                           self._bsx_hit(tid, True),
                                           self._bsx_ring(tx, ty, BSX_ORG_L, 14, 220, 0.6, 6)))
            self.shakes[tid] = 0.2
            return 1280 + 180

        if kind == "bs_l_belly":                     # 레바테인 스킬 1 — 기존 연출 유지
            self.fx_slash(tid, 1, color=BSX_PUR)
            self.fx_particles(tid, BSX_ORG, n=10, spread=90, dur=0.45, size=3)
            return 200

        self.fx_hit(tid)
        return 200

    def fx_bs_unwrap(self, src, tid):
        """{포장을 벗겨볼까} — (2번 영상) 돌진 → 금/주황 대형 초승달 난무 → X자 참격 + 흰 섬광 → 폭발."""
        tx, ty = self.center_of(tid)
        self._bsx_stab(src, tid, jit=0.0, ext=120, thick=1.4, dur=0.26)
        self.root.after(160, lambda: (self._bsx_arc(tid, 150, 210, 260, -0.4, BSX_ORG_L, BSX_ORG, 0.34, 1.6),
                                      self._bsx_hit(tid, False)))
        self.root.after(280, lambda: (self._bsx_arc(tid, 125, 20, 240, 0.35, BSX_PUR_L, BSX_PUR, 0.3, 1.3),
                                      self._bsx_hit(tid, False)))
        self.root.after(400, lambda: (self._bsx_arc(tid, 170, 120, 250, -0.15, BSX_ORG_L, BSX_ORG, 0.36, 1.8),
                                      self._bsx_hit(tid, False)))

        def cross():
            for sgn in (1, -1):
                self._ub_stroke([(tx - sgn * 190, ty - 130), (tx, ty), (tx + sgn * 190, ty + 130)],
                                BSX_ORG_L, BSX_PUR, 0.26, 1.4)

        self.root.after(540, cross)
        self.root.after(600, lambda: (self._bsx_veil("#FFFFFF", 0.25, "gray50"),
                                      self._bsx_sunburst(tx, ty, (BSX_ORG, BSX_ORG_L, BSX_PUR), 14, 22, 140, 0.45),
                                      self._bsx_hit(tid, True)))
        return 700

    def execute_bigsis(self, u, sk, plan, done):
        t = self.valid_target(u, plan, "enemy")
        if not t or t.side != "enemy":
            self.log("%s의 [%s]은 목표를 잃었다." % (u.name, sk["name"]), MUT)
            self.schedule(300, done)
            return
        dmg = sk["dmg"]
        if sk.get("wrap_cut") and u.bs_wrap > 0:
            cut = sk["wrap_cut"] * u.bs_wrap
            dmg = max(1, dmg - cut)
            self.log("[%s] 포장 %d — 피해 %d 감소 (%d→%d)." % (sk["name"], u.bs_wrap, cut, sk["dmg"], dmg), MUT)

        def after(dealt):
            self.log("%s의 [%s]! %s에게 %d 피해." % (u.name, sk["name"], t.name, dealt), BS_FIRE)
            if dealt > 0 and t.alive:
                if u.bs_leva:                               # 레바테인 — 스킬 적중시 화상 5
                    t.burn += BS_BURN
                    self.fx_number(t.id, "화상 +%d" % BS_BURN, BS_FIRE, 15, dy=-30)
                    self.log("[레바테인] %s에게 화상 %d 부여 (누적 %d)." % (t.name, BS_BURN, t.burn), BS_FIRE)
                if sk.get("extra_brk"):
                    self.ub_break_fixed(t, sk["extra_brk"], sk["name"])
                if t.alive and sk.get("speed_down"):
                    t.speed_minus = max(t.speed_minus, sk["speed_down"])
                    self.fx_number(t.id, "속도 -%d" % sk["speed_down"], BS_FIRE, 15, dy=-12)
                    self.log("[%s] %s의 다음턴 속도 -%d." % (sk["name"], t.name, sk["speed_down"]), BS_FIRE)
                if t.alive and sk.get("stun"):
                    t.stun_turns = max(t.stun_turns, 1)
                    self.fx_number(t.id, "기절!", SPC, 22, dy=-30)
                    self.log("[%s] %s 기절 — 다음 행동 불가." % (sk["name"], t.name), SPC)
            cost = sk.get("fun_cost", 0)
            if cost and u.alive and not u.bs_leva:
                u.bs_fun = max(0, u.bs_fun - cost)
                self.fx_number(u.id, "재미 %d" % u.bs_fun, SPC, 14, dy=-30)
                self.log("달아오르는 재미 -%d (남은 %d)." % (cost, u.bs_fun), SPC)
                if u.bs_fun <= 0:
                    self.bs_unwrap(u, done)
                    return
            done()

        if sk["kind"] == "bs_stamp":
            self.log("%s: '이제 갖고 놀기 질렸다!'" % u.name, BS_FIRE)
        elif sk["kind"] == "bs_l_slash":
            self.log("%s: '뜨거울거다, 좀 많이!'" % u.name, BS_FIRE)
        elif sk["kind"] == "bs_l_execute":
            self.log("%s: '불스아이군!'" % u.name, BS_FIRE)
        ms = self.fx_bs_skill(sk["kind"], t.id, u.id)
        self.schedule(ms, lambda: self.apply_damage(u, t, dmg, "heavy", after))

    def admin_equip_bigsis(self):
        unit = self.units.get("N")
        if not unit or unit.side != "ally":
            return
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
        unit.imperial_safety_round = None
        unit.aspect_id = BIGSIS_ASPECT["id"]
        unit.skills = BIGSIS_ASPECT["skills"]
        unit.max_sp = MAX_SP
        unit.sp = min(unit.sp, unit.max_sp)
        self.bs_reset(unit)
        self.log("[ADMIN] N에게 [큰누님/N] 형상을 장착했다. (이번 전투 한정)", UB_RED)
        self.fx_flash(unit.id, UB_RED, "gray50")
        beep([(220, 60), (330, 70), (440, 120)], self.sound)
        self.render()

    def admin_unequip_bigsis(self):
        unit = self.units.get("N")
        if not unit or not self.is_bigsis(unit):
            return
        self.bs_clear(unit)
        aid = self.__dict__.get("equipped", {}).get("N", "n_base")
        self.equip_aspect(aid)
        self.log("[ADMIN] 큰누님/N 장착을 해제했다.", UB_RED)
        self.render()

    def bigsis_tip_lines(self):
        return [
            "★★★ 특별해석 {거미집} 전용 형상 — 형상해석 [▶] 거미집 테마에서 얻는다",
            "기본효과: 포장",
            "   전투 시작시 포장 3 · 효과 없음, 특정 스킬을 통해 소모됨",
            "   포장이 0이 되면 [레바테인] 획득",
            "   레바테인: 자신의 공격력 +5 · 모든 스킬이 레바테인 전용 스킬로 변경",
            "   레바테인 개방시 달아오르는 재미가 제거되어 {포장을 벗겨볼까}를 사용할 수 없다",
            "패시브: 봉인된 검 [레바테인]",
            "   자신의 방어 행동이 방어 → 반격으로 변경",
            "   레바테인 상태에서 스킬이 적중하면 화상 5 부여",
            "   화상: 라운드 시작시 수치만큼 피해를 입고 전부 제거됨",
            "   전투 시작시 달아오르는 재미 2 획득 · 0이 되면 {포장을 벗겨볼까} 사용",
            "스킬 1: 짓밟기 [2포인트 소비]",
            "   지정한 대상에게 20 피해 · 포장 1당 피해 5 감소 (20→5까지)",
            "스킬 1-[레바테인]: 배때지를 갈라주지 [2포인트 소비]",
            "   지정한 대상에게 25 피해",
            "스킬 2: 고작 이거에 부셔지지 말라고! [4포인트 소비]",
            "   지정한 대상에게 45 피해 · 포장 1당 피해 5 감소 · 달아오르는 재미 -1",
            "스킬 2-[레바테인]: 칼빵 [레바테인] [4포인트 소비]",
            "   65 피해 · 15 고정 격파피해 · 다음턴 속도 감소 3",
            "스킬 3: 원한 스탬핑 [6포인트 소비]",
            "   지정한 대상에게 65 피해 · 포장 1당 피해 5 감소 (65→50까지) · 달아오르는 재미 -1",
            "스킬 3-[레바테인]: 즉결처형 [레바테인] [6포인트 소비]",
            "   100 피해 · 20 고정 격파피해 · 다음턴 속도 감소 3 · 기절 부여",
            "{포장을 벗겨볼까} [포인트 소모/획득 없음]",
            "   대상의 방어행동 무시 · 무작위 적에게 30 피해 · 포장 -1 · 이후 달아오르는 재미 2 획득",
            "방어행동: 반격",
            "   사용턴 동안 받는 피해 40% 감소 · 이후 받은 피해량의 50%만큼 반격 (처치 불가)",
            "   반격 2회 사용마다 달아오르는 재미 -1",
        ]

    # ================================================================
    # ★★★ 신탁 대행자/H (거미집 형상 — 신탁 패치)
    # ================================================================
    def is_oracle(self, unit):
        return unit.side == "ally" and unit.aspect_id == "h_oracle"

    def or_reset(self, u):
        u.or_unlock = 1
        u.or_hermes = 0
        u.or_grace = 0
        u.or_furioso = False
        u.or_used = set()
        u.or_hermes_turn = 0
        u.or_grace_round = None
        u.or_block_round = None
        u.or_turn_dmg = 0
        u.or_dmg_done = False
        u.or_iv_bonus_used = False

    def or_round_start(self, u):
        u.or_hermes_turn = 0
        u.or_turn_dmg = 0
        u.or_dmg_done = False

    def or_speed_bonus(self, u):
        if not self.is_oracle(u):
            return 0
        return {1: 0, 2: 1, 3: 1, 4: 2}.get(u.or_unlock, 0)

    def or_atk_bonus(self, u):
        return 5 if u.or_unlock >= 3 else 0

    def or_gain_hermes(self, u, n, force=False):
        """헤르메스 획득. 무기 효과는 턴당 3회, Furioso 지정 턴 · 3-2 대기 중에는 얻지 않는다."""
        if n <= 0 or u.or_furioso or not u.alive:
            return 0
        if not force:
            if u.or_block_round == self.round:
                return 0
            n = min(n, 3 - u.or_hermes_turn)
            if n <= 0:
                return 0
            u.or_hermes_turn += n
        u.or_hermes += n
        self.fx_number(u.id, "헤르메스 %d/9" % min(9, u.or_hermes), OR_GOLD, 14, dy=-12)
        self.log("[모조된 삶] 헤르메스 +%d (%d/9)." % (n, min(9, u.or_hermes)), OR_GOLD)
        if u.or_hermes >= 9:
            u.or_hermes = 0
            u.sp = max(u.sp, u.max_sp)
            u.or_furioso = True
            self.fx_flash(u.id, OR_GOLD, "gray50")
            self.fx_number(u.id, "Furioso", OR_SKY, 22, dy=-34)
            self.log("헤르메스 9 — 전부 제거 · SP %d 회복 · 스킬 3 → 3-2 [Furioso-Replica]." %
                     u.max_sp, OR_SKY)
            beep([(523, 70), (784, 80), (1046, 140)], self.sound)
        return n

    def or_grace_add(self, u, n, how):
        """가호 획득 — 로그에만 표시된다. 2 이상이면 해금 단계 상승 후 가호 초기화."""
        if u.or_unlock >= 4 or not u.alive:
            return
        u.or_grace += n
        self.log("[신탁 단말기] 지령 수행: %s — 가호 +%d (%d/2)." % (how, n, u.or_grace), OR_SKY)
        if u.or_grace >= 2:
            u.or_grace = 0
            u.or_unlock += 1
            self.fx_flash(u.id, OR_SKY, "gray50")
            self.fx_number(u.id, "해금 %s" % OR_ROMAN[u.or_unlock], OR_SKY, 20, dy=-34)
            self.log("해금 %s 단계로 상승했다. (가호 초기화)" % OR_ROMAN[u.or_unlock], OR_SKY)
            if u.or_unlock in OR_UNLOCK_LINES:
                self.log("%s: '%s'" % (u.name, OR_UNLOCK_LINES[u.or_unlock]), OR_GOLD)
            beep([(659, 60), (880, 70), (1318, 110)], self.sound)
            if u.or_unlock == 4 and u.or_hermes <= 7 and not u.or_iv_bonus_used:
                u.or_iv_bonus_used = True
                self.log("해금 IV 도달 — 헤르메스가 7 이하라 추가로 2 얻는다. (전투당 1회)", OR_GOLD)
                self.or_gain_hermes(u, 2, force=True)

    def or_mission(self, u, how):
        """지령 수행 — 처치 / 한 턴 40 이상 피해 / 공격 회피. 턴당 1회만 가호가 쌓인다."""
        if not u.alive or u.or_block_round == self.round or u.or_grace_round == self.round:
            return
        u.or_grace_round = self.round
        self.or_grace_add(u, 1, how)

    def or_on_damage(self, u, dealt):
        if u.or_block_round == self.round or u.or_dmg_done:
            return
        u.or_turn_dmg += dealt
        if u.or_turn_dmg >= 40:
            u.or_dmg_done = True
            self.or_mission(u, "한 턴에 40 이상 피해")

    def or_pick_weapon(self, u):
        """사용하지 않은 무기는 등장 확률이 3배."""
        weights = [1 if w["id"] in u.or_used else 3 for w in ORACLE_WEAPONS]
        return random.choices(ORACLE_WEAPONS, weights)[0]

    def or_weapon_dmg(self, w, dmg):
        if w["id"] == "sword":
            return dmg + 5
        if w["id"] == "scythe":
            return round(dmg * 1.3) + 10
        return dmg

    def or_weapon_after(self, u, t, w):
        if not t.alive:
            return
        if w["id"] == "rapier":
            t.speed_minus = max(t.speed_minus, 1)
            self.fx_number(t.id, "속도 -1", OR_SKY, 15, dy=-12)
        elif w["id"] == "lance":
            t.speed_minus = max(t.speed_minus, 2)
            self.fx_number(t.id, "속도 -2", OR_SKY, 15, dy=-12)
        elif w["id"] == "hammer":
            self.ub_break_fixed(t, 5, w["name"])
        elif w["id"] == "whip":
            self.ub_break_fixed(t, 10, w["name"])

    def execute_oracle(self, u, sk, plan, done):
        if sk["kind"] == "or_furioso":
            self.or_furioso_run(u, sk, plan, done)
            return
        t = self.valid_target(u, plan, "enemy")
        if not t or t.side != "enemy":
            self.schedule(300, done)
            return
        w = self.or_pick_weapon(u)
        self.log("%s: %s" % (u.name, w["line"]), OR_GOLD)
        if w["id"] not in u.or_used:                  # 사용하지 않은 무기 — 헤르메스 +1 (턴당 3회)
            u.or_used.add(w["id"])
            self.or_gain_hermes(u, 1)
            if len(u.or_used) >= len(ORACLE_WEAPONS):
                u.or_used = set()
                self.log("신탁 단말기의 무기가 한 바퀴 돌았다. (사용 기록 초기화)", MUT)
        dmg = self.or_weapon_dmg(w, sk["dmg"])
        self.fx_number(t.id, w["name"], OR_GOLD, 16, dy=-34)

        def after(dealt):
            self.log("%s의 [%s]! (%s) %s에게 %d 피해 · %s." %
                     (u.name, sk["name"], w["name"], t.name, dealt, w["eff"]), OR_GOLD)
            self.or_weapon_after(u, t, w)
            if sk["kind"] == "or_s3" and u.alive:
                self.or_grace_add(u, 1, "스킬 3")
            done()

        self.schedule(self.fx_or_skill(sk["kind"], t.id), lambda: self.apply_damage(u, t, dmg, "heavy", after))

    def or_furioso_run(self, u, sk, plan, done):
        """3-2 Furioso-Replica — 9회 적중 · 방어행동 무시 · 첫/마지막은 지정 대상 · 9번째는 낫 고정."""
        first = self.valid_target(u, plan, "enemy")
        if not first or first.side != "enemy":
            self.schedule(300, done)
            return
        self.log("%s: '격정의 마음을 모방하겠소'" % u.name, OR_GOLD)
        self.log("%s: [Furioso-Replica] — 모사된 신탁이 아홉 번 내리친다." % u.name, OR_SKY)
        self._orx_veil(OR_DEEP, 0.6)

        def hit(i):
            pool = [e for e in self.enemies() if e.alive]
            if i >= 9 or not pool:
                done()
                return
            t = first if (i in (0, 8) and first.alive) else random.choice(pool)
            w = ORACLE_BY_ID["scythe"] if i == 8 else random.choice(ORACLE_WEAPONS)
            dmg = self.or_weapon_dmg(w, sk["dmg"])
            self.fx_or_hit(t.id, w, i == 8)

            def after(dealt, t=t, w=w, i=i):
                self.log("[Furioso %d/9] %s — %s에게 %d 피해 · %s." %
                         (i + 1, w["name"], t.name, dealt, w["eff"]), OR_SKY)
                self.or_weapon_after(u, t, w)
                self.schedule(40, lambda: hit(i + 1))

            self.schedule(140, lambda: self.apply_damage(u, t, dmg, "heavy", after, skip_defense=True))

        self.schedule(520, lambda: hit(0))

    # ---------------- 이펙트 (금빛 / 하늘빛) ----------------
    def _orx_ring(self, cx, cy, col, r1=120, dur=0.4, squash=0.6):
        cv = self.canvas
        ring = cv.create_oval(cx, cy, cx, cy, outline=col, width=4, tags="fx")

        def up(p, e):
            r = 10 + (r1 - 10) * (1 - (1 - p) ** 3)
            cv.coords(ring, cx - r, cy - r * squash, cx + r, cy + r * squash)
            cv.itemconfig(ring, outline=lerp_color(col, BG, p), width=max(1, 4 * (1 - p)))

        self.add_fx([ring], dur, up)

    def _orx_veil(self, col, dur=0.5):
        cv = self.canvas
        veil = cv.create_rectangle(0, 0, WIN_W, WIN_H, fill=col, outline="", stipple="gray25", tags="fx")

        def up(p, e):
            cv.itemconfig(veil, fill=lerp_color(col, BG, p), stipple="gray25" if p < 0.5 else "gray12")

        self.add_fx([veil], dur, up)

    def _or_hit(self, tid, big=False):
        cx, cy = self.center_of(tid)
        self.fx_flash(tid, OR_GOLD, "gray50")
        self.fx_particles(tid, OR_GOLD, n=18 if big else 10, spread=130 if big else 95, dur=0.5, size=4)
        self.fx_particles(tid, OR_SKY, n=10 if big else 6, spread=110, dur=0.5, size=3)
        self._orx_ring(cx, cy, OR_GOLD_L, 130 if big else 90, 0.4)
        self._ub_sparkle(cx, cy, n=4 if big else 2, spread=80, size=(6, 12), dur=0.5,
                         cols=(OR_GOLD_L, OR_GOLD, OR_SKY))
        self.shakes[tid] = 0.4 if big else 0.22
        beep([(random.randint(260, 420), 22)], self.sound)

    def fx_or_skill(self, kind, tid):
        """스킬별 이펙트를 시작하고 피해가 들어갈 시점(ms)을 돌려준다."""
        tx, ty = self.center_of(tid)
        ra = math.radians
        if kind == "or_s1":                          # 얼어붙은 피를 휘감아 — 감겨드는 두 겹 호
            self._ub_crescent(tx, ty, 120, 72, ra(190), ra(300), -0.3, OR_GOLD_L, OR_SKY, 0.3, 1.4)
            self.root.after(110, lambda: self._ub_crescent(
                tx, ty, 92, 56, ra(20), ra(280), 0.3, OR_GOLD, OR_DEEP, 0.28, 1.1))
            self.root.after(190, lambda: self._or_hit(tid, False))
            return 290
        if kind == "or_s2":                          # 소리 없는 손뼉 → 꿰뚫기
            self._ub_stroke([(tx - 270, ty - 10), (tx - 130, ty - 4), (tx - 12, ty)], OR_GOLD_L, OR_SKY, 0.24, 1.4)
            self._ub_stroke([(tx + 270, ty + 10), (tx + 130, ty + 4), (tx + 12, ty)], OR_GOLD_L, OR_SKY, 0.24, 1.4)
            self.root.after(190, lambda: (self._orx_ring(tx, ty, OR_SKY, 150, 0.45, 0.8),
                                          self.fx_flash(tid, OR_GOLD_L, "gray50")))
            self.root.after(300, lambda: (
                self._ub_stroke([(tx, ty - 220), (tx + 8, ty), (tx, ty + 220)], OR_GOLD, OR_DEEP, 0.28, 1.7),
                self._or_hit(tid, True)))
            return 470
        if kind == "or_s3":                          # 폭포 — 위에서 쏟아지는 칼날
            for i, off in enumerate((-160, -80, 0, 80, 160)):
                self.root.after(i * 70, lambda off=off: self._ub_stroke(
                    [(tx + off, ty - 240), (tx + off * 0.9, ty - 60), (tx + off * 0.8, ty + 110)],
                    OR_GOLD_L, OR_SKY, 0.26, 1.0))
            self.root.after(380, lambda: (self._orx_veil(OR_DEEP, 0.4), self.fx_heavy(tid),
                                          self._or_hit(tid, True)))
            return 520
        self._or_hit(tid, False)
        return 200

    def fx_or_hit(self, tid, w, last=False):
        """Furioso 한 타 — 무작위 각도의 참격 + 무기 이름. 마지막(낫)은 크게."""
        x, y, w_, h = self.rect_of(tid)
        self.fx_number(tid, w["name"], OR_SKY if not last else OR_GOLD, 15 if not last else 22, dy=-34)
        self._one_slash(x, y, w_, h, random.uniform(-75, 75), OR_GOLD if last else OR_SKY)
        self.root.after(80, lambda: self._or_hit(tid, last))
        if last:
            cx, cy = self.center_of(tid)
            self._ub_crescent(cx, cy, 190, 112, math.radians(200), math.radians(250), -0.3,
                              OR_GOLD_L, OR_GOLD, 0.45, 1.8)
            self._orx_veil(OR_GOLD, 0.5)

    # ---------------- 어드민 ----------------
    def admin_equip_oracle(self):
        unit = self.units.get("H")
        if not unit or unit.side != "ally":
            return
        unit.fate_hp_spent = 0
        unit.fate_ready = False
        unit.hero_buff = False
        unit.hero_revive_used = False
        unit.hero_passive_shield_gained = 0
        unit.hero_echo_used = False
        unit.hero_echo_channel = None
        unit.aspect_id = ORACLE_ASPECT["id"]
        unit.skills = ORACLE_ASPECT["skills"]
        unit.max_sp = MAX_SP
        unit.sp = min(unit.sp, unit.max_sp)
        self.or_reset(unit)
        self.log("[ADMIN] H에게 [신탁 대행자/H] 형상을 장착했다.", UB_RED)
        self.fx_flash(unit.id, UB_RED, "gray50")
        beep([(220, 60), (330, 70), (440, 120)], self.sound)
        self.render()

    def admin_unequip_oracle(self):
        unit = self.units.get("H")
        if not unit or not self.is_oracle(unit):
            return
        aid = self.__dict__.get("equipped", {}).get("H", "h_base")
        self.equip_aspect(aid)
        self.log("[ADMIN] 신탁 대행자/H 장착을 해제했다.", UB_RED)
        self.render()

    def admin_oracle_hermes(self, n):
        unit = self.units.get("H")
        if unit and self.is_oracle(unit):
            self.or_gain_hermes(unit, n, force=True)
        self.render()

    def admin_oracle_unlock(self):
        unit = self.units.get("H")
        if unit and self.is_oracle(unit) and unit.or_unlock < 4:
            unit.or_grace = 1
            self.or_grace_add(unit, 1, "ADMIN")
        self.render()

    def oracle_tip_lines(self):
        c1, c2, c3 = OR_COSTS
        return [
            "★★★ 특별해석 {거미집} 전용 형상 — 형상해석 [▶] 거미집 테마에서 얻는다",
            "기본효과: 전투 시작시 헤르메스 · 해금 I 획득",
            "   해금 I~IV 단계별 효과 (중첩되지 않음)",
            "   I: 효과 없음 · II: 속도 최소값 +1",
            "   III: 속도 최소값 +1 · 공격력 +5 · IV: 속도 최소값 +2 · 공격력 +5",
            "   (속도 최소값은 최대값을 넘을 수 없다)",
            "패시브: 모조된 삶",
            "   사용하지 않은 무기로 스킬 사용시 헤르메스 +1 (턴당 3회) · 안 쓴 무기가 더 잘 나온다",
            "   해금 IV 도달시 헤르메스가 7 이하면 +2 (전투당 1회)",
            "   헤르메스 9: 전부 제거 · SP 6까지 회복 · 스킬 3 → 3-2",
            "   지령: 적 처치 / 한 턴에 40 이상 피해 / 공격 회피 → 가호 +1 (턴당 1회)",
            "   가호 2 이상이면 해금 단계 상승 후 가호 초기화 (가호는 로그에만 표시)",
            "신탁 단말기: 스킬 사용시마다 무기 9종 중 하나의 효과 발동",
            "   손도끼 · 스틸레토 · 바스타드 소드: 추가 효과 없음",
            "   레이피어: 속도 감소 1 · 랜스: 속도 감소 2",
            "   망치: 격파피해 +5 · 채찍: 격파피해 +10",
            "   검: 피해량 +5 · 낫: 피해량 ×1.3 후 +10",
            "스킬 1: 얼어붙은 피를 삼백삼십 휘감아 [%d포인트 소비]" % c1,
            "   지정한 대상에게 20 피해",
            "스킬 2: 소리 없이 손뼉을 쳐 즐기고, 목소리 없이 슬피 꿰뚫어 [%d포인트 소비]" % c2,
            "   지정한 대상에게 45 피해",
            "스킬 3: 날 세워 칼날을 웃거라, 낙옆향 나듯 폭포를 울거라 [%d포인트 소비]" % c3,
            "   지정한 대상에게 65 피해 · 가호 1 획득",
            "스킬 3-2: Furioso-Replica [포인트 소모/회복 없음]",
            "   방어행동 무시 · 이 턴은 지령 수행/헤르메스 획득 없음",
            "   총 9회 적중 (적중마다 35 피해 + 신탁 단말기 효과) · 모든 적을 무작위 공격",
            "   첫 타격과 마지막 타격은 지정한 대상 · 9번째 타격은 (낫) 고정",
        ]

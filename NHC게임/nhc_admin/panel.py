# -*- coding: utf-8 -*-
"""어드민 패널 (전투 중 'maki' 입력)"""
import math
import os
import random
import threading
import time
import tkinter as tk
import tkinter.font as tkfont

from nhc_data import *


class AdminMixin:
    """NHCBattle 에 섞여 들어가는 기능 묶음 (self 는 NHCBattle)."""

    def toggle_admin(self):
        if self.lobby:
            return
        if self.admin:
            self.close_admin()
            return
        self.admin = True
        self.codex_open = False
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
            u.sp = min(u.max_sp, max(u.sp, 1))
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
                if not self.is_fate_c(u) and not self.is_imperial_n(u):
                    u.sp = u.max_sp
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

    def admin_begin_kill_ally(self):
        self.admin = False
        self.admin_kill_pending = True
        self.status_msg = "처치할 아군을 선택하세요."
        self.render()

    def admin_cancel_kill_ally(self):
        self.admin_kill_pending = False
        self.status_msg = None
        self.render()

    def admin_kill_ally(self, target):
        self.log("[ADMIN] %s에게 처치 판정을 적용했다." % target.name, DMG)

        def after_kill(_dealt):
            if target.alive:
                self.log("[ADMIN] %s의 불사/부활 효과가 발동해 처치되지 않았다." %
                         target.name, HEAL)
            else:
                self.log("[ADMIN] %s을(를) 처치했다." % target.name, DMG)
            if not self.check_end():
                self.render()

        self.finalize(target, target, max(1, target.hp), "admin", after_kill, fixed=True)

    def admin_sp_max(self):
        for u in self.allies():
            if not self.is_fate_c(u) and not self.is_imperial_n(u):
                u.sp = u.max_sp
        self.log("[ADMIN] SP 회복 가능 아군의 SP를 최대로 채웠다.", SPC)
        self.render()

    def admin_item_add(self, item_id, n):
        total = self.add_item(item_id, n)
        self.log("[ADMIN] %s +%d → 보유 %d개" % (ITEMS[item_id]["name"], n, total), SPC)
        self.render()

    def admin_item_reset(self, item_id):
        self.__dict__.setdefault("inventory", {})[item_id] = 0
        self.log("[ADMIN] %s 초기화." % ITEMS[item_id]["name"], SPC)
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
        tabs = [("move", "이동"), ("item", "아이템"), ("aspect", "형상"),
                ("misc", "기타")]
        tw = 98
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

        elif self.admin_tab == "item":
            inv = self.__dict__.get("inventory", {})
            mw = (iw - gap * 3) / 4
            self.txt(ix, body_y, "아이템 지급 — 빛바랜 소망 %d개 · 작은 거울 %d개"
                     % (inv.get("faded_wish", 0), inv.get("small_mirror", 0)), 14, SPC, bold=True)
            self.txt(ix, body_y + 24, "지급한 아이템은 TAB 인벤토리와 제작소(Z)에서 확인한다.",
                     11, MUT, mono=True)
            row = [("빛바랜 소망 +1", lambda: self.admin_item_add("faded_wish", 1)),
                   ("빛바랜 소망 +5", lambda: self.admin_item_add("faded_wish", 5)),
                   ("빛바랜 소망 +15", lambda: self.admin_item_add("faded_wish", 15)),
                   ("빛바랜 소망 +50", lambda: self.admin_item_add("faded_wish", 50))]
            for i, (label, cb) in enumerate(row):
                self.abtn(ix + i * (mw + gap), body_y + 54, mw, 42, label, None, cb,
                          ITEM_TIER_COLOR[1], idx)
                idx += 1
            self.abtn(ix, body_y + 106, mw, 42, "빛바랜 소망 초기화", None,
                      lambda: self.admin_item_reset("faded_wish"), MUT, idx)
            idx += 1
            dim_row = [("희미한 소망 +1", lambda: self.admin_item_add("dim_wish", 1)),
                       ("희미한 소망 +5", lambda: self.admin_item_add("dim_wish", 5)),
                       ("희미한 소망 +20", lambda: self.admin_item_add("dim_wish", 20)),
                       ("희미한 소망 +50", lambda: self.admin_item_add("dim_wish", 50))]
            for i, (label, cb) in enumerate(dim_row):
                self.abtn(ix + i * (mw + gap), body_y + 158, mw, 42, label, None, cb,
                          ITEM_TIER_COLOR[2], idx)
                idx += 1
            self.abtn(ix, body_y + 210, mw, 42, "희미한 소망 초기화", None,
                      lambda: self.admin_item_reset("dim_wish"), MUT, idx)
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
            mw = (iw - gap * 3) / 4
            misc = [
                ("아군 완전 회복", "체력·격파체력 최대", self.admin_full_heal, HEAL),
                ("아군 SP 최대", "전원 SP %d" % MAX_SP, self.admin_sp_max, SPC),
                ("현재 적 전멸", "즉시 페이즈 클리어", self.admin_clear_wave, DMG),
                ("아군 처치", "클릭 후 아군 선택", self.admin_begin_kill_ally, DMG),
            ]
            for i, (label, sub, cb, color) in enumerate(misc):
                self.abtn(ix + i * (mw + gap), body_y, mw, 52, label, sub, cb, color, idx)
                idx += 1
            self.abtn(ix, body_y + 64, mw, 52, "환상도 전원 100%", "테스트용",
                      self.admin_ult_fill, ROSE, idx)
            idx += 1
            self.abtn(ix + mw + gap, body_y + 64, mw, 52, "환상 대기 초기화", "재사용 가능으로",
                      self.admin_ult_reset_cd, ROSE, idx)
            idx += 1
            self.abtn(ix + 2 * (mw + gap), body_y + 64, mw, 52, "관객 +5", "Orchestra/D 테스트",
                      lambda: self.admin_orch_aud(5), ORCH_GOLD, idx)
            idx += 1
            self.abtn(ix + 3 * (mw + gap), body_y + 64, mw, 52, "관객 최대 (20)", "피날레 조건 충족",
                      lambda: self.admin_orch_aud(ORCH_AUD_MAX), ORCH_GOLD, idx)
            idx += 1
            self.abtn(ix, body_y + 128, mw, 52, "관객 0", "관객 초기화",
                      lambda: self.admin_orch_aud(None), MUT, idx)
            idx += 1
            self.abtn(ix + mw + gap, body_y + 128, mw, 52, "피날레 즉시 진입", "관객 무관 · 바로 진입",
                      self.admin_orch_finale, STAR_COLOR[3], idx)
            idx += 1

        # 닫기
        self.abtn(px + pw / 2 - 100, py + ph - 46, 200, 34, "닫기 (ESC)", None,
                  self.close_admin, MUT, idx)
        self.txt(px + pw / 2, py + ph - 8, "전투 중 'maki' 를 입력하면 언제든 다시 열린다.",
                 10, MUT, mono=True, anchor="center")

    # ---------------- 어드민 ----------------
    def _admin_orch_unit(self):
        for a in self.allies():
            if self.is_orch(a):
                return a
        self.log("[ADMIN] Orchestra/D 를 장착한 아군이 없다. (로비에서 D 편성 + 형상 장착 후 전투)", MUT)
        self.render()
        return None

    def admin_orch_aud(self, n):
        """n 이 숫자면 관객 +n (최대 20), None 이면 0 으로 초기화."""
        u = self._admin_orch_unit()
        if not u:
            return
        if n is None:
            u.orch_aud = 0.0
            self.log("[ADMIN] 관객을 0으로 초기화했다.", ORCH_GOLD)
        else:
            self.orch_gain_aud(u, n)
            self.log("[ADMIN] 관객 +%g → %g/%d" % (n, u.orch_aud, ORCH_AUD_MAX), ORCH_GOLD)
        self.render()

    def admin_orch_finale(self):
        u = self._admin_orch_unit()
        if not u:
            return
        if u.orch_finale > 0:
            self.log("[ADMIN] 이미 피날레 중이다.", MUT)
        else:
            u.orch_aud = float(ORCH_AUD_MAX)
            self.orch_enter_finale(u)
            self.log("[ADMIN] 피날레에 강제 진입시켰다.", ORCH_GOLD)
        self.render()

    def admin_ult_fill(self):
        for a in self.allies():
            if a.id in ULTIMATES:
                a.ult_gauge = 100
        self.log("[ADMIN] 환상도를 100%로 채웠다.", SPC)
        self.render()

    def admin_ult_reset_cd(self):
        for a in self.allies():
            a.ult_use_round = None
        self.log("[ADMIN] 환상 재사용 대기를 초기화했다.", SPC)
        self.render()

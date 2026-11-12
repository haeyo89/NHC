# -*- coding: utf-8 -*-
"""제작소 · 비석 연출 · 아이템 아이콘"""
import math
import os
import random
import threading
import time
import tkinter as tk
import tkinter.font as tkfont

from nhc_data import *


class WorkshopMixin:
    """NHCBattle 에 섞여 들어가는 기능 묶음 (self 는 NHCBattle)."""

    def toggle_workshop(self):
        """전투 중 Z — 제작소 창 열기/닫기."""
        if self.codex_open and self.codex_page == "workshop":
            self.close_codex()
            return
        if (self.codex_open or self.admin or self.admin_kill_pending or self.modal
                or self.gacha_open or self.state == "augment_pick"):
            return
        self.codex_open = True
        self.codex_page = "workshop"
        self.codex_sel = None
        self.render()

    def render_workshop(self):
        self.buttons = []
        cv = self.canvas
        now = time.monotonic()
        if self.__dict__.get("_ws_since") is None:
            self._ws_since = now
            self._ws_ui = True
            self._ws_ui_since = now + 0.35                       # 비석이 먼저 나타나고 UI 가 뒤따라 열린다
        t = now - self._ws_since
        cv.create_rectangle(0, 0, WIN_W, WIN_H, fill="#000000", outline="", stipple="gray75", tags="ui")
        self.txt(MARGIN + 4, 22, "제작소", 30, TXT, bold=True, anchor="w")
        hint = "[Z] / [ESC] 닫기" if hasattr(self, "toggle_workshop") else "[ESC] 닫기"
        self.txt(WIN_W - MARGIN, 20, hint, 11, MUT, mono=True, anchor="ne")
        self.hbtn(WIN_W - MARGIN, 40, None, 24, "닫기", self.close_codex, MUT, anchor="ne")

        # 비석 (오른쪽)
        scx, scy = 830, 410
        flash = max(0.0, 1.0 - (now - self.__dict__.get("_ws_flash", -9.0)) / 0.9)
        if self.hover == ("wks", 1):
            flash = min(1.0, flash + 0.25)
        self.draw_stele(scx, scy, t, flash)
        self.buttons.append(dict(x=scx - 120, y=scy - 190, w=240, h=380, key=("wks", 1),
                                 cb=self.workshop_toggle_ui))
        self.txt(scx, 668, "비석을 누르면 창을 접고 펼 수 있다", 11, MUT, mono=True, anchor="center")

        # 제작 UI (비석 왼쪽 옆으로 흘러나온다)
        ui_open = self.__dict__.get("_ws_ui", True)
        p = max(0.0, min(1.0, (now - self._ws_ui_since) / 0.4))
        p = 1 - (1 - p) ** 3
        a = p if ui_open else 1.0 - p
        if a <= 0.02:
            return

        def fc(c):
            return lerp_color("#0B0A10", c, a)

        pw, ph = 560, 620
        px, py = 110 + (1 - a) * 70, 120
        cv.create_line(px + pw, py + ph / 2, scx - 84, scy, fill=fc("#4B3A92"), dash=(4, 6), tags="ui")
        cv.create_rectangle(px + 5, py + 5, px + pw + 5, py + ph + 5, fill="#05070A", outline="",
                            stipple="gray50", tags="ui")
        cv.create_rectangle(px, py, px + pw, py + ph, fill=fc(PANEL), outline=fc(SPC), width=2, tags="ui")
        cv.create_rectangle(px, py, px + pw, py + 5, fill=fc(SPC), outline="", tags="ui")
        self.txt(px + 24, py + 16, "제작", 24, fc(TXT), bold=True)
        self.txt(px + 24, py + 52, "재료를 바쳐 물건을 만든다", 11, fc(MUT), mono=True)
        cv.create_line(px + 20, py + 78, px + pw - 20, py + 78, fill=fc(BRD), tags="ui")

        inv = self.__dict__.get("inventory", {})
        rh = 124
        for i, rec in enumerate(WORKSHOP_RECIPES):
            item = ITEMS[rec["id"]]
            tc = ITEM_TIER_COLOR.get(item["tier"], MUT)
            rx, ry, rw = px + 20, py + 92 + i * (rh + 12), pw - 40
            cv.create_rectangle(rx, ry, rx + rw, ry + rh, fill=fc(PANEL2), outline=fc(BRD), tags="ui")
            cv.create_rectangle(rx + 14, ry + 14, rx + 106, ry + 106, fill=fc("#14181E"),
                                outline=fc(tc), tags="ui")
            if a > 0.8:
                self.draw_item_icon(rx + 60, ry + 58, 90, item)
            nf = self.font(20, bold=True)
            self.txt(rx + 122, ry + 12, item["name"], 20, fc(TXT), bold=True)
            self.txt(rx + 122 + nf.measure(item["name"]) + 10, ry + 18, "[%d T]" % item["tier"], 14,
                     fc(tc), mono=True, bold=True)
            self.txt(rx + 122, ry + 46, "%s  [제작 %d/%s]" % (item.get("effect", "효과: 없음"), inv.get(rec["id"], 0), rec.get("max", "∞")), 12, fc(MUT), mono=True)
            self.txt(rx + 122, ry + 72, "필요 재료", 11, fc(MUT), mono=True)
            enough = True
            my = ry + 94
            for mid, need in rec["cost"].items():
                have = inv.get(mid, 0)
                ok = have >= need
                enough = enough and ok
                mi = ITEMS[mid]
                if a > 0.8:
                    self.draw_item_icon(rx + 138, my + 10, 30, mi)
                self.txt(rx + 160, my, "%s  x%d     보유 %d" % (mi["name"], need, have), 13,
                         fc(HEAL if ok else DMG), bold=True)
                my += 22
            made = inv.get(rec["id"], 0)
            cap = rec.get("max")
            maxed = bool(cap) and made >= cap
            if maxed:
                enough = False
            bx, by, bw, bh = rx + rw - 122, ry + rh - 52, 108, 38
            hov = self.hover == ("wks", 10 + i)
            cv.create_rectangle(bx, by, bx + bw, by + bh,
                                fill=fc(PANEL2 if hov and enough else PANEL),
                                outline=fc(SPC if enough else BRD), width=2 if (hov and enough) else 1,
                                tags="ui")
            self.txt(bx + bw / 2, by + bh / 2, "제작" if enough else ("제작 완료" if maxed else "재료 부족"), 14,
                     fc(SPC if enough else MUT), bold=True, anchor="center")
            if a > 0.9:
                self.buttons.append(dict(x=bx, y=by, w=bw, h=bh, key=("wks", 10 + i),
                                         cb=(lambda r=rec["id"]: self.workshop_craft(r))))

        owned = "  ".join("%s x%d" % (ITEMS[r["id"]]["name"], inv.get(r["id"], 0))
                          for r in WORKSHOP_RECIPES)
        self.txt(px + 24, py + ph - 58, "제작품 보유: " + owned, 11, fc(MUT), mono=True)
        notice = self.__dict__.get("ws_notice", "")
        if notice:
            self.txt(px + 24, py + ph - 34, notice, 12, fc(SPC), mono=True)

    # ================================================================
    # 제작소 (제작소 패치) — 떠다니는 비석 + 옆에 뜨는 제작 UI
    # ================================================================
    def workshop_toggle_ui(self):
        self._ws_ui = not self.__dict__.get("_ws_ui", True)
        self._ws_ui_since = time.monotonic()
        self.render()

    def workshop_craft(self, rid):
        rec = next((r for r in WORKSHOP_RECIPES if r["id"] == rid), None)
        if not rec:
            return
        inv = self.__dict__.setdefault("inventory", {})
        if rec.get("max") and inv.get(rid, 0) >= rec["max"]:
            self.ws_notice = "더 이상 제작할 수 없다. (최대 %d개)" % rec["max"]
            self.render()
            return
        if any(inv.get(k, 0) < v for k, v in rec["cost"].items()):
            self.ws_notice = "재료가 부족하다."
            self.render()
            return
        for k, v in rec["cost"].items():
            inv[k] -= v
        total = self.add_item(rid, 1)
        item = ITEMS[rid]
        if rid == "worn_cloak":
            for u in self.allies():
                u.max_brk += 50
                if u.alive and not u.broken:
                    u.brk = min(u.max_brk, u.brk + 50)
            self.log("낡은 망토가 몸을 감싼다 — 모든 아군 최대 격파체력 +50.", BRKC)
        if rid == "torn_umbrella":
            self.log("헤진 우산이 펼쳐진다 — 모든 아군 공격력 +5.", DMG)
        if rid == "small_mirror":
            for u in self.allies():
                u.max_hp += 50
                if u.alive:
                    u.hp = min(u.max_hp, u.hp + 50)
            self.log("작은 거울의 기운이 번진다 — 모든 아군 최대 체력 +50.", HEAL)
        self.ws_notice = "[%s] 제작 완료!  (보유 %d개) · 인벤토리(TAB)에서 확인" % (item["name"], total)
        self._ws_flash = time.monotonic()
        self.log("제작소: [%s] 제작 완료. (보유 %d개)" % (item["name"], total),
                 ITEM_TIER_COLOR.get(item["tier"], MUT))
        beep([(660, 50), (880, 60), (1320, 120)], self.sound)
        self.render()

    def draw_stele(self, cx, cy, t, flash):
        """둥둥 떠 있는 비석 — 룬이 맥동하고 파편이 맴돈다."""
        cv = self.canvas
        bob = math.sin(t * 1.3) * 10
        x0, y0 = cx + math.sin(t * 0.7) * 3, cy + bob
        W, H = 78, 150
        glow = lerp_color("#9C8FEC", "#FFE9A8", max(0.0, min(1.0, flash)))
        k = 0.5 + 0.5 * math.sin(t * 1.3)                      # 높이가 높을수록 그림자는 작고 옅다
        sw = 96 - 22 * k
        cv.create_oval(cx - sw, cy + H + 60, cx + sw, cy + H + 76, fill="#05060A",
                       outline="", stipple="gray50", tags="ui")
        for i in range(4):                                       # 주변 기운
            r = 150 + i * 26 + 6 * math.sin(t + i)
            cv.create_oval(x0 - r, y0 - r * 1.1, x0 + r, y0 + r * 1.1,
                           outline=lerp_color("#07060D", glow, 0.10 + 0.05 * (4 - i) + 0.2 * flash),
                           width=2, tags="ui")

        top = []                                                 # 윗부분이 둥근 비석 외곽
        for j in range(9):
            ang = math.pi + math.pi * j / 8
            top.append((W * math.cos(ang), (-H + 60) + 60 * math.sin(ang)))
        outline = [(-W, H)] + top + [(W, H)]

        def pts(dx, dy):
            out = []
            for px, py in outline:
                out.extend((x0 + px + dx, y0 + py + dy))
            return out

        cv.create_polygon(*pts(16, -8), fill="#1A1D27", outline="#2C3040", width=2, tags="ui")
        cv.create_polygon(*pts(0, 0), fill="#2A2E3C", outline="#6B7090", width=2, tags="ui")
        cv.create_line(x0 - W + 3, y0 + H - 6, x0 - W + 3, y0 - H + 62, fill="#4A5070", width=2, tags="ui")
        for crack in (((-20, -60), (-8, -30), (-18, -5), (-4, 30)),
                      ((30, 20), (18, 52), (26, 80)), ((-40, 70), (-26, 92))):
            flat = []
            for px, py in crack:
                flat.extend((x0 + px, y0 + py))
            cv.create_line(*flat, fill="#12141C", width=3, tags="ui")
            cv.create_line(*flat, fill=lerp_color("#2A2E3C", glow, 0.35 + 0.3 * flash), width=1, tags="ui")

        gl = self.__dict__.get("_stele_glyphs")                 # 룬 문양 (고정 시드)
        if gl is None:
            rnd = random.Random(11)
            gl = []
            for _ in range(6):
                segs = []
                for _s in range(3):
                    segs.append((rnd.uniform(-12, 12), rnd.uniform(-12, 12),
                                 rnd.uniform(-12, 12), rnd.uniform(-12, 12)))
                gl.append(segs)
            self._stele_glyphs = gl
        for i, segs in enumerate(gl):
            gy = y0 - 62 + i * 30
            al = min(1.0, 0.3 + 0.45 * (0.5 + 0.5 * math.sin(t * 1.6 + i * 0.9)) + 0.5 * flash)
            for sx0, sy0, sx1, sy1 in segs:
                cv.create_line(x0 + sx0, gy + sy0 * 0.8, x0 + sx1, gy + sy1 * 0.8,
                               fill=lerp_color("#2A2E3C", glow, al), width=2, capstyle="round", tags="ui")
        gem_r = 9 + 2 * math.sin(t * 2.2)                        # 윗부분의 눈
        cv.create_oval(x0 - gem_r, y0 - H + 40 - gem_r, x0 + gem_r, y0 - H + 40 + gem_r,
                       fill=lerp_color("#2A2E3C", glow, 0.6 + 0.3 * flash), outline="#6B7090",
                       width=2, tags="ui")

        rnd = random.Random(5)                                   # 맴도는 파편
        for i in range(7):
            a0 = rnd.uniform(0, math.tau)
            rx = rnd.uniform(105, 140)
            ry = rnd.uniform(40, 80)
            spd = rnd.uniform(0.25, 0.5) * rnd.choice((-1, 1))
            sz = rnd.uniform(6, 12)
            rot = t * rnd.uniform(-1, 1) + a0
            ang = a0 + t * spd
            fx = x0 + math.cos(ang) * rx
            fy = y0 + math.sin(ang) * ry * 0.7 + math.sin(t * 1.3 + i) * 6
            q = []
            for dxy in ((0, -1.4), (1, 0.2), (0.4, 1.2), (-1, 0.3)):
                q.extend((fx + (dxy[0] * math.cos(rot) - dxy[1] * math.sin(rot)) * sz,
                          fy + (dxy[0] * math.sin(rot) + dxy[1] * math.cos(rot)) * sz))
            cv.create_polygon(*q, fill="#3A3F52", outline="#6B7090", width=1, tags="ui")

        for i in range(12):                                      # 떠오르는 빛 입자
            qq = (t * 0.25 + i / 12.0) % 1.0
            mx = x0 + math.sin(i * 2.1 + t) * 70
            my = y0 + H - qq * (2 * H + 40)
            s = 2.2
            cv.create_oval(mx - s, my - s, mx + s, my + s,
                           fill=lerp_color("#07060D", glow, (1 - qq) * 0.8), outline="", tags="ui")

    def lobby_workshop(self):
        self.codex_open = True
        self.codex_page = "workshop"
        self.render()

    def draw_item_icon(self, cx, cy, size, item):
        """빛이 나지 않는, 가루처럼 부서진 별 모양 아이콘."""
        if item.get("icon") == "mirror":
            self.draw_mirror_icon(cx, cy, size, item)
            return
        if item.get("icon") == "umbrella":
            self.draw_umbrella_icon(cx, cy, size, item)
            return
        if item.get("icon") == "cloak":
            self.draw_cloak_icon(cx, cy, size, item)
            return
        cv = self.canvas
        col = ITEM_TIER_COLOR.get(item["tier"], MUT)
        dim = lerp_color(PANEL, col, 0.55)
        r = size * 0.36
        pts = []
        for k in range(10):
            a = -math.pi / 2 + math.pi * k / 5
            rr = r if k % 2 == 0 else r * 0.45
            pts.extend((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
        cv.create_polygon(*pts, fill="", outline=dim, width=2, tags="ui")
        rnd = random.Random(sum(ord(c) for c in item["name"]))
        for _ in range(14):                       # 흩어진 가루
            a = rnd.random() * math.tau
            d = rnd.uniform(0.1, 0.5) * size
            s = rnd.uniform(0.8, 2.3) * (size / 70.0)
            px, py = cx + math.cos(a) * d, cy + math.sin(a) * d
            cv.create_oval(px - s, py - s, px + s, py + s,
                           fill=lerp_color(PANEL, col, rnd.uniform(0.3, 0.7)),
                           outline="", tags="ui")

    def draw_mirror_icon(self, cx, cy, size, item):
        """휴대용 콤팩트 거울 — 둥근 케이스, 거울면, 힌지와 여는 홈."""
        cv = self.canvas
        col = ITEM_TIER_COLOR.get(item["tier"], MUT)
        r = size * 0.32
        case = lerp_color(PANEL, col, 0.45)
        rim = lerp_color(PANEL, col, 0.95)
        lw = max(2, size / 28)
        cv.create_rectangle(cx - r * 0.3, cy - r - size * 0.07, cx + r * 0.3, cy - r + 2,
                            fill=rim, outline="", tags="ui")               # 힌지
        cv.create_oval(cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4,
                       fill=case, outline=rim, width=lw, tags="ui")        # 케이스
        cv.create_oval(cx - r + 3, cy - r + 3, cx + r - 3, cy + r - 3,
                       fill=lerp_color(PANEL, "#7FC8F8", 0.35),
                       outline=lerp_color(PANEL, col, 0.7), width=lw, tags="ui")  # 거울면
        cv.create_rectangle(cx - r * 0.22, cy + r + 1, cx + r * 0.22, cy + r + size * 0.06,
                            fill=rim, outline="", tags="ui")               # 여는 홈
        gl = lerp_color(PANEL, WHITE, 0.75)
        cv.create_line(cx - r * 0.55, cy - r * 0.25, cx - r * 0.2, cy - r * 0.62,
                       fill=gl, width=lw, capstyle="round", tags="ui")     # 반짝임
        cv.create_line(cx - r * 0.62, cy + r * 0.05, cx - r * 0.5, cy - r * 0.08,
                       fill=gl, width=lw, capstyle="round", tags="ui")

    def draw_cloak_icon(self, cx, cy, size, item):
        """낡은 망토 — 해진 밑단과 접힌 주름, 목에 건 걸쇠."""
        cv = self.canvas
        col = ITEM_TIER_COLOR.get(item["tier"], MUT)
        cloth = lerp_color(PANEL, col, 0.42)
        rim = lerp_color(PANEL, col, 0.9)
        lw = max(1, size / 34)
        w = size * 0.36
        top, bot = cy - size * 0.34, cy + size * 0.30
        pts = [cx - w * 0.38, top, cx + w * 0.38, top,
               cx + w * 0.60, top + size * 0.10, cx + w, bot - size * 0.04]
        hem = (0.00, 0.06, 0.01, 0.05, 0.02, 0.07, 0.00)     # 해진 밑단 (오른쪽 → 왼쪽)
        for k, d in enumerate(hem):
            pts.extend((cx + w - 2 * w * (k + 0.5) / len(hem), bot + size * d))
        pts.extend((cx - w, bot - size * 0.04, cx - w * 0.60, top + size * 0.10))
        cv.create_polygon(*pts, fill=cloth, outline=rim, width=lw, tags="ui")
        for k in (-2, -1, 1, 2):                             # 주름
            cv.create_line(cx + k * w * 0.12, top + size * 0.10, cx + k * w * 0.42, bot,
                           fill=rim, width=lw, tags="ui")
        cv.create_polygon(cx + w * 0.30, cy + size * 0.02, cx + w * 0.52, cy - size * 0.04,
                          cx + w * 0.58, cy + size * 0.12, cx + w * 0.38, cy + size * 0.16,
                          fill=PANEL, outline=rim, width=lw, tags="ui")      # 찢어진 구멍
        cv.create_oval(cx - size * 0.05, top - size * 0.01, cx + size * 0.05, top + size * 0.09,
                       fill=lerp_color(PANEL, SPC, 0.55), outline=rim, width=lw, tags="ui")  # 걸쇠

    def draw_umbrella_icon(self, cx, cy, size, item):
        """헤진 우산 — 해진 가장자리와 찢긴 구멍이 있는 낡은 우산."""
        cv = self.canvas
        col = ITEM_TIER_COLOR.get(item["tier"], MUT)
        cloth = lerp_color(PANEL, col, 0.42)
        rim = lerp_color(PANEL, col, 0.9)
        lw = max(1, size / 34)
        R = size * 0.40
        by = cy - size * 0.02                       # 캐노피 아랫선
        top_y = by - R * 0.85
        pts = []
        for k in range(13):                         # 둥근 윗부분
            a = math.pi + math.pi * k / 12
            pts.extend((cx + R * math.cos(a), by + R * 0.85 * math.sin(a)))
        drop = (0.00, 0.07, 0.02, 0.09, 0.01, 0.06, 0.03)   # 해진 아랫단 (오른쪽 → 왼쪽)
        for k, d in enumerate(drop):
            pts.extend((cx + R - 2 * R * (k + 0.5) / len(drop), by + size * d))
        cv.create_polygon(*pts, fill=cloth, outline=rim, width=lw, tags="ui")
        for k in range(1, 4):                       # 살
            fx = cx - R + 2 * R * k / 4
            cv.create_line(cx, top_y, fx, by + size * 0.02, fill=rim, width=lw, tags="ui")
        hx, hy = cx - R * 0.45, by - R * 0.42       # 찢어진 구멍
        cv.create_polygon(hx, hy, hx + R * 0.22, hy - R * 0.1, hx + R * 0.3, hy + R * 0.2,
                          hx + R * 0.08, hy + R * 0.28, fill=PANEL, outline=rim, width=lw, tags="ui")
        cv.create_line(cx, by, cx, cy + size * 0.30, fill=rim, width=max(2, size / 24),
                       capstyle="round", tags="ui")                      # 손잡이 대
        hook = [cx, cy + size * 0.30, cx + size * 0.03, cy + size * 0.37, cx + size * 0.10, cy + size * 0.39,
                cx + size * 0.15, cy + size * 0.34]
        cv.create_line(*hook, fill=rim, width=max(2, size / 24), smooth=True,
                       capstyle="round", tags="ui")                      # 갈고리 손잡이

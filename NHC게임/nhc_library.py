# -*- coding: utf-8 -*-
"""서재 — 전투효과/형상/등장인물 도감, 스토리 스크롤"""
import math
import os
import random
import threading
import time
import tkinter as tk
import tkinter.font as tkfont

from nhc_data import *


class LibraryMixin:
    """NHCBattle 에 섞여 들어가는 기능 묶음 (self 는 NHCBattle)."""

    # ================================================================
    # 전투효과 도감 — F 키로 열고 닫는다. 칩에 마우스를 올리면 설명, 클릭하면 아래에 고정.
    # ================================================================
    def toggle_codex(self):
        if self.codex_open:
            self.close_codex()
            return
        if (self.admin or self.admin_kill_pending or self.modal or self.gacha_open
                or self.state == "augment_pick"):
            return
        self.codex_open = True
        self.codex_page = "menu"
        self.codex_sel = None
        self.render()

    def close_codex(self):
        self.codex_open = False
        self.render()

    def select_effect(self, idx):
        self.codex_sel = None if self.codex_sel == idx else idx
        self.render()

    def effect_holders(self, eid):
        """지금 이 효과가 걸려 있는 유닛 목록."""
        checks = {
            "guard": lambda u: u.status == "guard",
            "evade": lambda u: u.status == "evade",
            "shield": lambda u: u.shield > 0,
            "focus": lambda u: bool(u.focused),
            "undying": lambda u: u.immortal_turns > 0,
            "broken": lambda u: u.broken,
            "curse": lambda u: u.curse_turns > 0,
            "stun": lambda u: u.stun_turns > 0,
            "fate": lambda u: u.fate_turns > 0,
            "speed_penalty": lambda u: u.speed_penalty > 0,
            "speed_minus": lambda u: u.speed_minus > 0,
            "speed_fix": lambda u: u.speed_fix,
            "bloom": lambda u: u.bloom_turns > 0,
            "paint": lambda u: u.paint > 0,
            "fun": lambda u: u.fun_turns > 0,
            "danger": lambda u: u.danger_turns > 0,
            "necessity": lambda u: self.is_fate_c(u) and u.fate_ready,
            "hero": lambda u: self.is_hero_h(u) and u.hero_buff,
            "echo": lambda u: self.is_hero_h(u) and bool(u.hero_echo_channel),
            "prayer": lambda u: (self.is_imperial_n(u) and not u.imperial_princess
                                 and u.imperial_prayer > 0),
            "guardian": lambda u: (self.is_imperial_n(u)
                                   and u.imperial_guardian_round == self.round),
            "princess": lambda u: self.is_imperial_n(u) and u.imperial_princess,
        }
        checks.update({
            "w_foresight": lambda u: self.is_underboss(u) and u.ub_overheat < 0,
            "w_ammo": lambda u: self.is_underboss(u) and u.ub_ammo > 0,
            "w_overheat": lambda u: self.is_underboss(u) and u.ub_overheat >= 0,
            "w_masterpiece": lambda u: u.ma_masterpiece,
            "w_melody": lambda u: u.ma_melody,
            "w_view": lambda u: self.is_maestro(u),
            "w_material": lambda u: self.is_maestro(u),
            "w_leva": lambda u: self.is_bigsis(u) and u.bs_leva,
            "w_counter": lambda u: u.status == "counter",
            "w_wrap": lambda u: self.is_bigsis(u) and u.bs_wrap > 0,
            "w_fun": lambda u: self.is_bigsis(u) and not u.bs_leva and u.bs_fun > 0,
            "w_rib": lambda u: u.rib_turns > 0,
            "w_burn": lambda u: u.burn > 0,
            "w_unlock": lambda u: self.is_oracle(u),
            "w_hermes": lambda u: self.is_oracle(u) and u.or_hermes > 0,
            "w_grace": lambda u: self.is_oracle(u) and u.or_grace > 0,
        })
        fn = checks.get(eid)
        if not fn:
            return []
        return [u for u in self.units.values() if u.alive and fn(u)]

    def draw_effect_tip(self, e):
        c = e["color"]
        title = e["name"]
        lines = [e["scope"], ""] + e["desc"].split(" / ")
        holders = self.effect_holders(e["id"])
        lines.append("")
        lines.append("현재 적용 중: " + (", ".join(u.name for u in holders) if holders else "없음"))
        tf, lf = self.font(15, bold=True), self.font(11, mono=True)
        lines = self.wrap_lines(lines, lf, 480)
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
        for i, l in enumerate(lines):
            color = c if i == 0 else (HEAL if l.startswith("현재 적용 중") and holders else MUT)
            self.txt(bx + 12, ty, l, 11, color, mono=True)
            ty += lh

    def codex_back(self):
        key = self.codex_page.rsplit("_", 1)[-1]
        self.codex_page = ("menu_" + key) if key in THEMES else "menu"
        self.codex_sel = None
        self.render()

    def codex_esc(self):
        if self.codex_page == "workshop":
            self.close_codex()
        elif self.codex_page == "char":
            self.codex_page = "char_select"
            self.render()
        elif self.codex_page not in MENU_PAGES:
            self.codex_back()
        else:
            self.close_codex()

    def codex_flip(self, page):
        self.codex_page = page
        self.codex_sel = None
        self.render()

    def codex_goto(self, page):
        self.codex_page = page
        self.codex_sel = None
        if page == "aspect":
            self.gacha_notice = ""
        self.render()

    def render_codex(self):
        if not self.codex_open:
            return
        key = self.codex_page.rsplit("_", 1)[-1]
        th = key if key in THEMES else None
        if self.codex_page == "effect" or (th and self.codex_page.startswith("effect_")):
            self.render_effect_codex(th)
        elif self.codex_page == "aspect" or (th and self.codex_page.startswith("aspect_")):
            self.render_aspect_codex(th)
        elif self.codex_page == "char_select":
            self.render_char_select()
        elif self.codex_page == "char":
            self.render_char_page()
        elif self.codex_page == "workshop":
            self.render_workshop()
        elif self.codex_page in MENU_PAGES and self.codex_page != "menu":
            self.render_library_menu(self.codex_page[5:])
        else:
            self.render_library_menu()

    def render_library_menu(self, th=None):
        web = bool(th)
        tdata = THEMES.get(th)
        n_pages = len(MENU_PAGES)
        cur = MENU_PAGES.index("menu_" + th) if th else 0
        self.buttons = []
        self.canvas.create_rectangle(0, 0, WIN_W, WIN_H, fill="#000000", outline="",
                                     stipple="gray75", tags="ui")
        pw, ph = 800, 330
        px, py = (WIN_W - pw) / 2, 250
        self.canvas.create_rectangle(px + 5, py + 5, px + pw + 5, py + ph + 5,
                                     fill="#05070A", outline="", stipple="gray50", tags="ui")
        mcol = tdata["color"] if web else SPC
        self.canvas.create_rectangle(px, py, px + pw, py + ph, fill=PANEL, outline=mcol,
                                     width=2, tags="ui")
        self.canvas.create_rectangle(px, py, px + pw, py + 5, fill=mcol, outline="", tags="ui")
        self.txt(px + 24, py + 16, "서재", 30, TXT, bold=True)
        if web:
            self.txt(px + 108, py + 26, "{%s} 테마" % tdata["label"], 16, mcol, bold=True)
        self.txt(px + 24, py + 62, "열람할 도감을 고르세요  (%d / %d)" % (cur + 1, n_pages),
                 12, MUT, mono=True)
        self.txt(px + pw - 24, py + 24, "[F] / [ESC] 닫기  ·  [← →] 테마", 11, MUT, mono=True, anchor="ne")
        for ax, label, ok, target, idx in (
                (px - 50, "◀", cur > 0, MENU_PAGES[max(cur - 1, 0)], 20),
                (px + pw + 10, "▶", cur < n_pages - 1, MENU_PAGES[min(cur + 1, n_pages - 1)], 21)):
            ahov = ok and self.hover == ("lib", idx)
            ay = py + ph / 2 - 40
            self.canvas.create_rectangle(ax, ay, ax + 40, ay + 80, fill=PANEL2 if ahov else PANEL,
                                         outline=mcol if ok else BRD, width=2 if ahov else 1, tags="ui")
            self.txt(ax + 20, ay + 40, label, 20, mcol if ok else BRD, bold=True, anchor="center")
            self.buttons.append(dict(x=ax, y=ay, w=40, h=80, key=("lib", idx),
                                     cb=(lambda t=target: self.codex_flip(t)) if ok else (lambda: None)))
        self.canvas.create_line(px + 24, py + 84, px + pw - 24, py + 84, fill=BRD, tags="ui")

        n_entries = 2 if web else 3
        bw, bh, gap = (pw - 48 - 16 * (n_entries - 1)) / n_entries, 190, 16
        by = py + 104
        entries = [
            ("전투효과 도감", "버프 · 디버프 · 형상 고유 효과 %d종" % len(EFFECTS), BRKC, "effect"),
            ("형상 도감", "보유 %d/%d · 클릭해 장착" % (
                sum(1 for a in ASPECTS if a["id"] in self.owned_aspects), len(ASPECTS)),
             SHLD, "aspect"),
            ("등장인물 도감", "N · H · C  컨셉 아트와 설명", ROSE, "char_select"),
        ]
        if web:
            entries = [
                ("%s 전투효과 도감" % tdata["label"],
                 "{%s} 전용 버프 · 디버프 · 수치 %d종" % (tdata["label"], len(tdata["effects"])) if tdata["effects"]
                 else "아직 등록된 효과가 없다 (임시)", mcol, "effect_" + th),
                ("%s 형상 도감" % tdata["label"], "보유 %d/%d · 클릭해 장착" % (
                    sum(1 for a in tdata["aspects"] if a["id"] in self.owned_aspects), len(tdata["aspects"]))
                 if tdata["aspects"] else "아직 등록된 형상이 없다 (임시)", mcol, "aspect_" + th),
            ]
        for i, (name, sub, color, page) in enumerate(entries):
            bx = px + 24 + i * (bw + gap)
            hov = self.hover == ("lib", i)
            self.canvas.create_rectangle(bx, by, bx + bw, by + bh,
                                         fill=PANEL2 if hov else PANEL, outline=color,
                                         width=3 if hov else 2, tags="ui")
            self.canvas.create_rectangle(bx, by, bx + bw, by + 6, fill=color, outline="",
                                         tags="ui")
            self.txt(bx + bw / 2, by + bh / 2 - 12, name, 22, color, bold=True, anchor="center")
            self.txt(bx + bw / 2, by + bh / 2 + 24, sub, 11, MUT, mono=True, anchor="center")
            self.buttons.append(dict(x=bx, y=by, w=bw, h=bh, key=("lib", i),
                                     cb=(lambda p=page: self.codex_goto(p))))

    def render_aspect_codex(self, th=None):
        web = bool(th)
        lst = THEMES[th]["aspects"] if web else ASPECTS
        pcol = THEMES[th]["color"] if web else SHLD
        self.buttons = []
        self.canvas.create_rectangle(0, 0, WIN_W, WIN_H, fill="#000000", outline="",
                                     stipple="gray75", tags="ui")
        pw, ph = 900, 440
        px, py = (WIN_W - pw) / 2, 130
        self.canvas.create_rectangle(px + 5, py + 5, px + pw + 5, py + ph + 5,
                                     fill="#05070A", outline="", stipple="gray50", tags="ui")
        self.canvas.create_rectangle(px, py, px + pw, py + ph, fill=PANEL, outline=pcol,
                                     width=2, tags="ui")
        self.canvas.create_rectangle(px, py, px + pw, py + 5, fill=pcol, outline="", tags="ui")
        ix, iw = px + 24, pw - 48

        self.txt(ix, py + 14, "%s 형상 도감" % THEMES[th]["label"] if web else "형상 도감", 28, TXT, bold=True)
        self.txt(ix + (290 if web else 170), py + 28, "보유 형상을 클릭해 장착 · 마우스를 올리면 스킬 확인", 12, MUT,
                 mono=True)
        self.txt(px + pw - 24, py + 24, "[F] 닫기 · [ESC] 서재로", 11, MUT, mono=True, anchor="ne")
        self.canvas.create_line(ix, py + 60, ix + iw, py + 60, fill=BRD, tags="ui")

        per_row, gap, ch = 5, 8, 64
        cw = (iw - (per_row - 1) * gap) / per_row
        y0 = py + 72
        for i, a in enumerate(lst):
            dx = ix + (i % per_row) * (cw + gap)
            dy = y0 + (i // per_row) * (ch + gap)
            owned = a["id"] in self.owned_aspects
            c = STAR_COLOR.get(a["star"], TXT)
            hov = self.hover == ("adx", i)
            self.canvas.create_rectangle(dx, dy, dx + cw, dy + ch,
                                         fill=PANEL2 if hov else PANEL,
                                         outline=c if owned else BRD,
                                         width=2 if (hov or a["star"] >= 2 and owned) else 1,
                                         tags="ui")
            self.txt(dx + cw / 2, dy + 13, "★" * a["star"], 11, c if owned else MUT,
                     bold=True, anchor="center")
            self.txt(dx + cw / 2, dy + 31, a["title"], 13, TXT if owned else MUT,
                     bold=True, anchor="center")
            unit = self.roster.get(a["char"])
            equipped = bool(unit and unit.aspect_id == a["id"])
            status = "장착 중" if equipped else ("클릭해 장착" if owned else "미보유")
            self.txt(dx + cw / 2, dy + 50, status, 10, HEAL if equipped else MUT,
                     mono=True, anchor="center")
            cb = (lambda aid=a["id"]: self.equip_aspect(aid)) if owned else (lambda: None)
            self.buttons.append(dict(x=dx, y=dy, w=cw, h=ch, key=("adx", i), cb=cb))

        if not lst:
            self.txt(ix + iw / 2, y0 + 60, "이 테마 전용 형상은 아직 없다. (임시)", 14, MUT, anchor="center")
        rows = (len(lst) + per_row - 1) // per_row
        sy = y0 + rows * (ch + gap) + 6
        parts = []
        for cid in ("N", "H", "C"):
            unit = self.roster.get(cid)
            asp = self.find_aspect(unit.aspect_id) if unit else None
            parts.append("%s: %s" % (cid, asp["title"] if asp else "-"))
        self.txt(ix, sy, "장착 중 — " + "  ·  ".join(parts), 12, TXT, mono=True)
        if self.gacha_notice:
            self.txt(ix, sy + 24, self.gacha_notice, 11, SPC, mono=True)

        bx = px + pw / 2 - 70
        self.canvas.create_rectangle(bx, py + ph - 44, bx + 140, py + ph - 10,
                                     fill=PANEL2 if self.hover == ("adx", -1) else PANEL,
                                     outline=MUT, tags="ui")
        self.txt(bx + 70, py + ph - 27, "← 서재로", 12, MUT, mono=True, anchor="center")
        self.buttons.append(dict(x=bx, y=py + ph - 44, w=140, h=34, key=("adx", -1),
                                 cb=self.codex_back))

        h = self.hover
        if isinstance(h, tuple) and h[0] == "adx" and 0 <= h[1] < len(lst):
            self.draw_aspect_tip(lst[h[1]])

    def codex_open_char(self, cid):
        self.codex_char = cid
        self.codex_char_page = 0
        self.codex_img_tab = 0
        self.codex_scroll = 0
        self.codex_page = "char"
        self.render()

    def codex_set_tab(self, k):
        self.codex_img_tab = k
        self.codex_scroll = 0
        self.render()

    def codex_set_char_page(self, p):
        self.codex_char_page = p
        self.codex_img_tab = 0
        self.codex_scroll = 0
        self.render()

    # ---- 스토리 스크롤 ----
    def char_texts(self, data, page):
        """(짧은 설명, 스토리). 'story' 키가 있으면 그것을, 2페이지는 desc 의 첫 빈 줄 뒤를 스토리로 쓴다."""
        desc = data.get("desc", "")
        if "story" in data:
            return desc, data["story"] or ""
        if page == 1:
            head, sep, tail = desc.partition("\n\n")
            if sep and tail.strip():
                return head, tail
        return desc, ""

    def wrap_story(self, text, font, maxw):
        out = []
        for para in text.split("\n"):
            if not para.strip():
                out.append("")
                continue
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

    def char_key(self, ev):
        """등장인물 페이지에서 ← → 로 1페이지/2페이지 전환."""
        if not (self.codex_open and self.codex_page == "char"):
            return False
        c = next((x for x in CHARACTERS if x["id"] == getattr(self, "codex_char", "N")), None)
        if not c or not c.get("special"):
            return False
        if ev.keysym == "Left":
            self.codex_set_char_page(0)
        elif ev.keysym == "Right":
            self.codex_set_char_page(1)
        else:
            return False
        return True

    def story_active(self):
        return bool(self.codex_open and self.codex_page == "char" and self.__dict__.get("_story"))

    def story_scroll_to(self, n):
        st = self._story
        mx = max(0, st["total"] - st["vis"])
        self.codex_scroll = max(0, min(mx, int(n)))
        self.render()

    def story_scroll_by(self, d):
        if self.story_active():
            self.story_scroll_to(getattr(self, "codex_scroll", 0) + d)

    def on_wheel(self, ev):
        if not self.story_active():
            return
        num = getattr(ev, "num", None)
        if num == 4:
            step = -3
        elif num == 5:
            step = 3
        else:
            d = getattr(ev, "delta", 0)
            if not d:
                return
            step = -3 if d > 0 else 3
        self.story_scroll_by(step)

    def story_key(self, ev):
        if not self.story_active():
            return False
        st = self._story
        page = max(1, st["vis"] - 2)
        cur = getattr(self, "codex_scroll", 0)
        k = ev.keysym
        if k == "Up":
            self.story_scroll_to(cur - 1)
        elif k == "Down":
            self.story_scroll_to(cur + 1)
        elif k == "Prior":
            self.story_scroll_to(cur - page)
        elif k == "Next":
            self.story_scroll_to(cur + page)
        elif k == "Home":
            self.story_scroll_to(0)
        elif k == "End":
            self.story_scroll_to(10 ** 9)
        else:
            return False
        return True

    def story_thumb_press(self):
        self._sb_drag = dict(y0=self.mouse[1], s0=getattr(self, "codex_scroll", 0))

    def story_track_click(self):
        st = self.__dict__.get("_story")
        if not st:
            return
        mx = st["total"] - st["vis"]
        span = st["track_h"] - st["thumb_h"]
        if mx <= 0 or span <= 0:
            return
        frac = (self.mouse[1] - st["track_y"] - st["thumb_h"] / 2.0) / span
        self.story_scroll_to(round(frac * mx))

    def story_drag(self, ev):
        d = self.__dict__.get("_sb_drag")
        st = self.__dict__.get("_story")
        if not d or not st:
            return
        mx = st["total"] - st["vis"]
        span = st["track_h"] - st["thumb_h"]
        if mx <= 0 or span <= 0:
            return
        y = (ev.y - getattr(self.canvas, "oy", 0.0)) / getattr(self.canvas, "s", 1.0)
        self.story_scroll_to(round(d["s0"] + (y - d["y0"]) / span * mx))

    def render_story_panel(self, data, text, accent, x, y, w, h):
        self.canvas.create_rectangle(x, y, x + w, y + h, fill=PANEL2, outline=BRD, tags="ui")
        self.txt(x + 18, y + 12, "스토리", 15, accent, bold=True)
        self.txt(x + 92, y + 15, data.get("title", ""), 12, MUT, mono=True)
        self.canvas.create_line(x + 18, y + 42, x + w - 18, y + 42, fill=BRD, tags="ui")

        lf = self.font(15)
        sbw = 12
        left, top = x + 24, y + 56
        maxw = w - 48 - sbw - 12
        view_h = h - 56 - 22
        lh = lf.metrics("linespace") + 9
        vis = max(1, int(view_h // lh))
        key = (hash(text), int(maxw))
        cache = self.__dict__.get("_story_wrap")
        if not cache or cache[0] != key:
            cache = (key, self.wrap_story(text, lf, maxw))
            self._story_wrap = cache
        lines = cache[1]
        total = len(lines)
        mx = max(0, total - vis)
        self.codex_scroll = max(0, min(mx, int(getattr(self, "codex_scroll", 0))))
        s0 = self.codex_scroll
        for i, line in enumerate(lines[s0:s0 + vis]):
            if line:
                self.txt(left, top + i * lh, line, 15, TXT)

        track_x, track_y, track_h = x + w - 18 - sbw, top, vis * lh
        thumb_h = track_h
        if mx > 0:
            thumb_h = max(32.0, track_h * vis / float(total))
            thumb_y = track_y + (track_h - thumb_h) * (s0 / float(mx))
            self.canvas.create_rectangle(track_x, track_y, track_x + sbw, track_y + track_h,
                                         fill=PANEL, outline=BRD, tags="ui")
            self.canvas.create_rectangle(track_x + 1, thumb_y, track_x + sbw - 1, thumb_y + thumb_h,
                                         fill=accent, outline="", tags="ui")
            self.buttons.append(dict(x=track_x, y=thumb_y, w=sbw, h=thumb_h, key=("sbt", 0),
                                     cb=self.story_thumb_press))
            self.buttons.append(dict(x=track_x, y=track_y, w=sbw, h=track_h, key=("sbt", 1),
                                     cb=self.story_track_click))
        self._story = dict(total=total, vis=vis, track_y=track_y, track_h=track_h,
                           thumb_h=thumb_h)
        self.txt(x + w - 18, y + 15, "%d–%d / %d줄" % (s0 + 1, min(total, s0 + vis), total),
                 11, MUT, mono=True, anchor="ne")
        if mx > 0:
            self.txt(x + w / 2, y + h - 11, "마우스 휠 · ↑↓ · PageUp/PageDown · 스크롤바 드래그",
                     10, MUT, mono=True, anchor="center")

    def codex_to_char_select(self):
        self.codex_page = "char_select"
        self.render()

    def _load_fit(self, p):
        """이미지를 표시 상자(CHAR_IMG_BOX)에 꽉 차게 맞춘다.
        Pillow 가 있으면 부드럽게 리사이즈하고, 없으면 tk 의 정수 배율(zoom/subsample)로 최대한 맞춘다."""
        box = int(round(CHAR_IMG_BOX * self.canvas.s))
        try:
            from PIL import Image, ImageTk
            im = Image.open(p).convert("RGBA")
            r = box / float(max(im.size))
            resample = getattr(Image, "Resampling", Image).LANCZOS
            im = im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), resample)
            return ImageTk.PhotoImage(im)
        except Exception:
            pass
        try:
            img = tk.PhotoImage(file=p)
        except tk.TclError:
            return None
        big = max(img.width(), img.height())
        best = (1, max(1, math.ceil(big / float(box))))
        best_size = big / float(best[1])
        for z in (1, 2, 3):
            for s in range(1, 13):
                size = big * z / float(s)
                if best_size < size <= box:
                    best, best_size = (z, s), size
        z, s = best
        if z > 1:
            img = img.zoom(z, z)
        if s > 1:
            img = img.subsample(s, s)
        return img

    def _char_image(self, fname):
        """등장인물 이미지를 불러온다 (표시 상자 418px 안에 맞게 정수 배율로 축소). 없으면 None."""
        cache = self.__dict__.setdefault("_char_img_cache", {})
        key = (fname, int(round(CHAR_IMG_BOX * self.canvas.s)))
        if key in cache:
            return cache[key]
        for _old in [k for k in cache if k[0] == fname]:
            del cache[_old]
        img = None
        base = os.path.dirname(os.path.abspath(__file__))
        for d in (base, os.path.join(base, "images"), os.path.join(base, "assets"), os.getcwd()):
            p = os.path.join(d, fname)
            if os.path.exists(p):
                img = self._load_fit(p)
                break
        cache[key] = img
        return img

    def render_char_select(self):
        self.buttons = []
        self.canvas.create_rectangle(0, 0, WIN_W, WIN_H, fill="#000000", outline="",
                                     stipple="gray75", tags="ui")
        pw, ph = 900, 330
        px, py = (WIN_W - pw) / 2, 250
        self.canvas.create_rectangle(px + 5, py + 5, px + pw + 5, py + ph + 5,
                                     fill="#05070A", outline="", stipple="gray50", tags="ui")
        self.canvas.create_rectangle(px, py, px + pw, py + ph, fill=PANEL, outline=ROSE,
                                     width=2, tags="ui")
        self.canvas.create_rectangle(px, py, px + pw, py + 5, fill=ROSE, outline="", tags="ui")
        self.txt(px + 24, py + 16, "등장인물 도감", 30, TXT, bold=True)
        self.txt(px + 24, py + 62, "열람할 등장인물을 고르세요", 12, MUT, mono=True)
        self.txt(px + pw - 24, py + 24, "[F] 닫기 · [ESC] 서재로", 11, MUT, mono=True, anchor="ne")
        self.canvas.create_line(px + 24, py + 84, px + pw - 24, py + 84, fill=BRD, tags="ui")
        n = len(CHARACTERS)
        gap = 16
        bw, bh = (pw - 48 -(n - 1) * gap) / n, 150
        by = py + 104
        for i, c in enumerate(CHARACTERS):
            bx = px + 24 + i * (bw + gap)
            hov = self.hover == ("chs", i)
            self.canvas.create_rectangle(bx, by, bx + bw, by + bh,
                                         fill=PANEL2 if hov else PANEL, outline=c["color"],
                                         width=3 if hov else 2, tags="ui")
            self.canvas.create_rectangle(bx, by, bx + bw, by + 6, fill=c["color"], outline="",
                                         tags="ui")
            self.txt(bx + bw / 2, by + 52, c["id"], 44, c["color"], bold=True, anchor="center")
            self.txt(bx + bw / 2, by + 98, c["role"], 12, TXT, mono=True, anchor="center")
            has = any(fn for _, fn in c["images"])
            self.txt(bx + bw / 2, by + 124, "컨셉 아트 · 이미지" if has else "준비 중",
                     11, HEAL if has else MUT, mono=True, anchor="center")
            sp = c.get("special")
            if sp:
                sp_lock = sp["aspect"] not in self.owned_aspects
                self.txt(bx + bw / 2, by + 20,
                         "★★★ 특별 일러스트 · " + ("잠김" if sp_lock else "해금"),
                         10, MUT if sp_lock else STAR_COLOR[3], mono=True, anchor="center")
            self.buttons.append(dict(x=bx, y=by, w=bw, h=bh, key=("chs", i),
                                     cb=(lambda cid=c["id"]: self.codex_open_char(cid))))

        bx = px + pw / 2 - 70
        self.canvas.create_rectangle(bx, py + ph - 46, bx + 140, py + ph - 14,
                                     fill=PANEL2 if self.hover == ("chs", -1) else PANEL,
                                     outline=MUT, tags="ui")
        self.txt(bx + 70, py + ph - 30, "← 서재로", 12, MUT, mono=True, anchor="center")
        self.buttons.append(dict(x=bx, y=py + ph - 46, w=140, h=32, key=("chs", -1),
                                 cb=self.codex_back))

    def render_char_page(self):
        self.buttons = []
        self._story = None
        c = next((x for x in CHARACTERS if x["id"] == getattr(self, "codex_char", "N")),
                 CHARACTERS[0])
        special = c.get("special")
        page = getattr(self, "codex_char_page", 0) if special else 0
        sp_aspect = next((a for a in ASPECTS if special and a["id"] == special["aspect"]), None)
        sp_name = sp_aspect["title"] if sp_aspect else "특별"
        sp_locked = bool(special and special["aspect"] not in self.owned_aspects)
        locked = bool(page == 1 and sp_locked)
        data = special if page == 1 else c
        accent = STAR_COLOR[3] if page == 1 else c["color"]
        sc = getattr(self.canvas, "s", 1.0)
        desc_text, story_text = self.char_texts(data, page)
        has_story = bool(story_text.strip()) and not locked
        seen = self.__dict__.setdefault("_special_seen", set())
        if special and page == 1 and not sp_locked:
            seen.add(c["id"])
        show_new = bool(special and not sp_locked and c["id"] not in seen)

        self.canvas.create_rectangle(0, 0, WIN_W, WIN_H, fill="#000000", outline="",
                                     stipple="gray75", tags="ui")
        pw, ph = 1000, 810
        px, py = (WIN_W - pw) / 2, 10
        self.canvas.create_rectangle(px + 5, py + 5, px + pw + 5, py + ph + 5,
                                     fill="#05070A", outline="", stipple="gray50", tags="ui")
        self.canvas.create_rectangle(px, py, px + pw, py + ph, fill=PANEL, outline=accent,
                                     width=2, tags="ui")
        self.canvas.create_rectangle(px, py, px + pw, py + 5, fill=accent, outline="",
                                     tags="ui")
        ix, iw = px + 24, pw - 48
        self.txt(ix, py + 12, c["id"], 32, c["color"], bold=True)
        self.txt(ix + 52, py + 28, c["role"], 14, TXT, mono=True)
        self.canvas.create_line(ix, py + 62, ix + iw, py + 62, fill=BRD, tags="ui")

        # 페이지 전환 — 헤더 오른쪽에 크게
        if special:
            pf = self.font(13, bold=True)
            labels = [("1  기본 프로필", c["color"]),
                      ("2  ★★★ %s 특별 일러스트%s" % (sp_name, "  · 잠김" if sp_locked else ""),
                       STAR_COLOR[3])]
            widths = [pf.measure(lbl) + 32 for lbl, _ in labels]
            bx = ix + iw
            for k in (1, 0):
                lbl, col = labels[k]
                bx -= widths[k]
                on = (k == page)
                lock_k = (k == 1 and sp_locked)
                hov = self.hover == ("chp", k)
                self.canvas.create_rectangle(bx, py + 12, bx + widths[k], py + 46,
                                             fill=col if on else (PANEL2 if hov else PANEL),
                                             outline=MUT if lock_k else col,
                                             width=3 if (on or hov) else 2, tags="ui")
                self.txt(bx + widths[k] / 2, py + 29, lbl, 13,
                         "#101318" if on else (MUT if lock_k else TXT),
                         bold=True, anchor="center")
                if k == 1 and show_new and not on:
                    self.canvas.create_rectangle(bx + widths[k] - 40, py + 3, bx + widths[k] - 2,
                                                 py + 20, fill=DMG, outline="", tags="ui")
                    self.txt(bx + widths[k] - 21, py + 11, "NEW", 10, "#FFFFFF", mono=True,
                             bold=True, anchor="center")
                self.buttons.append(dict(x=bx, y=py + 12, w=widths[k], h=34, key=("chp", k),
                                         cb=(lambda p=k: self.codex_set_char_page(p))))
                bx -= 8
            self.txt(bx + 2, py + 29, "페이지 ▶", 11, MUT, mono=True, anchor="e")
            self.txt(ix + iw, py + 49, "← → 키로도 전환할 수 있다", 10, MUT, mono=True, anchor="ne")

        box = CHAR_IMG_BOX
        ty = py + 70

        images = data["images"]
        tabs = list(images) + ([("스토리", None)] if has_story else [])
        tab = max(0, min(getattr(self, "codex_img_tab", 0), len(tabs) - 1))
        story_tab = bool(has_story and tab == len(images))

        # 이미지/스토리 탭 (잠겨 있으면 숨긴다)
        if not locked:
            tx = ix
            for k, (tab_label, _fn) in enumerate(tabs):
                tw = 150
                on = (k == tab)
                hov = self.hover == ("cht", k)
                self.canvas.create_rectangle(tx, ty, tx + tw, ty + 32,
                                             fill=accent if on else (PANEL2 if hov else PANEL),
                                             outline=accent, width=2, tags="ui")
                self.txt(tx + tw / 2, ty + 16, tab_label, 13, "#101318" if on else TXT,
                         bold=on, anchor="center")
                self.buttons.append(dict(x=tx, y=ty, w=tw, h=32, key=("cht", k),
                                         cb=(lambda i=k: self.codex_set_tab(i))))
                tx += tw + 8

        iy = ty + 40
        if story_tab:
            self.render_story_panel(data, story_text, accent, ix, iy, iw, box)
        else:
            # 큰 이미지 (왼쪽)
            if locked:
                cx, cy = ix + box / 2, iy + box / 2
                self.canvas.create_rectangle(ix, iy, ix + box, iy + box, fill="#161A20",
                                             outline=MUT, width=2, dash=(8, 6), tags="ui")
                self.txt(cx, cy - 56, "잠김", 46, MUT, bold=True, anchor="center")
                self.txt(cx, cy + 4, "%s 형상을 획득하면 열린다" % sp_name, 16, TXT, anchor="center")
                self.wtxt(cx, cy + 40, box - 60,
                          "형상해석 ★★★ 1%%  ·  형상파편 %d개로 선택 교환" % GACHA_PITY_TIER3,
                          12, MUT, mono=True, anchor="n", justify="center")
            else:
                label, fname = images[tab]
                img = self._char_image(fname) if fname else None
                self.canvas.create_rectangle(ix - 1, iy - 1, ix + box + 1, iy + box + 1,
                                             fill="#FFFFFF" if img else PANEL2,
                                             outline=accent if img else BRD, tags="ui")
                if img:
                    self.canvas.create_image(ix + (box - img.width() / sc) / 2,
                                             iy + (box - img.height() / sc) / 2,
                                             image=img, anchor="nw", tags="ui")
                else:
                    if fname:
                        msg = ("이미지 파일을 찾을 수 없다\n%s\nNHC.py 와 같은 폴더(또는 images 폴더)에 "
                               "넣어주세요." % fname)
                    else:
                        msg = "준비 중"
                    self.wtxt(ix + box / 2, iy + box / 2, box - 40, msg, 13, MUT, mono=True,
                              anchor="center", justify="center")

            # 설명 (오른쪽)
            dx = ix + box + 20
            dw = iw - box - 20
            self.canvas.create_rectangle(dx, ty, dx + dw, iy + box, fill=PANEL2, outline=BRD,
                                         tags="ui")
            box_title = "프로필" if page == 0 else data["title"]
            self.txt(dx + 14, ty + 12, box_title, 14, accent, bold=True)
            self.canvas.create_line(dx + 14, ty + 40, dx + dw - 14, ty + 40, fill=BRD, tags="ui")
            if locked:
                desc = ("잠겨 있다.\n\n형상해석(E 키)에서 %s 형상을 획득하면 이 페이지가 열린다.\n\n"
                        "획득 확률은 ★★★ 1%%이며, 형상파편 %d개로 선택 교환도 할 수 있다."
                        % (sp_name, GACHA_PITY_TIER3))
            else:
                desc = desc_text
                if has_story:
                    desc += "\n\n▶ '스토리' 탭에서 이어서 읽을 수 있다."
            self.wtxt(dx + 14, ty + 54, dw - 28, desc, 13, MUT if locked else TXT)

            # 페이지 이동 큰 버튼 (설명 칸 아래)
            if special:
                cb_y = iy + box - 56
                if page == 0:
                    lbl = "★★★ %s 특별 일러스트 보러 가기 ▶" % sp_name + ("\n(잠김)" if sp_locked else "")
                    col, target = STAR_COLOR[3], 1
                    dim = sp_locked
                else:
                    lbl = "◀ 1페이지 · 기본 프로필로 돌아가기"
                    col, target = c["color"], 0
                    dim = False
                hov = self.hover == ("chg", 0)
                self.canvas.create_rectangle(dx + 14, cb_y, dx + dw - 14, cb_y + 44,
                                             fill=PANEL2 if hov else PANEL,
                                             outline=MUT if dim else col, width=2, tags="ui")
                self.wtxt(dx + dw / 2, cb_y + 22, dw - 48, lbl, 12, MUT if dim else col,
                          anchor="center", bold=True, justify="center")
                self.buttons.append(dict(x=dx + 14, y=cb_y, w=dw - 28, h=44, key=("chg", 0),
                                         cb=(lambda p=target: self.codex_set_char_page(p))))

        bx = px + pw / 2 - 70
        self.canvas.create_rectangle(bx, py + ph - 46, bx + 140, py + ph - 14,
                                     fill=PANEL2 if self.hover == ("chr", -1) else PANEL,
                                     outline=MUT, tags="ui")
        self.txt(bx + 70, py + ph - 30, "← 목록으로", 12, MUT, mono=True, anchor="center")
        self.buttons.append(dict(x=bx, y=py + ph - 46, w=140, h=32, key=("chr", -1),
                                 cb=self.codex_to_char_select))
        self.txt(px + pw - 24, py + ph - 30, "[F] 닫기 · [ESC] 목록으로", 11, MUT, mono=True,
                 anchor="e")

    def render_effect_codex(self, th=None):
        web = bool(th)
        if not self.codex_open:
            return
        effects, cats = (THEMES[th]["effects"], THEMES[th]["cats"]) if web else (EFFECTS, EFFECT_CATS)
        ecol = THEMES[th]["color"] if web else BRKC
        self.buttons = []     # 뒤쪽 버튼이 눌리지 않도록 교체
        self.canvas.create_rectangle(0, 0, WIN_W, WIN_H, fill="#000000", outline="",
                                     stipple="gray75", tags="ui")
        pw, ph = 900, 640
        px, py = (WIN_W - pw) / 2, 60
        self.canvas.create_rectangle(px + 5, py + 5, px + pw + 5, py + ph + 5,
                                     fill="#05070A", outline="", stipple="gray50", tags="ui")
        self.canvas.create_rectangle(px, py, px + pw, py + ph, fill=PANEL, outline=ecol,
                                     width=2, tags="ui")
        self.canvas.create_rectangle(px, py, px + pw, py + 5, fill=ecol, outline="", tags="ui")
        ix, iw = px + 24, pw - 48

        self.txt(ix, py + 14, "%s 전투효과 도감" % THEMES[th]["label"] if web else "전투효과 도감", 28, TXT, bold=True)
        self.txt(ix + (340 if web else 214), py + 28, "마우스를 올리면 설명 · 클릭하면 아래에 고정", 12, MUT, mono=True)
        self.txt(px + pw - 24, py + 24, "[F] 닫기 · [ESC] 서재로", 11, MUT, mono=True, anchor="ne")
        self.canvas.create_line(ix, py + 60, ix + iw, py + 60, fill=BRD, tags="ui")

        per_row, gap, chip_h = 5, 8, 46
        cw = (iw - (per_row - 1) * gap) / per_row
        y = py + 72
        for cat_id, cat_label, cat_color in cats:
            items = [(i, e) for i, e in enumerate(effects) if e["cat"] == cat_id]
            self.txt(ix, y, "%s  (%d)" % (cat_label, len(items)), 13, cat_color, bold=True)
            y += 24
            for n, (idx, e) in enumerate(items):
                cx = ix + (n % per_row) * (cw + gap)
                cy = y + (n // per_row) * (chip_h + gap)
                hov = self.hover == ("cdx", idx)
                sel = self.codex_sel == idx
                holders = self.effect_holders(e["id"])
                self.canvas.create_rectangle(cx, cy, cx + cw, cy + chip_h,
                                             fill=PANEL2 if (hov or sel) else PANEL,
                                             outline=e["color"],
                                             width=3 if sel else (2 if hov else 1), tags="ui")
                self.txt(cx + cw / 2, cy + 15, e["name"], 14, e["color"], bold=True,
                         anchor="center")
                if holders:
                    self.txt(cx + cw / 2, cy + 34, "● 적용 중 %d" % len(holders), 10, HEAL,
                             mono=True, anchor="center")
                else:
                    sub = e["scope"]
                    sf = self.font(10, mono=True)
                    if sf.measure(sub) > cw - 12:
                        while sub and sf.measure(sub + "…") > cw - 12:
                            sub = sub[:-1]
                        sub += "…"
                    self.txt(cx + cw / 2, cy + 34, sub, 10, MUT, mono=True, anchor="center")
                self.buttons.append(dict(x=cx, y=cy, w=cw, h=chip_h, key=("cdx", idx),
                                         cb=(lambda k=idx: self.select_effect(k))))
            rows = (len(items) + per_row - 1) // per_row
            y += rows * (chip_h + gap) + 8

        if not effects:
            self.txt(ix + iw / 2, y + 40, "이 테마 전용 전투효과는 아직 없다. (임시)", 14, MUT, anchor="center")

        # 고정된 상세 설명
        dy = py + ph - 138
        dh = 86
        self.canvas.create_rectangle(ix, dy, ix + iw, dy + dh, fill=PANEL2, outline=BRD, tags="ui")
        if self.codex_sel is not None and self.codex_sel < len(effects):
            e = effects[self.codex_sel]
            self.txt(ix + 14, dy + 8, e["name"], 16, e["color"], bold=True)
            self.txt(ix + iw - 14, dy + 12, e["scope"], 11, MUT, mono=True, anchor="ne")
            self.wtxt(ix + 14, dy + 32, iw - 28, e["desc"].replace(" / ", "\n"), 11, TXT, mono=True)
        else:
            self.txt(ix + iw / 2, dy + dh / 2, "효과를 클릭하면 여기에 설명이 고정된다.", 12, MUT,
                     mono=True, anchor="center")

        bx = px + pw / 2 - 70
        self.canvas.create_rectangle(bx, py + ph - 40, bx + 140, py + ph - 8,
                                     fill=PANEL2 if self.hover == ("cdx", -1) else PANEL,
                                     outline=MUT, tags="ui")
        self.txt(bx + 70, py + ph - 24, "← 서재로", 12, MUT, mono=True, anchor="center")
        self.buttons.append(dict(x=bx, y=py + ph - 40, w=140, h=32, key=("cdx", -1),
                                 cb=self.codex_back))

        h = self.hover
        if isinstance(h, tuple) and h[0] == "cdx" and 0 <= h[1] < len(effects):
            self.draw_effect_tip(effects[h[1]])

    def lobby_library(self):
        self.codex_open = True
        self.codex_page = "menu"
        self.codex_sel = None
        self.render()

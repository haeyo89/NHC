#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
어드민 패널(기타 탭)에 Orchestra/D 테스트 버튼을 추가한다.

  관객 +5 / 관객 최대(20) / 관객 0 / 피날레 즉시 진입

사용법 (NHC게임.py 가 있는 폴더에서):
    python apply_admin_aud.py

· nhc_admin/panel.py 에 버튼과 메서드를 추가한다 (원본은 .bak 으로 백업).
· nhc_admin/aspects.py 의 '0ㅁ.4' 오타도 함께 고친다.
· 앵커가 맞고 문법 검사를 통과해야만 파일을 쓴다.
"""
import os
import shutil
import sys

base = os.path.dirname(os.path.abspath(__file__))
panel_path = os.path.join(base, "nhc_admin", "panel.py")
asp_path = os.path.join(base, "nhc_admin", "aspects.py")


def fail(msg):
    sys.exit("[중단] %s 아무 파일도 수정하지 않았습니다." % msg)


if not os.path.exists(panel_path):
    fail("nhc_admin/panel.py 를 찾지 못했습니다. (이 스크립트를 NHC게임.py 와 같은 폴더에 두세요)")
panel = open(panel_path, encoding="utf-8").read()
if "admin_orch_aud" in panel:
    fail("이미 적용되어 있습니다.")

# ---- 1) 버튼 ----
BTN_ANCHOR = "self.admin_ult_reset_cd, ROSE, idx)\n            idx += 1\n"
if panel.count(BTN_ANCHOR) != 1:
    fail("기타 탭의 '환상 대기 초기화' 버튼 위치를 찾지 못했습니다 (%d곳)." % panel.count(BTN_ANCHOR))
BTN_ADD = '''            self.abtn(ix + 2 * (mw + gap), body_y + 64, mw, 52, "관객 +5", "Orchestra/D 테스트",
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
'''
panel = panel.replace(BTN_ANCHOR, BTN_ANCHOR + BTN_ADD, 1)

# ---- 2) 메서드 ----
M_ANCHOR = "    def admin_ult_fill(self):"
if panel.count(M_ANCHOR) != 1:
    fail("admin_ult_fill 위치를 찾지 못했습니다.")
METHODS = '''    def _admin_orch_unit(self):
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

'''
panel = panel.replace(M_ANCHOR, METHODS + M_ANCHOR, 1)

try:
    compile(panel, panel_path, "exec")
except SyntaxError as e:
    fail("패치 결과가 문법 검사를 통과하지 못했습니다 (%s)." % e)

# ---- 3) aspects.py 오타 ----
asp_fixed = None
if os.path.exists(asp_path):
    asp = open(asp_path, encoding="utf-8").read()
    if "0ㅁ.4" in asp:
        asp_fixed = asp.replace("0ㅁ.4", "0.4")
        try:
            compile(asp_fixed, asp_path, "exec")
        except SyntaxError as e:
            fail("aspects.py 오타 수정 후에도 문법 오류가 있습니다 (%s, 줄 %s)." % (e.msg, e.lineno))

shutil.copyfile(panel_path, panel_path + ".bak_aud")
open(panel_path, "w", encoding="utf-8", newline="\n").write(panel)
print("nhc_admin/panel.py 수정 완료 (백업: panel.py.bak_aud)")
if asp_fixed is not None:
    shutil.copyfile(asp_path, asp_path + ".bak_aud")
    open(asp_path, "w", encoding="utf-8", newline="\n").write(asp_fixed)
    print("nhc_admin/aspects.py 오타 '0ㅁ.4' → '0.4' 수정 완료")
print("\n전투 중 maki → '기타' 탭에서 확인하세요.")
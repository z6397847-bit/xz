# -*- coding: utf-8 -*-
"""
日内做T信号系统 - Kivy移动端应用 (Android兼容版)
"""

import os
import traceback

# 日志函数
def app_log(msg):
    try:
        with open('/sdcard/t0app_log.txt', 'a') as f:
            from datetime import datetime
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except:
        pass

app_log("=== Starting T0 Trading App ===")

try:
    from kivy.app import App
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.gridlayout import GridLayout
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.label import Label
    from kivy.uix.button import Button
    from kivy.uix.textinput import TextInput
    from kivy.uix.popup import Popup
    from kivy.uix.progressbar import ProgressBar
    from kivy.uix.widget import Widget
    from kivy.clock import Clock
    from kivy.properties import StringProperty, NumericProperty
    from kivy.graphics import Color, Rectangle, RoundedRectangle
    from kivy.metrics import dp, sp
    from kivy.utils import get_color_from_hex, platform
    
    import threading
    import requests
    from datetime import datetime
    
    app_log("Imports successful")
    
    # ==================== 主题配置 ====================
    THEME = {
        'bg': '#0f1117', 'card': '#1a1d26', 'card2': '#252a36',
        'text': '#ffffff', 'gray': '#6b7280', 'green': '#22c55e',
        'red': '#ef4444', 'blue': '#3b82f6'
    }
    
    # ==================== 全局数据 ====================
    class AppData:
        watchlist = ['600586', '000001', '600519', '000858']
        current = '600586'
        stock_cache = {}
    
    DATA = AppData()
    
    # ==================== API ====================
    def fetch_quote(code):
        try:
            sym = f"sh{code}" if code.startswith('6') else f"sz{code}"
            r = requests.get(f'http://qt.gtimg.cn/q={sym}', timeout=5)
            r.encoding = 'gbk'
            if 'v_' in r.text:
                p = r.text.split('~')
                if len(p) > 40:
                    return {
                        'name': p[1], 'code': code,
                        'price': float(p[3] or 0),
                        'change': float(p[32] or 0),
                        'high': float(p[33] or 0),
                        'low': float(p[34] or 0),
                    }
        except Exception as e:
            app_log(f"fetch_quote error: {e}")
        return None
    
    def fetch_prices(code):
        try:
            sym = f"sh{code}" if code.startswith('6') else f"sz{code}"
            r = requests.get(f'http://data.gtimg.cn/flashdata/hushen/minute/{sym}.js', timeout=5)
            prices = []
            for line in r.text.split('\\n\\')[1:]:
                parts = line.strip().split(' ')
                if len(parts) >= 2:
                    try:
                        prices.append(float(parts[1]))
                    except:
                        pass
            return prices
        except Exception as e:
            app_log(f"fetch_prices error: {e}")
        return []
    
    # ==================== 简单技术分析 ====================
    def calc_rsi(p, n=14):
        if len(p) < n+1: return 50
        gains, losses = [], []
        for i in range(1, min(n+1, len(p))):
            diff = p[-i] - p[-i-1]
            if diff > 0:
                gains.append(diff)
            else:
                losses.append(-diff)
        avg_gain = sum(gains) / n if gains else 0.01
        avg_loss = sum(losses) / n if losses else 0.01
        rs = avg_gain / avg_loss
        return round(100 - 100 / (1 + rs), 1)
    
    def calc_ma(p, n):
        return round(sum(p[-n:]) / min(n, len(p)), 2) if p else 0
    
    def calc_support_resistance(p, n=15):
        if len(p) < n: 
            return (round(min(p), 2), round(max(p), 2)) if p else (0, 0)
        return round(min(p[-n:]), 2), round(max(p[-n:]), 2)
    
    # ==================== UI组件 ====================
    class CLabel(Label):
        def __init__(self, **kw):
            super().__init__(**kw)
            if 'color' not in kw:
                self.color = get_color_from_hex(THEME['text'])
    
    class CButton(Button):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.background_normal = ''
            if 'background_color' not in kw:
                self.background_color = get_color_from_hex(THEME['blue'])
    
    class Card(BoxLayout):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.padding = dp(8)
            with self.canvas.before:
                Color(*get_color_from_hex(THEME['card']))
                self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
            self.bind(pos=self._update, size=self._update)
        
        def _update(self, *a):
            self.rect.pos = self.pos
            self.rect.size = self.size
    
    # ==================== 主页 ====================
    class HomePage(BoxLayout):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.orientation = 'vertical'
            self.spacing = dp(5)
            self.padding = dp(5)
            
            app_log("Building HomePage...")
            
            # 绘制背景
            with self.canvas.before:
                Color(*get_color_from_hex(THEME['bg']))
                self.bg_rect = Rectangle(pos=self.pos, size=self.size)
            self.bind(pos=self._upd_bg, size=self._upd_bg)
            
            self._build()
            Clock.schedule_once(lambda dt: self.refresh(), 1)
            
            app_log("HomePage built")
        
        def _upd_bg(self, *a):
            self.bg_rect.pos = self.pos
            self.bg_rect.size = self.size
        
        def _build(self):
            # 股票信息
            info = Card(size_hint_y=0.15, orientation='horizontal')
            left = BoxLayout(orientation='vertical', size_hint_x=0.6)
            self.name_lbl = CLabel(text='--', font_size=sp(18), bold=True, halign='left')
            self.code_lbl = CLabel(text='--', font_size=sp(12), color=get_color_from_hex(THEME['gray']))
            left.add_widget(self.name_lbl)
            left.add_widget(self.code_lbl)
            right = BoxLayout(orientation='vertical', size_hint_x=0.4)
            self.price_lbl = CLabel(text='--', font_size=sp(22), bold=True, halign='right')
            self.change_lbl = CLabel(text='--', font_size=sp(14), halign='right')
            right.add_widget(self.price_lbl)
            right.add_widget(self.change_lbl)
            info.add_widget(left)
            info.add_widget(right)
            self.add_widget(info)
            
            # 技术指标
            g1 = GridLayout(cols=4, spacing=dp(4), size_hint_y=0.12)
            self.rsi_lbl = self._make_indicator("RSI", "--")
            self.ma5_lbl = self._make_indicator("MA5", "--")
            self.sup_lbl = self._make_indicator("支撑", "--")
            self.res_lbl = self._make_indicator("压力", "--")
            g1.add_widget(self.rsi_lbl)
            g1.add_widget(self.ma5_lbl)
            g1.add_widget(self.sup_lbl)
            g1.add_widget(self.res_lbl)
            self.add_widget(g1)
            
            # 信号评分
            sig = Card(size_hint_y=0.2, orientation='vertical')
            sig.add_widget(CLabel(text='📊 信号评分', font_size=sp(14), size_hint_y=0.3))
            self.score_lbl = CLabel(text='--', font_size=sp(36), bold=True, size_hint_y=0.4)
            sig.add_widget(self.score_lbl)
            self.sig_tip = CLabel(text='等待分析...', font_size=sp(12), size_hint_y=0.3)
            sig.add_widget(self.sig_tip)
            self.add_widget(sig)
            
            # 自选股列表标题
            self.add_widget(CLabel(text='📋 自选股', font_size=sp(14), size_hint_y=0.05, halign='left'))
            
            # 自选股列表
            sv = ScrollView(size_hint_y=0.35)
            self.stock_list = BoxLayout(orientation='vertical', spacing=dp(3), size_hint_y=None)
            self.stock_list.bind(minimum_height=self.stock_list.setter('height'))
            sv.add_widget(self.stock_list)
            self.add_widget(sv)
            
            self._build_stock_list()
            
            # 刷新按钮
            btn = CButton(text='刷新数据', size_hint_y=0.08, font_size=sp(14))
            btn.bind(on_release=lambda x: self.refresh())
            self.add_widget(btn)
        
        def _make_indicator(self, name, value):
            box = Card(orientation='vertical', padding=dp(4))
            box.add_widget(CLabel(text=name, font_size=sp(10), color=get_color_from_hex(THEME['gray'])))
            lbl = CLabel(text=value, font_size=sp(13), bold=True)
            box.add_widget(lbl)
            box.value_lbl = lbl
            return box
        
        def _build_stock_list(self):
            self.stock_list.clear_widgets()
            self.stock_btns = {}
            for code in DATA.watchlist:
                btn = Button(
                    text=f'{code}  --',
                    size_hint_y=None, height=dp(45),
                    background_normal='',
                    background_color=get_color_from_hex(THEME['card'])
                )
                btn.code = code
                btn.bind(on_release=lambda x: self._select_stock(x.code))
                self.stock_list.add_widget(btn)
                self.stock_btns[code] = btn
        
        def _select_stock(self, code):
            DATA.current = code
            self.refresh()
        
        def refresh(self):
            app_log(f"Refreshing data for {DATA.current}")
            def f():
                # 获取当前股票数据
                q = fetch_quote(DATA.current)
                if q:
                    DATA.stock_cache[DATA.current] = q
                p = fetch_prices(DATA.current)
                
                # 获取自选股数据
                for code in DATA.watchlist:
                    qq = fetch_quote(code)
                    if qq:
                        DATA.stock_cache[code] = qq
                
                Clock.schedule_once(lambda dt: self._update_ui(q, p), 0)
            
            threading.Thread(target=f, daemon=True).start()
        
        def _update_ui(self, q, prices):
            app_log("Updating UI...")
            if q:
                self.name_lbl.text = q['name']
                self.code_lbl.text = q['code']
                self.price_lbl.text = f"{q['price']:.2f}"
                c = q['change']
                self.change_lbl.text = f"{'+' if c >= 0 else ''}{c:.2f}%"
                col = THEME['green'] if c >= 0 else THEME['red']
                self.price_lbl.color = self.change_lbl.color = get_color_from_hex(col)
            
            if prices:
                rsi = calc_rsi(prices)
                ma5 = calc_ma(prices, 5)
                sup, res = calc_support_resistance(prices)
                
                self.rsi_lbl.value_lbl.text = str(rsi)
                self.ma5_lbl.value_lbl.text = str(ma5)
                self.sup_lbl.value_lbl.text = str(sup)
                self.res_lbl.value_lbl.text = str(res)
                
                # 简单评分
                score = 50
                if rsi < 30: score += 30
                elif rsi < 40: score += 20
                elif rsi > 70: score -= 20
                
                self.score_lbl.text = str(min(100, max(0, score)))
                
                if score >= 70:
                    self.sig_tip.text = '📈 建议买入'
                    self.sig_tip.color = get_color_from_hex(THEME['green'])
                elif score <= 30:
                    self.sig_tip.text = '📉 建议卖出'
                    self.sig_tip.color = get_color_from_hex(THEME['red'])
                else:
                    self.sig_tip.text = '⏸ 观望等待'
                    self.sig_tip.color = get_color_from_hex(THEME['gray'])
            
            # 更新自选股列表
            for code, btn in self.stock_btns.items():
                qq = DATA.stock_cache.get(code)
                if qq:
                    c = qq['change']
                    color = THEME['green'] if c >= 0 else THEME['red']
                    btn.text = f"{qq['name']}  {qq['price']:.2f}  {'+' if c >= 0 else ''}{c:.2f}%"
                    # 高亮当前选中
                    if code == DATA.current:
                        btn.background_color = get_color_from_hex(THEME['blue'])
                    else:
                        btn.background_color = get_color_from_hex(THEME['card'])
            
            app_log("UI updated")

    # ==================== 主应用 ====================
    class MainApp(BoxLayout):
        def __init__(self, **kw):
            super().__init__(**kw)
            app_log("Building MainApp...")
            self.home = HomePage()
            self.add_widget(self.home)
            app_log("MainApp built")

    class T0App(App):
        def build(self):
            app_log("T0App.build()")
            return MainApp()
        
        def on_start(self):
            app_log("T0App.on_start()")
        
        def on_pause(self):
            app_log("T0App.on_pause()")
            return True
        
        def on_resume(self):
            app_log("T0App.on_resume()")

    app_log("App class defined, starting...")

except Exception as e:
    error_msg = f"INIT ERROR: {e}\n{traceback.format_exc()}"
    app_log(error_msg)
    raise

if __name__ == '__main__':
    T0App().run()

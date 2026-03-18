import ccxt
import pandas as pd
import ta
import os
import time
import winsound
import asyncio
import asyncio
import msvcrt
import json
import re
import unicodedata
from datetime import datetime
from math import floor
# =================================================================
# 🎨 STYLE & PALETTE
# =================================================================
G_LNR, G_CYN, G_GRN, G_RED, G_YLW, G_WHT, G_BOLD, RESET = "\033[95m", "\033[96m", "\033[92m", "\033[91m", "\033[93m", "\033[97m", "\033[1m", "\033[0m"

# =================================================================
# 🔑 API & CONFIG (WAJIB DIUBAH!)
# =================================================================
# Harap ganti dengan API Key dan Secret Anda sendiri dari BINANCE
API_KEY = "URTkupyJPK4Fftxo7fs5VCpb90CdZznJNCbUeJ1etjHXxB2RvuxLReHTLPibcHJr"      # GANTI DENGAN API KEY BINANCE ANDA
SECRET = "WWGjW1SDgVu6URYWVUvPodpSdKWNFTw4zctSO4pbjKTF9UtVJnJQguxoODyUKQdO"    # GANTI DENGAN SECRET KEY BINANCE ANDA

# --- PENGATURAN TRADING ---
DRY_RUN = True             # 🟢 True = SIMULASI (AMAN), False = LIVE TRADING (UANG ASLI)
LEVERAGE = 20              # Leverage yang akan digunakan (contoh: 20x)
TRADE_CAPITAL_USDT = 10.0     # Modal manual (hanya dipakai jika AUTO_SCALE_MARGIN = False)

# --- SISTEM MODAL DINAMIS (COMPOUND INTEREST) ---
AUTO_SCALE_MARGIN = True    # ⚡ True = Gunakan % saldo, False = Gunakan angka tetap di atas
MARGIN_RISK_PCT = 10.0      # % saldo per koin (Contoh: 10.0 = 10% dari wallet)
SAFE_FLOOR_USDT = 10.0       # Batas minimal modal (Jangan kurang dari biaya admin & debu)
BE_TRIGGER_PCT = 1.2       # Pindahkan SL ke Break-Even jika profit mencapai 1.2%
PARTIAL_TP_PCT = 1.5       # Amankan 50% profit (Take Half) saat mencapai 1.5%

# Konfigurasi Baru: TP/SL Dinamis via ATR dan Multi-Timeframe
TIMEFRAME_EXEC = '15m'     # Timeframe untuk eksekusi sinyal EMA 7 & 14
TIMEFRAME_MACRO = '1h'     # Timeframe untuk filter arah trend utama (EMA 200)
ATR_TP1_MULT = 1.0         # TP1 (Tutup 33% & Aktifkan Break-Even)
ATR_TP2_MULT = 2.0         # TP2 (Tutup 33% lagi)
ATR_TP3_MULT = 3.5         # TP3 (Tutup sisa posisi)
ATR_MULTIPLIER_SL = 2.0    # SL diperlebar menjadi 2.0x ATR agar lebih tahan gocekan
TSL_ACTIVATION_PCT = 20.0  # TSL aktif jika profit > 15%
TSL_DISTANCE_PCT = 1.0    # Jarak SL mengekor (5% di bawah harga puncak)
MAX_CONCURRENT_TRADES = 1  # Maksimal koin yang ditradingkan dalam 1 waktu
active_trades = {}         # Dictionary untuk menyimpan state posisi trading yang aktif
ZERO_FEE_LIST = [
    "BTC/USDT:USDT", "ETH/USDT:USDT"
] # Hanya koin utama yang mendukung trading otomatis penuh tanpa agreement tambahan
macro_cache = {}          # 🧠 Cache untuk data EMA 200 (Macro)

# =================================================================
# ⚙️ KONEKSI & INISIALISASI MESIN
# =================================================================
exchange = ccxt.binance({
    "apiKey": API_KEY,
    "secret": SECRET,
    "enableRateLimit": True,
    "options": {
        "defaultType": "swap",  # Menggunakan pasar USDT-M FUTURES (Swap)
        "fetchMarkets": ["spot", "linear"], # Bypass dapi.binance.com error 
        "adjustForTimeDifference": True,
        "recvWindow": 60000 
    }
})

# Pastikan bot menyinkronkan waktu dengan server Binance sebelum mulai
try:
    exchange.load_time_difference()
    # Muat metadata market untuk mendapatkan informasi status koin (Trading/Maintenance)
    print(f"{G_YLW}⏳ Memuat basis data market Binance...{RESET}")
    exchange.load_markets() # Sync call is fine here at start, or use asyncio.to_thread
except Exception:
    pass

stats = {"wins": 0, "losses": 0, "start_time": datetime.now(), "last_pnl": 0.0}
bot_messages = [] # Buffer untuk pesan log agar tidak merusak UI

def add_log(msg):
    """Menambahkan pesan ke buffer dan menjaga ukurannya (maks 5 pesan)."""
    global bot_messages
    t_now = datetime.now().strftime("%H:%M:%S")
    bot_messages.append(f"[{t_now}] {msg}")
    if len(bot_messages) > 5:
        bot_messages.pop(0)

def clear_screen(): 
    # Gunakan os.system('cls') untuk Windows agar membersihkan seluruh scrollback buffer
    # Ini penting untuk koin yang sangat banyak (100+) agar tidak "numpuk"
    if os.name == 'nt':
        os.system('cls')
    else:
        print("\033[H\033[2J", end="", flush=True)

def strip_ansi(text):
    """Menghapus kode warna ANSI agar perhitungan panjang teks akurat."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', str(text))

def get_visual_width(text):
    """Menghitung lebar visual teks (mengabaikan ANSI, menangani wide characters/emojis)."""
    clean = strip_ansi(text)
    width = 0
    for char in clean:
        cp = ord(char)
        # Box Drawing characters (U+2500 - U+257F) should always be 1-wide
        if 0x2500 <= cp <= 0x257F:
            width += 1
            continue
            
        # emojis specific handle for trading bot
        # 🛡️, 💎, 🚀, 💥, 🎯, 🔥, ⚡, 🤖, 🟢, 🔴, 🟡, 🕒, ✅, 🛡, 🧪, 🛡️
        # Many of these are 'A' (Ambiguous) or 'W' (Wide)
        eaw = unicodedata.east_asian_width(char)
        if eaw in ('W', 'F', 'A'):
            width += 2
        else:
            width += 1
    return width

def f_p(val):
    """Smart format price berdasarkan besarnya nilai (Precision handling)."""
    try:
        val = float(val)
        if val == 0: return "0.00"
        abs_v = abs(val)
        if abs_v >= 1000: return f"{val:,.1f}"
        if abs_v >= 10: return f"{val:,.2f}"
        if abs_v >= 1: return f"{val:,.4f}"
        if abs_v >= 0.01: return f"{val:,.5f}"
        if abs_v >= 0.0001: return f"{val:,.7f}"
        return f"{val:,.8f}"
    except: return str(val)

    
def draw_header(bal, live_pnl=0, return_str=False, width=87):
    """Menggambar header dashboard yang rapi dan informatif."""
    output = []
    def echo(txt):
        if return_str: output.append(txt)
        else: print(txt)

    uptime = str(datetime.now() - stats["start_time"]).split('.')[0]
    won, total, last_pnl_str, pnl_color = 0, 0, "$+0.00", G_WHT
    try:
        if os.path.exists("trade_history.json"):
            with open("trade_history.json", "r") as f:
                history = json.load(f)
                won = sum(1 for x in history if x.get('pnl_val', x.get('pnl_value', 0)) > 0)
                total = len(history)
                if history:
                    last = history[-1]
                    last_v = last.get('pnl_val', last.get('pnl_value', 0.0))
                    last_pnl_str = f"${last_v:+.2f}"
                    pnl_color = G_GRN if last_v > 0 else G_RED
    except: pass

    TABLE_WIDTH = max(87, width)
    INNER_WIDTH = TABLE_WIDTH - 2
    
    # Header Title
    title = "🤖 AG-FUTUREBOT v1.2 (Premium Scaling)"
    title_width = get_visual_width(title)
    title_pad = (INNER_WIDTH - title_width) // 2
    title_pad_left = " " * title_pad
    title_pad_right = " " * (INNER_WIDTH - title_pad - title_width)
    
    echo(f"{G_CYN}╔{'═' * INNER_WIDTH}╗{RESET}")
    echo(f"{G_CYN}║{title_pad_left}{G_BOLD}{title}{RESET}{title_pad_right}{G_CYN}║{RESET}")
    
    # Pembatas dinamis
    sep_pos = int(INNER_WIDTH * 0.6)
    echo(f"{G_CYN}╠{'═' * sep_pos}╤{'═' * (INNER_WIDTH - sep_pos - 1)}╣{RESET}")
    
    # Baris 1: Saldo & Mode
    mode_raw = 'SIMULASI' if DRY_RUN else 'LIVE TRADING'
    mode_col = G_YLW if DRY_RUN else G_GRN
    
    pnl_str_fmt = f"{G_GRN}+{live_pnl:.2f}{RESET}" if live_pnl > 0 else f"{G_RED}{live_pnl:.2f}{RESET}" if live_pnl < 0 else f"{live_pnl:.2f}"
    
    bal_total = bal.get('total', 0)
    bal_free = bal.get('free', 0)
    equity = bal_total + live_pnl
    equity_col = G_GRN if live_pnl > 0 else G_RED if live_pnl < 0 else G_WHT
    
    s_left_content = f" Wallet: {equity_col}${equity:,.2f}{RESET} │ Margin: {G_YLW}${bal_free:,.2f}{RESET} ({pnl_str_fmt})"
    s_left_width = get_visual_width(s_left_content)
    s_left_pad = " " * max(0, sep_pos - s_left_width)
    
    s_right_content = f" {mode_col}{mode_raw}{RESET} | Up: {uptime}"
    s_right_width = get_visual_width(s_right_content)
    s_right_pad = " " * max(0, (INNER_WIDTH - sep_pos - 1) - s_right_width)
    
    echo(f"{G_CYN}║{s_left_content}{s_left_pad}│{s_right_content}{s_right_pad}║{RESET}")
    
    # Baris 2: Capital & Stats
    scale_text_raw = f"⚡ AUTO-SCALE ({MARGIN_RISK_PCT}%)" if AUTO_SCALE_MARGIN else f"固定 FIXED ({TRADE_CAPITAL_USDT} USDT)"
    scale_col = G_YLW if AUTO_SCALE_MARGIN else G_CYN
    
    c_left_content = f" Capital: {scale_col}{scale_text_raw}{RESET}"
    c_left_width = get_visual_width(c_left_content)
    c_left_pad = " " * max(0, sep_pos - c_left_width)
    
    c_right_content = f" W/L: {G_GRN}{won}{RESET}/{total} | Last: {pnl_color}{last_pnl_str}{RESET}"
    c_right_width = get_visual_width(c_right_content)
    c_right_pad = " " * max(0, (INNER_WIDTH - sep_pos - 1) - c_right_width)
    
    echo(f"{G_CYN}║{c_left_content}{c_left_pad}│{c_right_content}{c_right_pad}║{RESET}")
    echo(f"{G_CYN}╚{'═' * INNER_WIDTH}╝{RESET}")
    
    if bot_messages:
        echo(f" {G_CYN}🕒 NOTIFIKASI TERBARU:{RESET}")
        for m in bot_messages:
            echo(f"  {G_WHT}• {m}{RESET}")
        echo("")
    
    if return_str: return "\n".join(output)

def draw_active_trades(return_str=False, width=87):
    """Menampilkan daftar posisi aktif dengan lebar dinamis dan format harga presisi."""
    output = []
    def echo(txt):
        if return_str: output.append(txt)
        else: print(txt)

    if active_trades:
        # Pre-formatting rows to calculate width
        rows_data = []
        max_row_v_width = 0
        
        for sym, t in active_trades.items():
            side_color = G_GRN if t['side'] == "LONG" else G_RED
            pnl_color = G_GRN if t['pnl_pct'] >= 0 else G_RED
            
            be_icon = "🛡️" if t.get('be_active') else "  "
            tsl_icon = "💎" if t.get('tsl_active') else "  "
            tp1_tag = "✅" if t.get('tp1_active') else "1️⃣"
            tp2_tag = "✅" if t.get('tp2_active') else "2️⃣"
            
            s_name = f"{sym.split('/')[0][:8]}"
            c1 = f" {G_WHT}{s_name:<8}{RESET} "
            c2 = f"{side_color}{t['side'][:1]}{RESET} "
            c3 = f"{G_CYN}{be_icon}{tsl_icon}{RESET} "
            c4 = f"E:{f_p(t.get('entry',0))} "
            c5 = f"PnL:{pnl_color}{t['pnl_pct']:>+4.0f}%{RESET} "
            
            # Use smart formatter f_p
            prices = f"{G_GRN}{tp1_tag}{f_p(t.get('tp1',0))} {tp2_tag}{f_p(t.get('tp2',0))} 3️⃣{f_p(t.get('tp3',0))}{RESET}"
            c6 = f"│ {prices} "
            c7 = f"│ SL:{G_RED}{f_p(t.get('sl',0))}{RESET} "
            c8 = f"│ N:{G_YLW}{f_p(t.get('now',0))}{RESET} "
            
            line_content = f"{c1}│ {c2}│ {c3}│ {c4}│ {c5}{c6}{c7}{c8}"
            max_row_v_width = max(max_row_v_width, get_visual_width(line_content))
            rows_data.append(line_content)

        TABLE_WIDTH = max(87, width, max_row_v_width + 2)
        INNER_WIDTH = TABLE_WIDTH - 2
        
        title_text = f" [ POSISI AKTIF ({len(active_trades)}/{MAX_CONCURRENT_TRADES}) ] "
        title_width = get_visual_width(title_text)
        side_pad = max(0, (INNER_WIDTH - title_width) // 2)
        pad_left = "═" * side_pad
        pad_right = "═" * (INNER_WIDTH - side_pad - title_width)
        
        echo(f"{G_CYN}╔{pad_left}{G_WHT}{title_text}{G_CYN}{pad_right}╗{RESET}")
        
        for row in rows_data:
            v_width = get_visual_width(row)
            padding = " " * max(0, INNER_WIDTH - v_width)
            echo(f"{G_CYN}║{row}{padding}║{RESET}")
            
        echo(f"{G_CYN}╚{'═' * INNER_WIDTH}╝{RESET}")
        return TABLE_WIDTH if not return_str else "\n".join(output)
    
    if return_str: return ""

async def get_balance():
    if DRY_RUN: return {"total": 12.5, "free": 12.5}
    try:
        bal = await asyncio.to_thread(exchange.fetch_balance)
        return {
            "total": float(bal['total'].get('USDT', 0)),
            "free": float(bal['free'].get('USDT', 0))
        }
    except Exception as e:
        print(f"\n{G_RED}Error saat mengambil saldo: {e}{RESET}")
        return {"total": 0.0, "free": 0.0}

# =================================================================
# 🧠 MESIN ANALISIS & STRATEGI
# =================================================================
async def fetch_ohlcv(symbol, timeframe, limit=100):
    """Helper untuk mengambil data harian/menit dan menghitung indikator dasar."""
    try:
        ohlcv = await asyncio.to_thread(exchange.fetch_ohlcv, symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['t', 'o', 'h', 'l', 'c', 'v'])
        # Hitung indikator standar (EMA 9/21/50, RSI, ADX, ATR)
        df['ema_fast'] = ta.trend.ema_indicator(df['c'], window=9)
        df['ema_slow'] = ta.trend.ema_indicator(df['c'], window=21)
        df['ema_pulse'] = ta.trend.ema_indicator(df['c'], window=50)
        df['rsi'] = ta.momentum.rsi(df['c'], window=14)
        df['adx'] = ta.trend.adx(df['h'], df['l'], df['c'], window=14)
        df['atr'] = ta.volatility.average_true_range(df['h'], df['l'], df['c'], window=14)
        return df
    except Exception:
        return None

async def analyze_signal(symbol, momentum=False):
    try:
        if not "/" in symbol: symbol = f"{symbol.upper()}/USDT:USDT"
        
        # 1. Ambil data Makro untuk Filter Tren (EMA 200) - DENGAN CACHE (Diturunkan ke 3 Menit agar lebih Up-to-date)
        now_ts = time.time()
        if symbol in macro_cache and (now_ts - macro_cache[symbol]['ts'] < 120):
            macro_trend = macro_cache[symbol]['trend']
        else:
            ohlcv_macro = await asyncio.to_thread(exchange.fetch_ohlcv, symbol, TIMEFRAME_MACRO, limit=250)
            df_macro = pd.DataFrame(ohlcv_macro, columns=['t', 'o', 'h', 'l', 'c', 'v'])
            df_macro['ema_200'] = ta.trend.ema_indicator(df_macro['c'], window=200)
            macro_trend = "UP" if df_macro.iloc[-1]['c'] > df_macro.iloc[-1]['ema_200'] else "DOWN"
            macro_cache[symbol] = {'trend': macro_trend, 'ts': now_ts}
        
        # 2. Ambil data Eksekusi (EMA 7 & 14, ADX, ATR) menggunakan helper
        df = await fetch_ohlcv(symbol, TIMEFRAME_EXEC, limit=100)
        if df is None: return "WAIT", [], 0
        
        # Tambahkan Volume EMA khusus untuk analyze_signal
        df['vol_ema'] = ta.trend.ema_indicator(df['v'], window=20)
        
        last, prev = df.iloc[-1], df.iloc[-2]
        
        # Filter Sideway & Filter Validasi Indikator
        # ADX sudah diturunkan user ke 18 (Sudah Bagus untuk Agresif)
        if pd.isna(last['adx']) or pd.isna(last['atr']) or last['adx'] < 20:
            return "WAIT", 0, 0
            
        # Filter Volume: Sekarang lebih longgar (60% dari rata-rata cukup untuk masuk)
        if last['v'] < (last['vol_ema'] * 0.6):
            return "WAIT", 0, 0
        
        atr_val = last['atr']
        price_now = last['c']
        
        # Hitung jarak harga untuk SL dan TP berdasar ATR
        # (Jarak TP disesuaikan otomatis di bawah berdasarkan trend)
        
        # Logika Sinyal Terpadu (EMA Crossover + EMA 50 Pulse + RSI Filter)
        def check_signal():
            # 1. Pastikan RSI tidak ekstrem (Filter Overbought/Oversold)
            # LONG hanya jika RSI < 70, SHORT hanya jika RSI > 30
            rsi_val = last['rsi']
            
            # Crossover murni dalam 5 bar terakhir
            for idx in range(-1, -6, -1):
                c = df.iloc[idx]
                p = df.iloc[idx-1]
                
                # --- LOGIKA LONG ---
                # Crossover 9/21 + Diatas EMA 50 + RSI Kurang dari 70
                if c['ema_fast'] > c['ema_slow'] and p['ema_fast'] <= p['ema_slow']:
                    if c['c'] > c['ema_pulse'] and rsi_val < 70:
                        return "LONG"
                
                # --- LOGIKA SHORT ---
                # Crossover 9/21 + Dibawah EMA 50 + RSI Lebih dari 30
                if c['ema_fast'] < c['ema_slow'] and p['ema_fast'] >= p['ema_slow']:
                    if c['c'] < c['ema_pulse'] and rsi_val > 30:
                        return "SHORT"
            
            # Trend Flow Momentum (Hanya untuk Sniper Mode)
            if momentum:
                if last['ema_fast'] > last['ema_slow'] and last['c'] > last['ema_pulse'] and rsi_val < 65: 
                    return "LONG"
                if last['ema_fast'] < last['ema_slow'] and last['c'] < last['ema_pulse'] and rsi_val > 35: 
                    return "SHORT"
                
            return "WAIT"

        sig = check_signal()

        if sig == "LONG": 
            # LONG SIGNAL - Target lebih besar jika Macro Trend mendukung
            tp1 = price_now + (atr_val * (1.2 if macro_trend == "UP" else 0.8))
            tp2 = price_now + (atr_val * (2.2 if macro_trend == "UP" else 1.5))
            tp3 = price_now + (atr_val * (3.8 if (momentum or macro_trend == "UP") else 2.5))
            sl = price_now - (atr_val * ATR_MULTIPLIER_SL)
            return "LONG", [tp1, tp2, tp3], sl
            
        elif sig == "SHORT": 
            # SHORT SIGNAL - Target lebih besar jika Macro Trend mendukung
            tp1 = price_now - (atr_val * (1.2 if macro_trend == "DOWN" else 0.8))
            tp2 = price_now - (atr_val * (2.2 if macro_trend == "DOWN" else 1.5))
            tp3 = price_now - (atr_val * (3.8 if (momentum or macro_trend == "DOWN") else 2.5))
            sl = price_now + (atr_val * ATR_MULTIPLIER_SL)
            return "SHORT", [tp1, tp2, tp3], sl
            
        return "WAIT", [], 0
    except Exception:
        return "WAIT", 0, 0

# =================================================================
# ⚙️ FUNGSI CORE TRADING FUTURES
# =================================================================
async def set_leverage(symbol, leverage):
    try:
        if DRY_RUN: 
            print(f"{G_YLW}🤖 [SIMULASI] Leverage diatur ke {leverage}x untuk {symbol}{RESET}")
            return True
        
        print(f"{G_YLW}Mengatur margin ISOLATED dan leverage {leverage}x untuk {symbol}...{RESET}")
        
        try:
            # Set to isolated margin mode first
            await asyncio.to_thread(exchange.set_margin_mode, 'isolated', symbol)
        except Exception as e:
            # Ignore error if it's already in isolated mode
            if "No need to change margin type" not in str(e) and "-4046" not in str(e):
                pass # Print ignore
            
        # Set leverage for Binance
        await asyncio.to_thread(exchange.set_leverage, leverage, symbol)
        
        print(f"{G_GRN}✅ Leverage berhasil diatur ke {leverage}x.{RESET}")
        return leverage
    except Exception as e:
        # Fallback jika leverage ditolak (Error -4028: Leverage is not valid)
        if "-4028" in str(e) or "not valid" in str(e).lower():
            if leverage > 10:
                print(f"{G_YLW}⚠️ Leverage {leverage}x ditolak Binance. Mencoba otomatis ke 10x...{RESET}")
                return await set_leverage(symbol, 10)
            elif leverage > 5:
                print(f"{G_YLW}⚠️ Leverage {leverage}x ditolak Binance. Mencoba otomatis ke 5x...{RESET}")
                return await set_leverage(symbol, 5)
        
        print(f"\n{G_RED}Gagal mengatur leverage untuk {symbol}: {e}{RESET}")
        await asyncio.sleep(4) 
        return 0

async def get_position(symbol):
    try:
        positions = await asyncio.to_thread(exchange.fetch_positions, [symbol])
        # Gunakan p['symbol'] (format terpadu CCXT) untuk pencocokan yang akurat
        position = next((p for p in positions if p['symbol'] == symbol), None)
        if position and float(position['contracts']) > 0:
            return position
        return None
    except Exception:
        return None

async def monitor_position(symbol, entry_price, contracts, pos_side, tp_targets, sl_p, actual_lev, momentum=False):
    """Fungsi mandiri untuk memantau satu posisi trading aktif dengan 3 lapis TP"""
    be_activated = False
    tp1_taken = False
    tp2_taken = False
    tsl_active = False
    highest_price = entry_price if pos_side == "LONG" else 0
    lowest_price = entry_price if pos_side == "SHORT" else 9999999
    current_contracts = contracts
    original_contracts = contracts
    realized_pnl_val = 0.0 # Melacak profit yang sudah dikunci (TP1, TP2)
    closing_side = 'sell' if pos_side == "LONG" else 'buy'
    try:
        while symbol in active_trades:
            pnl_pct = 0
            pnl_value = 0
            p_now = 0

            # Jika mode LIVE, ambil status riil dari exchange
            if not DRY_RUN:
                position = await get_position(symbol)
                # Jika posisi sudah tidak ada di exchange, berarti sudah ditutup oleh TP/SL/Manual
                if not position:
                    add_log(f"💥 Posisi {symbol} telah tertutup di server Binance.")
                    ticker = await asyncio.to_thread(exchange.fetch_ticker, symbol)
                    close_price = ticker['last']
                    pnl_pct = ((close_price - entry_price) / entry_price) * 100 * actual_lev
                    if pos_side == "SHORT": pnl_pct *= -1
                    pnl_value = (TRADE_CAPITAL_USDT * pnl_pct) / 100
                    result = "WIN" if pnl_pct > 0 else "LOSS"
                    save_trade_history(symbol, pos_side, entry_price, close_price, pnl_pct, pnl_value, result)
                    winsound.Beep(800, 500)
                    del active_trades[symbol]
                    break
                    
                ticker = await asyncio.to_thread(exchange.fetch_ticker, symbol)
                p_now = ticker['last']

                # SINKRONISASI DATA HARGA & PNL DARI EXCHANGE
                if position.get('entryPrice') and float(position['entryPrice']) > 0:
                    entry_price = float(position['entryPrice'])
                
                if position.get('unrealizedPnl') is not None:
                    pnl_value = float(position['unrealizedPnl'])
                    margin_used = float(position.get('initialMargin', TRADE_CAPITAL_USDT))
                    pnl_pct = (pnl_value / margin_used) * 100 if margin_used > 0 else 0
                else:
                    pnl_pct = ((p_now - entry_price) / entry_price) * 100 * actual_lev
                    if pos_side == "SHORT": pnl_pct *= -1
                    pnl_value = (TRADE_CAPITAL_USDT * pnl_pct) / 100
            else:
                # Mode Simulasi: Pantau harga ticker dan eksekusi lokal
                ticker = await asyncio.to_thread(exchange.fetch_ticker, symbol)
                p_now = ticker['last']
                
                # Update PnL untuk Simulasi
                pnl_pct = ((p_now - entry_price) / entry_price) * 100 * actual_lev
                if pos_side == "SHORT": pnl_pct *= -1
                pnl_value = (TRADE_CAPITAL_USDT * pnl_pct) / 100
            
            # --- LOGIKA 3-LAYER TAKE PROFIT ---
            tp1, tp2, tp3 = tp_targets
            
            # 1. TP1: Take 33% and Activate Break-Even
            hit_tp1 = (pos_side == "LONG" and p_now >= tp1) or (pos_side == "SHORT" and p_now <= tp1)
            if not tp1_taken and hit_tp1:
                tp1_taken = True
                be_activated = True
                sl_p = entry_price
                
                amt_to_close = current_contracts / 3
                # Hitung profit dari 1/3 posisi ini
                p1_pct = ((p_now - entry_price) / entry_price) * 100 * actual_lev
                if pos_side == "SHORT": p1_pct *= -1
                realized_pnl_val += (TRADE_CAPITAL_USDT * (1/3) * p1_pct) / 100
                
                add_log(f"🎯 TP1 HIT: Mengunci 33% profit {symbol} & BE Aktif")
                
                if not DRY_RUN:
                    try:
                        await asyncio.to_thread(exchange.create_market_order, symbol, closing_side, amt_to_close, params={'reduceOnly': True})
                        current_contracts -= amt_to_close
                        # Update SL di server
                        await asyncio.to_thread(exchange.cancel_all_orders, symbol)
                        await asyncio.to_thread(
                            exchange.create_order, symbol, 'STOP_MARKET', closing_side, current_contracts, 
                            None, {'stopPrice': sl_p, 'reduceOnly': True, 'workingType': 'CONTRACT_PRICE'}
                        )
                    except Exception as e: add_log(f"Gagal TP1 {symbol}: {e}")
                else:
                    current_contracts -= amt_to_close
                winsound.Beep(1000, 400)

            # 2. TP2: Take another 33% (approx 50% of remaining)
            hit_tp2 = (pos_side == "LONG" and p_now >= tp2) or (pos_side == "SHORT" and p_now <= tp2)
            if tp1_taken and not tp2_taken and hit_tp2:
                tp2_taken = True
                amt_to_close = current_contracts / 2 # Setengah dari sisa (~33% awal)
                # Hitung profit dari bagian ini
                p2_pct = ((p_now - entry_price) / entry_price) * 100 * actual_lev
                if pos_side == "SHORT": p2_pct *= -1
                realized_pnl_val += (TRADE_CAPITAL_USDT * (1/3) * p2_pct) / 100

                add_log(f"🎯 TP2 HIT: Mengunci 33% lagi untuk {symbol}")
                
                if not DRY_RUN:
                    try:
                        await asyncio.to_thread(exchange.create_market_order, symbol, closing_side, amt_to_close, params={'reduceOnly': True})
                        current_contracts -= amt_to_close
                        # Update SL di server untuk sisa kontrak
                        await asyncio.to_thread(exchange.cancel_all_orders, symbol)
                        await asyncio.to_thread(
                            exchange.create_order, symbol, 'STOP_MARKET', closing_side, current_contracts, 
                            None, {'stopPrice': sl_p, 'reduceOnly': True, 'workingType': 'CONTRACT_PRICE'}
                        )
                    except Exception as e: add_log(f"Gagal TP2 {symbol}: {e}")
                else:
                    current_contracts -= amt_to_close
                winsound.Beep(1200, 400)

            # 3. TP3: Final Target (Close Remaining)
            hit_tp3 = (pos_side == "LONG" and p_now >= tp3) or (pos_side == "SHORT" and p_now <= tp3)
            if (tp2_taken or (tp1_taken and momentum)) and hit_tp3:
                add_log(f"🚀 TP3 HIT: Target Maksimal {symbol} tercapai!")
                if not DRY_RUN:
                    try:
                        await asyncio.to_thread(exchange.cancel_all_orders, symbol)
                        await asyncio.to_thread(exchange.create_market_order, symbol, closing_side, current_contracts, params={'reduceOnly': True})
                    except: pass
                
                pnl_pct = ((p_now - entry_price) / entry_price) * 100 * actual_lev
                if pos_side == "SHORT": pnl_pct *= -1
                # Final part (33% sisa)
                final_pnl_val = (TRADE_CAPITAL_USDT * (current_contracts/original_contracts) * pnl_pct) / 100
                total_pnl_val = realized_pnl_val + final_pnl_val
                
                save_trade_history(symbol, pos_side, entry_price, p_now, pnl_pct, total_pnl_val, "WIN")
                winsound.Beep(1500, 600)
                del active_trades[symbol]
                break

            # --- DYNAMIC TRAILING STOP LOSS (TSL) ---
            if pnl_pct >= TSL_ACTIVATION_PCT:
                tsl_active = True
                if pos_side == "LONG":
                    highest_price = max(highest_price, p_now)
                    # SL mengekor 5% di bawah harga tertinggi yang pernah dicapai
                    trail_sl = highest_price * (1 - (TSL_DISTANCE_PCT / 100))
                    if trail_sl > sl_p:
                        sl_p = trail_sl
                        add_log(f"🛡️ TSL {symbol} naik ke {sl_p:,.4f}")
                else:
                    lowest_price = min(lowest_price, p_now) if lowest_price > 0 else p_now
                    # SL mengekor 5% di atas harga terendah yang pernah dicapai
                    trail_sl = lowest_price * (1 + (TSL_DISTANCE_PCT / 100))
                    if trail_sl < sl_p:
                        sl_p = trail_sl
                        add_log(f"🛡️ TSL {symbol} turun ke {sl_p:,.4f}")

            # --- STOP LOSS / BE / TSL PROTECTION ---
            hit_sl = (pos_side == "LONG" and p_now <= sl_p) or (pos_side == "SHORT" and p_now >= sl_p)
            if hit_sl:
                res = "TSL-EXIT" if tsl_active else "BE-EXIT" if be_activated else "LOSS"
                add_log(f"💥 {symbol} Exit: {res}")
                if not DRY_RUN:
                    try:
                        await asyncio.to_thread(exchange.cancel_all_orders, symbol)
                        await asyncio.to_thread(exchange.create_market_order, symbol, closing_side, current_contracts, params={'reduceOnly': True})
                    except: pass
                
                pnl_pct = ((p_now - entry_price) / entry_price) * 100 * actual_lev
                if pos_side == "SHORT": pnl_pct *= -1
                # Profit dari sisa kontrak yang masih ada
                final_pnl_val = (TRADE_CAPITAL_USDT * (current_contracts/original_contracts) * pnl_pct) / 100
                total_pnl_val = realized_pnl_val + final_pnl_val
                
                save_trade_history(symbol, pos_side, entry_price, p_now, pnl_pct, total_pnl_val, res)
                winsound.Beep(400, 500)
                del active_trades[symbol]
                break

            active_trades[symbol] = {
                'side': pos_side, 'entry': entry_price, 'now': p_now, 
                'tp': tp3, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3,
                'sl': sl_p, 'pnl_pct': pnl_pct, 'pnl_val': pnl_value,
                'be_active': be_activated, 'tsl_active': tsl_active,
                'tp1_active': tp1_taken, 'tp2_active': tp2_taken,
                'momentum': momentum
            }
            
            await asyncio.sleep(2)
            
    except Exception as e:
        print(f"\n{G_RED}Error memantau posisi {symbol}: {e}{RESET}")
        if symbol in active_trades: del active_trades[symbol]

async def execute_trade(symbol, signal, tp_targets, sl_target, actual_leverage_manual=None, momentum=False):
    global active_trades
    if symbol in active_trades: return False
    
    # --- FINAL STATUS GUARD ---
    try:
        market = exchange.market(symbol)
        if not market.get('active') or market['info'].get('status') != 'TRADING':
            print(f"\n{G_RED}❌ GAGAL: {symbol} sedang dinonaktifkan atau maintenance oleh Binance. Melewati...{RESET}")
            return False
    except Exception:
        pass # Jika gagal fetch metadata, lanjut (fallback ke error order asli)
    
    try:
        # 1. Ambil Saldo Tersedia (Free Margin)
        bal_dict = await get_balance()
        bal_total = bal_dict['total']
        bal_free = bal_dict['free']
        
        # 2. Hitung Modal Dinamis (Margin)
        final_capital = 0.0
        if AUTO_SCALE_MARGIN:
            calculated_margin = bal_free * (MARGIN_RISK_PCT / 100)
            final_capital = max(calculated_margin, SAFE_FLOOR_USDT)
        else:
            final_capital = TRADE_CAPITAL_USDT
            
        print(f"\n{G_CYN}  🔔 SIGNAL {symbol} DITEMUKAN! Mengeksekusi order...{RESET}")
        
        # Atur Leverage & Margin Type
        actual_leverage = LEVERAGE
        if not DRY_RUN:
            try:
                await asyncio.to_thread(exchange.set_margin_mode, "ISOLATED", symbol)
            except Exception: pass
            
            # Gunakan helper set_leverage agar ada fallback jika 50x ditolak
            res_lev = await set_leverage(symbol, LEVERAGE)
            if res_lev == 0: return False # Gagal set leverage sama sekali
            actual_leverage = res_lev
        else:
            print(f"  🤖 {G_CYN}[SIMULASI]{RESET} Leverage diatur ke {LEVERAGE}x untuk {symbol}")
            
        # 3. SAFETY CHECKS
        # Jangan entry jika dana bebas sangat sedikit
        if bal_free < 0.5:
            print(f"{G_RED}❌ SALDO BEBAS TERLALU RENDAH (${bal_free:.2f}). Melewati {symbol}...{RESET}")
            return False
            
        # Jangan entry jika modal lebih besar dari dana yang tersedia
        if final_capital > bal_free:
            final_capital = bal_free * 0.95 # Gunakan 95% dari sisa saldo agar aman dari fee
        
        # Kalkulasi Qty berdasarkan modal yang sudah dihitung (final_capital)
        ticker = await asyncio.to_thread(exchange.fetch_ticker, symbol)
        price_now = ticker['last']
        
        # --- AUTO-CALCULATE TP/SL IF EMPTY (For Snipe Mode) ---
        if not tp_targets or sl_target == 0:
            df = await fetch_ohlcv(symbol, TIMEFRAME_EXEC)
            if df is not None:
                atr_val = df['atr'].iloc[-1]
                tp1 = price_now + (atr_val * 1.0) if signal == "LONG" else price_now - (atr_val * 1.0)
                tp2 = price_now + (atr_val * 2.0) if signal == "LONG" else price_now - (atr_val * 2.0)
                tp3 = price_now + (atr_val * 3.5) if signal == "LONG" else price_now - (atr_val * 3.5)
                tp_targets = [tp1, tp2, tp3]
                sl_target = price_now - (atr_val * 2.0) if signal == "LONG" else price_now + (atr_val * 2.0)
            else:
                # Fallback
                dist = 0.015
                tp1 = price_now * (1 + dist) if signal == "LONG" else price_now * (1 - dist)
                tp2 = price_now * (1 + dist*2) if signal == "LONG" else price_now * (1 - dist*2)
                tp3 = price_now * (1 + dist*3) if signal == "LONG" else price_now * (1 - dist*3)
                tp_targets = [tp1, tp2, tp3]
                sl_target = price_now * (1 - 0.02) if signal == "LONG" else price_now * (1 + 0.02)

        amount = (final_capital * actual_leverage) / price_now
        
        # Pembulatan amount agar tidak melebihi margin (Precision handling)
        # Sederhananya, kita buang desimal berlebih sesuai koinnya (rata-rata koin butuh integer atau 1-3 desimal)
        amount = floor(amount * 1000) / 1000  # Fallback 3 desimal
        
        print(f"  🔔 MENGEKSEKUSI {signal} UNTUK {G_WHT}{symbol}{RESET} PADA {G_YLW}{price_now:,.4f}{RESET}")
        print(f"  Target TP1: {G_GRN}{tp_targets[0]:,.4f}{RESET} | TP2: {G_GRN}{tp_targets[1]:,.4f}{RESET} | TP3: {G_GRN}{tp_targets[2]:,.4f}{RESET}")
        print(f"  Target SL: {G_RED}{sl_target:,.4f}{RESET}")
        print(f"  Membuka posisi {signal} di server... (Modal: ${final_capital:.2f})")
        
        # Mapping Side: LONG -> buy, SHORT -> sell (Wajib untuk Binance)
        side_mapped = 'buy' if signal == "LONG" else 'sell'
        closing_side = 'sell' if signal == "LONG" else 'buy'
        
        if DRY_RUN:
            print(f"{G_YLW}🤖 [SIMULASI] Membuka posisi {signal} sejumlah {amount:.4f} {symbol.split('/')[0]}{RESET}")
            # Simpan ke memori trade aktif
            active_trades[symbol] = {
                'side': signal, 'entry': price_now, 'now': price_now, 
                'tp1': tp_targets[0], 'tp2': tp_targets[1], 'tp3': tp_targets[2], 
                'sl': sl_target, 'pnl_pct': 0, 'pnl_val': 0,
                'be_active': False, 'tsl_active': False
            }
            winsound.Beep(1200, 300)
            
            # Jalankan task monitoring di latar belakang
            asyncio.create_task(monitor_position(symbol, price_now, amount, signal, tp_targets, sl_target, actual_leverage))
            return True
            
        else:
            try:
                print(f"{G_YLW}Membuka posisi {signal} di server...{RESET}")
                order_res = await asyncio.to_thread(exchange.create_order, symbol, 'MARKET', side_mapped, amount)
                
                # Gunakan harga eksekusi asli dari Binance (Slippage handling)
                actual_entry = order_res.get('average') or order_res.get('price') or price_now
                print(f"{G_GRN}✅ Posisi Entry {signal} berhasil dibuka pada harga {actual_entry:,.4f}!{RESET}")
                
                # --- MENGIRIM ORDER TP & SL LIMIT KE BINANCE SERVER ---
                print(f"{G_YLW}Mengirim order Take Profit & Stop Loss ke server...{RESET}")
                
                # Stop Loss Market
                await asyncio.to_thread(
                    exchange.create_order, symbol, 'STOP_MARKET', closing_side, amount, 
                    None, {'stopPrice': sl_target, 'reduceOnly': True, 'workingType': 'CONTRACT_PRICE'}
                )
                
                # Take Profit Market
                await asyncio.to_thread(
                    exchange.create_order, symbol, 'TAKE_PROFIT_MARKET', closing_side, amount, 
                    None, {'stopPrice': tp_targets[2], 'reduceOnly': True}
                )
                
                print(f"{G_GRN}✅ Order TP & SL berhasil dipasang di server!{RESET}")
                winsound.Beep(1200, 300)
                
                active_trades[symbol] = {
                    'side': signal, 'entry': actual_entry, 'now': actual_entry, 
                    'tp1': tp_targets[0], 'tp2': tp_targets[1], 'tp3': tp_targets[2],
                    'sl': sl_target, 'pnl_pct': 0, 'pnl_val': 0,
                    'be_active': False, 'tsl_active': False
                }
                
                # Jalankan pemantauan pasif
                asyncio.create_task(monitor_position(symbol, actual_entry, amount, signal, tp_targets, sl_target, actual_leverage, momentum))
                return True
                
            except Exception as e:
                print(f"\n{G_RED}❌ GAGAL MENGEKSEKUSI TRADE {symbol}: {e}{RESET}")
                return False

    except Exception as e:
        print(f"\n{G_RED}Kesalahan eksekusi untuk {symbol}: {e}{RESET}")
        return False


async def close_all_positions():
    """Menutup semua posisi aktif dan membatalkan semua order di Binance."""
    global active_trades
    if not active_trades:
        print(f"\n {G_YLW}Tidak ada posisi aktif untuk ditutup.{RESET}")
        return

    print(f"\n {G_RED}🛑 EMERGENCY: MENUTUP SEMUA POSISI...{RESET}")
    symbols = list(active_trades.keys())
    
    for symbol in symbols:
        try:
            trade = active_trades.get(symbol)
            if not trade: continue
            
            side = trade['side']
            closing_side = 'sell' if side == "LONG" else 'buy'
            
            if not DRY_RUN:
                # 1. Batalkan semua order (TP/SL)
                await asyncio.to_thread(exchange.cancel_all_orders, symbol)
                # 2. Ambil sisa kontrak
                pos = await get_position(symbol)
                if pos:
                    amount = float(pos['contracts'])
                    # 3. Tutup dengan Market Order
                    await asyncio.to_thread(exchange.create_market_order, symbol, closing_side, amount, params={'reduceOnly': True})
            
            add_log(f"🛑 {symbol} Ditutup Paksa via Emergency Stop")
            # Force trigger monitor_position exit by removing from dict
            if symbol in active_trades: del active_trades[symbol]
            
        except Exception as e:
            print(f" Gagal menutup {symbol}: {e}")
    
    print(f" {G_GRN}✅ Semua posisi telah ditutup.{RESET}")
    winsound.Beep(400, 1000)
    await asyncio.sleep(1)

# =================================================================
# 📜 HISTORY & STATS MODULE
# =================================================================
HISTORY_FILE = "trade_history.json"

def load_local_stats():
    """Membaca file history dan memuat total win/loss saat bot dijalankan."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
                if not history: return
                stats['wins'] = sum(1 for trade in history if trade.get('result') == 'WIN')
                stats['losses'] = sum(1 for trade in history if trade.get('result') == 'LOSS')
                # Safe access untuk PnL terakhir
                last_trade = history[-1]
                stats['last_pnl'] = last_trade.get('pnl_value') or last_trade.get('pnl_val', 0.0)
        except Exception as e:
            print(f"Error loading history: {e}")

def save_trade_history(symbol, pos_side, entry_price, close_price, pnl_pct, pnl_value, result):
    """Menyimpan data trading yang sudah selesai ke file JSON."""
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        except Exception:
            pass
            
    trade_record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": symbol,
        "side": pos_side,
        "entry_price": entry_price,
        "close_price": close_price,
        "pnl_pct": pnl_pct,
        "pnl_value": pnl_value, # Standarisasi ke pnl_value
        "result": result,
        "mode": "SIMULASI" if DRY_RUN else "LIVE"
    }
    
    history.append(trade_record)
    
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=4)
            
        # Update stats saat ini agar tampilan di header Menu langsung terganti
        if result == 'WIN':
            stats['wins'] += 1
        elif result == 'LOSS':
            stats['losses'] += 1
        stats['last_pnl'] = pnl_value
    except Exception as e:
        print(f"Error saving history: {e}")

async def view_trade_history():
    """Menampilkan rekapan trading di tampilan Menu"""
    clear_screen()
    
    def print_empty_history():
        print(f"{G_CYN}╔═════════════════════════════════════════════════════════════════════════════════════╗{RESET}")
        print(f"{G_CYN}║{G_WHT}{G_BOLD}                                📜 TRADE HISTORY RECAP                               {G_CYN}║{RESET}")
        print(f"{G_CYN}╠═════════════════════════════════════════════════════════════════════════════════════╣{RESET}")
        print(f"{G_CYN}║ {G_YLW}{'Belum ada riwayat trading yang tersimpan.':^83}{G_CYN} ║{RESET}")
        print(f"{G_CYN}╚═════════════════════════════════════════════════════════════════════════════════════╝{RESET}\n")

    if not os.path.exists(HISTORY_FILE):
        print_empty_history()
    else:
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
                
            if not history:
                print_empty_history()
            else:
                full_ui = []
                full_ui.append(f"{G_CYN}╔═════════════════════════════════════════════════════════════════════════════════════╗{RESET}")
                full_ui.append(f"{G_CYN}║{G_WHT}{G_BOLD}                                📜 TRADE HISTORY RECAP                               {G_CYN}║{RESET}")
                full_ui.append(f"{G_CYN}╠══════════════════════╤═════════════════╤═══════╤═══════════╤═══════════╤════════════╣{RESET}")
                full_ui.append(f"{G_CYN}║ {G_WHT}{'TANGGAL':<20} │ {'SYMBOL':<15} │ {'SIDE':<5} │ {'PnL %':<9} │ {'PnL USDT':<9} │ {'RESULT':<10}{G_CYN} ║{RESET}")
                full_ui.append(f"{G_CYN}╠══════════════════════╪═════════════════╪═══════╪═══════════╪═══════════╪════════════╣{RESET}")
                
                # Menampilkan 15 data trade terakhir
                for trade in history[-15:]:
                    res_col = G_GRN if trade.get('result') == 'WIN' else G_RED
                    pnl_col = G_GRN if trade.get('pnl_pct', 0) >= 0 else G_RED
                    pnl_pct_str = f"{trade.get('pnl_pct', 0):>+7.2f}%"
                    val = trade.get('pnl_value') if trade.get('pnl_value') is not None else trade.get('pnl_val', 0)
                    pnl_val_str = f"{val:>+8.2f}"
                    full_ui.append(f"{G_CYN}║ {G_WHT}{trade['timestamp']:<20} {G_CYN}│ {G_WHT}{trade['symbol']:<15} {G_CYN}│ {G_WHT}{trade['side']:<5} {G_CYN}│ {pnl_col}{pnl_pct_str:<9}{G_CYN} │ {pnl_col}{pnl_val_str:<9}{G_CYN} │ {res_col}{trade['result']:<10}{G_CYN} ║{RESET}")
                    
                total_pnl = sum(t.get('pnl_value') if t.get('pnl_value') is not None else t.get('pnl_val', 0) for t in history)
                total_win = sum(1 for t in history if t.get('result') == 'WIN')
                total_loss = sum(1 for t in history if t.get('result') == 'LOSS')
                
                full_ui.append(f"{G_CYN}╠══════════════════════╧═════════════════╧═══════╧═══════════╧═══════════╧════════════╣{RESET}")
                pnl_str = f"${total_pnl:.2f}"
                pnl_color = G_GRN if total_pnl >= 0 else G_RED
                full_ui.append(f"{G_CYN}║ {G_WHT}Total PnL : {pnl_color}{pnl_str:<15}{G_CYN}{' ' * 56} ║{RESET}")
                full_ui.append(f"{G_CYN}║ {G_WHT}Total Win : {G_GRN}{total_win:<15}{G_CYN}{' ' * 56} ║{RESET}")
                full_ui.append(f"{G_CYN}║ {G_WHT}Total Loss: {G_RED}{total_loss:<15}{G_CYN}{' ' * 56} ║{RESET}")
                full_ui.append(f"{G_CYN}╚═════════════════════════════════════════════════════════════════════════════════════╝{RESET}")
                
                clear_screen()
                print("\n".join(full_ui))
        except Exception as e:
            print(f" {G_RED}Gagal membaca history: {e}{RESET}")
            
    prompt = f"\n {G_YLW}Tekan '1' untuk HAPUS SEMUA | Enter: Kembali ❯ {RESET}"
    choice = await asyncio.to_thread(input, prompt)
    
    if choice == '1':
        if os.path.exists(HISTORY_FILE):
            try:
                os.remove(HISTORY_FILE)
                # Reset Global Stats agar header di Menu Utama ikut nol
                stats['wins'] = 0
                stats['losses'] = 0
                stats['last_pnl'] = 0.0
                print(f"\n {G_GRN}✅ Semua riwayat trading telah dihapus!{RESET}")
                winsound.Beep(800, 500)
            except Exception as e:
                print(f" {G_RED}Gagal menghapus file: {e}{RESET}")
        else:
            print(f"\n {G_YLW}Tidak ada riwayat untuk dihapus.{RESET}")
        await asyncio.sleep(1.5)

# =================================================================
# 📈 ANALYTICS & TOP MOVERS
# =================================================================
async def top_movers_view():
    """Layar khusus untuk menampilkan koin dengan pergerakan harga & volume tertinggi."""
    while True:
        clear_screen()
        bal = await get_balance()
        draw_header(bal)
        
        print(f"{G_CYN}╠{'═' * 30}[ TOP MOVERS ]{'═' * 41}╣{RESET}")
        
        items = [
            f"  {G_YLW}Pilih Kategori:{RESET}",
            f"  {G_GRN}[1] 🚀 BULLISH LIST (Tabel Harga Naik){RESET}",
            f"  {G_RED}[2] 📉 BEARISH LIST (Tabel Harga Turun){RESET}",
            f"  {G_GRN}[3] ⚡ SNIPE TOP BULLISH (Auto-Entry #1){RESET}",
            f"  {G_RED}[4] ⚡ SNIPE TOP BEARISH (Auto-Entry #1){RESET}",
            f"  {G_WHT}[0] Kembali ke Menu Utama{RESET}"
        ]
        
        for item in items:
            iv = get_visual_width(item)
            padding = " " * (85 - iv)
            print(f"{G_CYN}║{item}{padding}║{RESET}")

        print(f"{G_CYN}╚{'═' * 85}╝{RESET}")
        
        choice = await asyncio.to_thread(input, f"\n {G_WHT}Pilih ❯ {RESET}")
        if choice == '0': break
        if choice not in ['1', '2', '3', '4']: continue
        
        # Mode: 1/3 = Bullish, 2/4 = Bearish
        mode = "BULLISH" if choice in ['1', '3'] else "BEARISH"
        is_sniper = choice in ['3', '4']
        
        # Progress indicator
        print(f"\n {G_CYN}⏳ Mengambil data real-time dari Binance...{RESET}")
        
        try:
            tickers = await asyncio.to_thread(exchange.fetch_tickers)
            valid_coins = []
            for symbol, t in tickers.items():
                if symbol.endswith(':USDT') and t.get('quoteVolume') is not None:
                    # Filter: Hanya koin yang berstatus TRADING / Aktif
                    try:
                        mk = exchange.market(symbol)
                        if not mk.get('active') or mk['info'].get('status') != 'TRADING':
                            continue
                    except: continue

                    valid_coins.append({
                        'symbol': symbol,
                        'change': (t.get('percentage') or 0),
                        'vol': (t.get('quoteVolume') or 0),
                        'price': (t.get('last') or 0)
                    })
            
            # Algorithm Sync: Binance Top Movers style
            # 1. Ambil koin likuid dulu (150 koin teratas berdasar volume)
            liquid_pool = sorted(valid_coins, key=lambda x: x['vol'], reverse=True)[:150]
            
            # 2. Urutkan berdasarkan % Change dari pool likuid tersebut
            if mode == "BULLISH":
                # Kenaikan tertinggi di atas
                sorted_coins = sorted(liquid_pool, key=lambda x: x['change'], reverse=True)[:15]
            else:
                # Penurunan terdalam di atas
                sorted_coins = sorted(liquid_pool, key=lambda x: x['change'])[:15]

            # --- LOGIKA SMART SNIPER MODE ---
            if is_sniper:
                if not sorted_coins:
                    print(f"\n {G_RED}❌ GAGAL: Tidak ditemukan koin yang sesuai kriteria sniping.{RESET}")
                    await asyncio.sleep(2); continue
                
                target_side = "LONG" if mode == "BULLISH" else "SHORT"
                found_target = None
                
                print(f" {G_YLW}⚡ Menganalisa Top 5 koin {mode} untuk sinyal {target_side} valid...{RESET}")
                for i in range(min(5, len(sorted_coins))):
                    candidate = sorted_coins[i]
                    sym = candidate['symbol']
                    sig, tp_targets, sl_tgt = await analyze_signal(sym, momentum=True)
                    
                    if sig == target_side:
                        found_target = (sym, sig, tp_targets, sl_tgt, candidate)
                        break
                
                if not found_target:
                    print(f" {G_RED}❌ GAGAL SNIPE: Tidak ditemukan sinyal {target_side} valid di Top 5 koin.{RESET}")
                    print(f" {G_YLW} (Koin teratas mungkin sudah jenuh atau sedang koreksi/reversal){RESET}")
                    await asyncio.sleep(4); continue
                    
                sym, side, tp_targets, sl_tgt, selected = found_target
                print(f"\n {G_YLW}🎯 SNIPER FOUND: Menembak {sym} ({selected['change']:+.2f}%) Sinyal: {side}{RESET}")
                
                # Safety Guard Sniper
                if len(active_trades) >= MAX_CONCURRENT_TRADES:
                    print(f" {G_RED}❌ GAGAL: Slot trading penuh ({MAX_CONCURRENT_TRADES}).{RESET}")
                    await asyncio.sleep(2); continue
                
                req_cap = 5.5 if "BTC" in sym else TRADE_CAPITAL_USDT
                if bal.get('free', 0) < (req_cap * 1.05):
                    print(f" {G_RED}❌ GAGAL: Saldo tidak cukup untuk sniping.{RESET}")
                    await asyncio.sleep(2); continue
                
                # Eksekusi instan
                success = await execute_trade(sym, side, tp_targets, sl_tgt, momentum=True)
                if success:
                    print(f"{G_GRN}🎯 Sniper sukses! Masuk ke layar monitoring...{RESET}")
                    await asyncio.sleep(1)
                    scan_mode = "PUMP" if mode == "BULLISH" else "DUMP"
                    await global_scanner(mode=scan_mode, momentum=True)
                    return
                else:
                    await asyncio.sleep(2); continue
                
            # Layar Hasil (Normal Mode)
            while True:
                total_pnl = sum(t.get('pnl_val', 0) for t in active_trades.values())
                
                full_ui = []
                full_ui.append(draw_header(bal, live_pnl=total_pnl, return_str=True))
                
                title = f" TOP {mode} MOVERS (BINANCE STYLE) "
                side_p = (85 - len(title)) // 2
                full_ui.append(f"{G_CYN}╔{'═' * side_p}{G_WHT}{title}{G_CYN}{'═' * (85 - side_p - len(title))}╗{RESET}")
                full_ui.append(f"{G_CYN}║ {'NO':<4} │ {'SYMBOL':<22} │ {'PRICE':<15} │ {'CHANGE':<10} │ {'VOLUME (USDT)':<20} ║{RESET}")
                full_ui.append(f"{G_CYN}╠{'═' * 6}╪{'═' * 24}╪{'═' * 17}╪{'═' * 12}╪{'═' * 22}╣{RESET}")
                
                for i, c in enumerate(sorted_coins):
                    sym = c['symbol']
                    chg_col = G_GRN if c['change'] >= 0 else G_RED
                    vol_fmt = f"${c['vol']:,.0f}"
                    
                    slot_full = len(active_trades) >= MAX_CONCURRENT_TRADES
                    is_holding = sym in active_trades
                    req_cap = 5.5 if "BTC" in sym else TRADE_CAPITAL_USDT
                    low_bal = bal.get('free', 0) < (req_cap * 1.05)
                    
                    status = ""
                    if is_holding: status = f"{G_CYN}[HOLDING]{RESET}"
                    elif slot_full: status = f"{G_YLW}[FULL]{RESET}"
                    elif low_bal: status = f"{G_RED}[LOW BAL]{RESET}"
                    
                    s_disp = f"{sym.split('/')[0][:12]} {status}"
                    s_v = get_visual_width(s_disp)
                    c2_text = f"{s_disp}{' ' * (22 - s_v)}"
                    
                    line = f" {i+1:<4} │ {c2_text} │ {c['price']:<15,.4f} │ {chg_col}{c['change']:>+8.2f}%{RESET} │ {G_WHT}{vol_fmt:<20}{RESET} "
                    full_ui.append(f"{G_CYN}║{line}║{RESET}")
                
                full_ui.append(f"{G_CYN}╚{'═' * 6}╧{'═' * 24}╧{'═' * 17}╧{'═' * 12}╧{'═' * 22}╝{RESET}")
                full_ui.append(f"\n {G_YLW}(Masukkan No. Koin untuk Trading | Enter: Refresh | 0: Ganti Kategori){RESET}")
                
                clear_screen()
                print("\n".join(full_ui))
                
                sub_choice = await asyncio.to_thread(input, f" {G_WHT}Aksi/No ❯ {RESET}")
                if sub_choice == '0': break
                
                # Cek jika input adalah angka untuk memilih koin
                if sub_choice.isdigit():
                    idx = int(sub_choice) - 1
                    if 0 <= idx < len(sorted_coins):
                        selected = sorted_coins[idx]
                        sym = selected['symbol']
                        
                        # Guard Layer
                        if sym in active_trades:
                            print(f"\n {G_RED}❌ GAGAL: {sym} sudah ada dalam posisi aktif! {RESET}")
                            await asyncio.sleep(2); continue
                            
                        if len(active_trades) >= MAX_CONCURRENT_TRADES:
                            print(f"\n {G_YLW}⚠️ SLOT PENUH (Maks {MAX_CONCURRENT_TRADES}). Tunggu trade lain selesai.{RESET}")
                            await asyncio.sleep(2); continue
                            
                        req_cap = 5.5 if "BTC" in sym else TRADE_CAPITAL_USDT
                        if bal.get('free', 0) < (req_cap * 1.05):
                            print(f"\n {G_RED}❌ SALDO MARGIN TIDAK CUKUP (Aman: {req_cap*1.05:.2f} USDT).{RESET}")
                            await asyncio.sleep(2); continue

                        side = "LONG" if mode == "BULLISH" else "SHORT"
                        print(f"\n {G_YLW}Menganalisa {sym} untuk entry {side} (MOMENTUM MODE)...{RESET}")
                        sig, tp_targets, sl_tgt = await analyze_signal(sym, momentum=True)
                        
                        if sig != side:
                            print(f" {G_RED}❌ GAGAL: Sinyal EMA saat ini ({sig}) tidak mendukung {side}.{RESET}")
                            print(f" {G_YLW} (Koin teratas mungkin sedang dalam fase koreksi/reversal){RESET}")
                            await asyncio.sleep(4); continue
                            
                        # Fallback TP/SL
                        if not tp_targets or sl_tgt == 0:
                            p = selected['price']
                            dist = 0.025 # Lebih lebar untuk momentum
                            tp1 = p * (1 + dist) if side == "LONG" else p * (1 - dist)
                            tp2 = p * (1 + dist * 2) if side == "LONG" else p * (1 - dist * 2)
                            tp3 = p * (1 + dist * 3) if side == "LONG" else p * (1 - dist * 3)
                            tp_targets = [tp1, tp2, tp3]
                            sl_tgt = p * (1 - dist) if side == "LONG" else p * (1 + dist)
                        
                        success = await execute_trade(sym, side, tp_targets, sl_tgt, momentum=True)
                        if success:
                            print(f"{G_YLW}Membuka layar monitoring & Auto-Scanner...{RESET}")
                            await asyncio.sleep(1)
                            # Pass mode ke scanner: Bullish -> PUMP, Bearish -> DUMP
                            scan_mode = "PUMP" if mode == "BULLISH" else "DUMP"
                            await global_scanner(mode=scan_mode, momentum=True)
                            return 
                        else:
                            await asyncio.sleep(2); continue
                
                # Jika bukan angka dan bukan 0, asumsikan refresh
                if not sub_choice:
                    break # Pecah loop inner ke fetch data baru
                
                continue
                
        except Exception as e:
            print(f"{G_RED}Error mengambil Top Movers: {e}{RESET}")
            await asyncio.sleep(2)

# =================================================================
# 📊 UI & MENU UTAMA
# =================================================================
async def global_scanner(mode="MIXED", momentum=False):
    spinner_frames = ['|', '/', '-', '\\']
    sp_idx = 0
    
    while True:
        # --- CHECK: JIKA SLOT PENUH, MASUK KE MODE MONITORING FOKUS ---
        if len(active_trades) >= MAX_CONCURRENT_TRADES:
            bal = await get_balance()
            live_pnl = sum(t['pnl_val'] for t in active_trades.values())
            
            full_ui = []
            hdr = draw_header(bal, live_pnl, return_str=True)
            if hdr: full_ui.append(hdr)
            
            act = draw_active_trades(return_str=True)
            if act: full_ui.append(act)
            
            full_ui.append(f"\n {G_WHT}Update harga otomatis dalam 2 detik...{RESET}")
            full_ui.append(f" {G_RED} {G_BOLD}(Tekan '0' untuk TUTUP SEMUA & Kembali){RESET}")
            
            clear_screen()
            print("\n".join(full_ui))
            
            start_time = time.time()
            close_triggered = False
            while time.time() - start_time < 2.0:
                if msvcrt.kbhit():
                    if msvcrt.getch().decode('utf-8', 'ignore') == '0':
                        close_triggered = True; break
                await asyncio.sleep(0.1)
            
            if close_triggered:
                await close_all_positions()
                return # Stop everything
            continue

        # --- MODE SCANNER ---
        try:
            # Mengurangi flicker: Fetch data secara background tanpa hapus layar dulu
            current_free_bal = await get_balance()
            tickers = await asyncio.to_thread(exchange.fetch_tickers)
            valid_coins = []
            
            for symbol, t in tickers.items():
                if symbol.endswith(':USDT') and t.get('quoteVolume') is not None:
                    # Filter koin aktif
                    try:
                        mk = exchange.market(symbol)
                        if not mk.get('active') or mk['info'].get('status') != 'TRADING':
                            continue
                    except: continue

                    valid_coins.append({
                        'symbol': symbol, 
                        'vol': (t.get('quoteVolume') or 0), 
                        'price': (t.get('last') or 0),
                        'change': (t.get('percentage') or 0)
                    })
            
            current_symbols = [c['symbol'] for c in valid_coins]
            # Algorithm Sync: Binance style % Change priority
            liquid_pool = sorted(valid_coins, key=lambda x: x['vol'], reverse=True)[:150]
            
            if mode == "PUMP":
                # Cari koin naik (Top Gainers) - Descending
                top_coins = sorted(liquid_pool, key=lambda x: x.get('change', 0), reverse=True)[:25]
            elif mode == "DUMP":
                # Cari koin turun (Top Losers) - Ascending
                top_coins = sorted(liquid_pool, key=lambda x: x.get('change', 0))[:25]
            else:
                # Mode MIXED: Cari volatilitas tertinggi (Absolut)
                top_coins = sorted(liquid_pool, key=lambda x: abs(x.get('change', 0)), reverse=True)[:25]
            
            top_symbols = [c['symbol'] for c in top_coins]
            for z_sym in ZERO_FEE_LIST:
                if z_sym in current_symbols and z_sym not in top_symbols:
                    z_coin = next((c for c in valid_coins if c['symbol'] == z_sym), None)
                    if z_coin: top_coins.append(z_coin)

            # Analisis Paralel
            analysis_tasks = [analyze_signal(coin['symbol'], momentum=momentum) for coin in top_coins]
            results = await asyncio.gather(*analysis_tasks)
            
            # --- UPDATE DISPLAY (Hanya dilakukan saat data sudah siap) ---
            total_pnl = sum(t.get('pnl_val', 0) for t in active_trades.values())
            
            # --- CALCULATE DYNAMIC UI WIDTH ---
            active_trades_str = ""
            dynamic_width = 87
            if active_trades:
                # Iterate rows to find max width needed
                max_v = 0
                for sym, t in active_trades.items():
                    side_color = G_GRN if t['side'] == "LONG" else G_RED
                    pnl_color = G_GRN if t['pnl_pct'] >= 0 else G_RED
                    be_icon = "🛡️" if t.get('be_active') else "  "
                    tsl_icon = "💎" if t.get('tsl_active') else "  "
                    tp1_tag = "✅" if t.get('tp1_active') else "1️⃣"
                    tp2_tag = "✅" if t.get('tp2_active') else "2️⃣"
                    s_name = f"{sym.split('/')[0][:8]}"
                    c1 = f" {G_WHT}{s_name:<8}{RESET} "
                    c2 = f"{side_color}{t['side'][:1]}{RESET} "
                    c3 = f"{G_CYN}{be_icon}{tsl_icon}{RESET} "
                    c4 = f"PnL:{pnl_color}{t['pnl_pct']:>+4.0f}%{RESET} "
                    prices = f"{G_GRN}{tp1_tag}{f_p(t.get('tp1',0))} {tp2_tag}{f_p(t.get('tp2',0))} 3️⃣{f_p(t.get('tp3',0))}{RESET}"
                    c5 = f" {prices} "
                    c6 = f"{G_RED}SL:{f_p(t['sl'])}{RESET} "
                    c7 = f"{G_YLW}N:{f_p(t['now'])}{RESET} "
                    line = f"{c1}│ {c2}│ {c3}│ {c4}│{c5}│ {c6}│ {c7}"
                    max_v = max(max_v, get_visual_width(line))
                dynamic_width = max(87, max_v + 2)
                active_trades_str = draw_active_trades(return_str=True, width=dynamic_width)

            full_ui = []
            full_ui.append(draw_header(current_free_bal, live_pnl=total_pnl, return_str=True, width=dynamic_width))
            
            INNER_WIDTH = dynamic_width - 2
            scanner_title = " ULTIMATE MIXED SCANNER (25) " if mode == "MIXED" else " MOMENTUM SCANNER " if mode == "PUMP" else " DUMP FINDER "
            t_w = get_visual_width(scanner_title)
            p1 = (INNER_WIDTH - t_w - 2) // 2
            p2 = INNER_WIDTH - t_w - 2 - p1
            
            full_ui.append(f"{G_CYN}╔{'═' * p1}[{G_WHT}{scanner_title}{G_CYN}]{'═' * p2}╗{RESET}")
            full_ui.append(f"{G_CYN}║ {'NO':<4} │ {'SYMBOL':<20} │ {'SIGNAL':<{INNER_WIDTH-31}} ║{RESET}")
            full_ui.append(f"{G_CYN}╠{'═' * 6}╪{'═' * 22}╪{'═' * (INNER_WIDTH-30)}╣{RESET}")
            
            sp = spinner_frames[sp_idx % 4]
            sp_idx += 1
            
            found_signals = []
            for i, coin in enumerate(top_coins):
                sym = coin['symbol']
                sig, tp_targets, sl_tgt = results[i]
                
                c1_text = f" {i+1:<4} "
                c2_base = f" {sym}"
                c2_width = get_visual_width(c2_base)
                c2_text = f"{c2_base}{' ' * max(0, 21 - c2_width)} "
                
                if (sig in ["LONG", "SHORT"]) and len(active_trades) >= MAX_CONCURRENT_TRADES:
                    sig_display = f"{G_YLW}{G_BOLD}MAX TRADES{RESET}"
                elif sym in active_trades:
                    sig_display = f"{G_CYN}{G_BOLD}HOLDING{RESET}"
                else:
                    if sig == "LONG": color = G_GRN
                    elif sig == "SHORT": color = G_RED
                    else: color = G_YLW
                    
                    fee_tag = f" {G_LNR}[0-FEE]{RESET}" if sym in ZERO_FEE_LIST else ""
                    spinner_str = f" {G_YLW}{sp}{RESET}" if sig == "WAIT" else ""
                    sig_display = f"{color}{G_BOLD}{sig}{RESET}{spinner_str}{fee_tag}"
                    
                    if sig in ["LONG", "SHORT"]:
                        req_capital = TRADE_CAPITAL_USDT
                        if "BTC" in sym: req_capital = 5.5
                        if current_free_bal.get('free', 0) < (req_capital * 1.05):
                            sig_display = f"{G_RED}{G_BOLD}LOW BALANCE{RESET}"
                        else:
                            found_signals.append((sym, sig, tp_targets, sl_tgt, req_capital))

                change_24h = coin.get('change', 0)
                trend_label = f" {G_GRN}[PUMP {change_24h:+.1f}%]{RESET}" if change_24h > 3.0 else f" {G_RED}[DUMP {change_24h:+.1f}%]{RESET}" if change_24h < -3.0 else ""
                vol_label = f" {G_LNR}[🔥 VOL]{RESET}" if i < 5 else ""
                
                c3_content = f" {sig_display}{trend_label}{vol_label}"
                c3_width = get_visual_width(c3_content)
                c3_pad = " " * max(0, (INNER_WIDTH - 30) - c3_width)
                full_ui.append(f"{G_CYN}║{c1_text}{G_CYN}│{RESET}{c2_text}{G_CYN}│{RESET}{c3_content}{c3_pad}{G_CYN}║{RESET}")

            full_ui.append(f"{G_CYN}╚{'═' * 6}╧{'═' * 22}╧{'═' * (INNER_WIDTH-30)}╝{RESET}")
            
            if active_trades_str:
                full_ui.append(active_trades_str)

            full_ui.append(f"\n {G_WHT}Refresh otomatis dalam 2 detik...{RESET}")
            full_ui.append(f" {G_RED} {G_BOLD}(Tekan '0' untuk TUTUP SEMUA & Kembali){RESET}")

            clear_screen()
            print("\n".join(full_ui))

            # --- EKSEKUSI OTOMATIS SINYAL YANG DITEMUKAN ---
            for sym, sig, tp_targets, sl_tgt, req_cap in found_signals:
                if len(active_trades) >= MAX_CONCURRENT_TRADES: break
                if sym in active_trades: continue
                
                print(f"\n {G_YLW}⚡ SIGNAL DETECTED: {sig} on {sym}...{RESET}")
                # Langsung eksekusi tanpa tanya (Full Auto mode)
                await execute_trade(sym, sig, tp_targets, sl_tgt, momentum=momentum)
                await asyncio.sleep(1) # Gap antar order
            
            start_time = time.time()
            cancelled = False
            while time.time() - start_time < 2.0:
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8', 'ignore')
                    if key == '0':
                        if active_trades:
                            await close_all_positions()
                        else:
                            print(f"\n {G_YLW}Menghentikan monitor dan kembali ke menu...{RESET}")
                        return # Stop everything
                await asyncio.sleep(0.1)
            
        except Exception as e:
            print(f"\n {G_RED}Error Scanner: {e}{RESET}")
            await asyncio.sleep(3)
            continue

async def main_menu():
    # Load past trades into W/L counter
    load_local_stats()
    
    while True:
        total_pnl = sum(t.get('pnl_val', 0) for t in active_trades.values())
        balance = await get_balance()
        
        full_ui = []
        full_ui.append(draw_header(balance, live_pnl=total_pnl, return_str=True))
        full_ui.append(f"{G_CYN}╠{'═' * 30}[ MENU UTAMA ]{'═' * 41}╣{RESET}")
        
        TABLE_WIDTH = 87
        INNER_WIDTH = TABLE_WIDTH - 2
        
        menus = [
            f" {G_CYN}[1]{RESET} {G_WHT}🚀 GLOBAL SCANNER {G_GRN}(Cari & Trading Otomatis){RESET}",
            f" {G_CYN}[2]{RESET} {G_WHT}🎯 MANUAL TRADE   {G_YLW}(Input Koin Manual){RESET}",
            f" {G_CYN}[3]{RESET} {G_WHT}📈 TOP MOVERS      {G_CYN}(Analisa Volume & Tren){RESET}",
            f" {G_CYN}[4]{RESET} {G_WHT}📜 TRADE HISTORY  {G_LNR}(Lihat Rekap PnL){RESET}",
            f" {G_CYN}[5]{RESET} {G_RED}❌ EXIT{RESET}"
        ]
        
        for m in menus:
            m_width = get_visual_width(m)
            padding = " " * (INNER_WIDTH - m_width)
            full_ui.append(f"{G_CYN}║{m}{padding}║{RESET}")
            
        full_ui.append(f"{G_CYN}╚{'═' * INNER_WIDTH}╝{RESET}")
        
        clear_screen()
        print("\n".join(full_ui))
        
        # Monitor dihapus dari sini agar menu bersih
        
        choice = await asyncio.to_thread(input, f"\n {G_WHT}Pilih Menu ❯ {RESET}")
        
        if choice == "1":
            await global_scanner(mode="MIXED")
        elif choice == "2":
            if len(active_trades) >= MAX_CONCURRENT_TRADES:
                print(f"\n {G_RED}❌ GAGAL: Slot trading penuh ({MAX_CONCURRENT_TRADES}). Tunggu trade lain selesai.{RESET}")
                await asyncio.sleep(2)
                continue
                
            coin = await asyncio.to_thread(input, f" {G_WHT}Masukkan Simbol Koin (Contoh: BTC, ETH) ❯ {RESET}")
            if coin:
                symbol = f"{coin.upper()}/USDT:USDT"
                side_input = await asyncio.to_thread(input, f" {G_WHT}Pilih Posisi (L untuk LONG / S untuk SHORT) [Default: L] ❯ {RESET}")
                side = "SHORT" if side_input.upper() == "S" else "LONG"
                
                sig, tp_targets, sl_tgt = await analyze_signal(symbol)
                # Fallback jika analyze signal tak beri target TP manual
                if not tp_targets or sl_tgt == 0:
                     ticker = await asyncio.to_thread(exchange.fetch_ticker, symbol)
                     p = ticker['last']
                     dist = 0.015
                     tp1 = p * (1 + dist) if side == "LONG" else p * (1 - dist)
                     tp2 = p * (1 + dist*2) if side == "LONG" else p * (1 - dist*2)
                     tp3 = p * (1 + dist*3) if side == "LONG" else p * (1 - dist*3)
                     tp_targets = [tp1, tp2, tp3]
                     sl_tgt = p * (1 - dist) if side == "LONG" else p * (1 + dist)
                
                success = await execute_trade(symbol, side, tp_targets, sl_tgt)
                if success:
                    print(f"{G_YLW}Membuka layar monitoring...{RESET}")
                    await asyncio.sleep(1)
                    await global_scanner()
                else:
                    await asyncio.sleep(3)
        elif choice == "3":
            await top_movers_view()
        elif choice == "4":
            await view_trade_history()
        elif choice == "5":
            break
            break

if __name__ == "__main__":
    try:
        asyncio.run(main_menu())
    except KeyboardInterrupt:
        print(f"\n\n{G_RED}Program dihentikan. Sampai jumpa lagi!{RESET}")
    finally:
        print(f"{G_WHT}Menutup semua koneksi...{RESET}")

import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta

DB_NAME = 'fuel_station_v3.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create specific custom pump tables manually 
    cursor.execute('CREATE TABLE IF NOT EXISTS petrol_pump_2 (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, meter REAL, qr_ac REAL, subsidy REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS petrol_pump_4 (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, meter REAL, qr_ac REAL, subsidy REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS petrol_pump_6 (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, meter REAL, qr_ac REAL, subsidy REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS petrol_pump_7 (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, meter REAL, qr_ac REAL, subsidy REAL)')
    
    cursor.execute('CREATE TABLE IF NOT EXISTS diesel_pump_1 (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, verification_check REAL, subsidy REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS diesel_pump_3 (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, verification_check REAL, subsidy REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS diesel_pump_5 (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, verification_check REAL, subsidy REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS diesel_pump_8 (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, verification_check REAL, subsidy REAL)')
    
    # Price History tracking schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config_prices (
            fuel_type TEXT,
            start_date TEXT,
            end_date TEXT,
            commercial_price REAL,
            PRIMARY KEY (fuel_type, start_date)
        )
    ''')
    
    # Pre-populate baseline history matching your actual schedule structure
    cursor.execute("SELECT COUNT(*) FROM config_prices")
    if cursor.fetchone() == 0:
        cursor.execute("INSERT INTO config_prices VALUES ('petrol', '2026-07-01', '2026-07-08', 3.37)")
        cursor.execute("INSERT INTO config_prices VALUES ('diesel', '2026-07-01', '2026-07-08', 3.97)")
        cursor.execute("INSERT INTO config_prices VALUES ('petrol', '2026-07-09', '2026-07-15', 3.37)")
        cursor.execute("INSERT INTO config_prices VALUES ('diesel', '2026-07-09', '2026-07-15', 3.97)")
        
    cursor.execute('CREATE TABLE IF NOT EXISTS receipt_counter (last_id INTEGER PRIMARY KEY)')
    cursor.execute("SELECT COUNT(*) FROM receipt_counter")
    if cursor.fetchone() == 0:
        cursor.execute("INSERT INTO receipt_counter (last_id) VALUES (0)")
    conn.commit()
    conn.close()

def get_price_for_date(fuel_type, date_str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT commercial_price FROM config_prices WHERE fuel_type = ? AND ? BETWEEN start_date AND end_date",
        (fuel_type, date_str[:10])
    )
    res = cursor.fetchone()
    conn.close()
    if res:
        return res[0]
    return 3.37 if fuel_type == 'petrol' else 3.97

def update_weekly_price(fuel_type, start_date, end_date, price):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO config_prices (fuel_type, start_date, end_date, commercial_price) VALUES (?, ?, ?, ?)",
        (fuel_type, start_date, end_date, price)
    )
    conn.commit()
    conn.close()

def get_next_receipt_number(prefix):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT last_id FROM receipt_counter")
    last_id_row = cursor.fetchone()
    last_id = last_id_row[0] if last_id_row else 0
    next_id = last_id + 1
    cursor.execute("UPDATE receipt_counter SET last_id = ?", (next_id,))
    conn.commit()
    conn.close()
    return f"{prefix}-{next_id:06d}"

def get_last_meter_reading(pump_no):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT meter FROM petrol_pump_{pump_no} ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        return result[0] if result else 0.0
    except:
        return 0.0
    finally:
        conn.close()

init_db()

st.set_page_config(page_title="Station POS & Admin Suite", layout="wide")

# Get current system date for processing
pc_now = datetime.now()
current_date_str = pc_now.strftime('%Y-%m-%d')

# Fetch active prices right now
active_market_petrol = get_price_for_date('petrol', current_date_str)
active_market_diesel = get_price_for_date('diesel', current_date_str)

# Clean Navigation Sidebar 
st.sidebar.title("🧭 Station Navigation")
page = st.sidebar.radio("Go to:", ["🛒 Cashier Counter", "📊 Admin Reporting & Prices"])

# ================= PAGE 1: CASHIER COUNTER =================
if page == "🛒 Cashier Counter":
    st.title("⛽ Fuel Transaction Terminal")
    st.caption(f"🕒 **Computer Clock Sync:** {pc_now.strftime('%A, %d %B %Y | %I:%M:%S %p')}")
    
    col_config1, col_config2 = st.columns(2)
    with col_config1:
        fuel_category = st.selectbox("Select Fuel Type", ["Petrol (RON95)", "Diesel"])
    with col_config2:
        if fuel_category == "Petrol (RON95)":
            pump_selection = st.selectbox("Select Pump", [2, 4, 6, 7], format_func=lambda x: f"Pump {x}")
        else:
            pump_selection = st.selectbox("Select Pump", [1, 3, 5, 8], format_func=lambda x: f"Pump {x}")
            
    st.markdown("---")
    col_in1, col_in2 = st.columns(2)
    
    if fuel_category == "Petrol (RON95)":
        with col_in1:
            rate_type = st.radio("Pricing Tier", [f"Normal Market (RM {active_market_petrol:.2f})", "Subsidized (RM 1.99)"])
            harga_applied = 1.99 if "Subsidized" in rate_type else active_market_petrol
            liter = st.number_input("LITER Dispensed", min_value=0.0, step=0.001, format="%.3f")
        with col_in2:
            diisi_rm = st.number_input("Gross Filled Amount (Diisi RM)", min_value=0.0, step=0.01, format="%.2f")
            qr_ac = st.number_input("QR / Card Payment (QR/AC)", min_value=0.0, step=0.01, format="%.2f")
        
        dibayar_rm = round(harga_applied * liter, 1)
        subsidy_rate = round(active_market_petrol - 1.99, 2)
        subsidy = round(abs((liter * subsidy_rate) - qr_ac), 2) if harga_applied == 1.99 else 0.0
        prev_m = get_last_meter_reading(pump_selection)
        calculated_meter = prev_m + liter
        
    else: # Diesel Logic
        with col_in1:
            diisi_rm = st.number_input("Diisi (RM) - From Pump", min_value=0.0, step=0.01, format="%.2f")
            rate_type = st.radio("Pricing Tier", [f"Commercial Market (RM {active_market_diesel:.2f})", "Subsidized (RM 2.15)"])
            harga_applied = 2.15 if "Subsidized" in rate_type else active_market_diesel
        with col_in2:
            st.info("💡 Litres and Subsidy are calculated automatically from Diisi.")
        
        liter = round(diisi_rm / active_market_diesel, 2) if active_market_diesel > 0 else 0.0
        if harga_applied == 2.15:
            dibayar_rm = round(liter * 2.15, 2)
            subsidy = round(diisi_rm - dibayar_rm, 2)
            subsidy_rate = round(active_market_diesel - 2.15, 2)
            v_check = round(abs(liter * subsidy_rate - subsidy), 2)
        else:
            dibayar_rm = diisi_rm
            subsidy = 0.0
            v_check = 0.0
        calculated_meter = 0.0

    st.markdown("### 📊 Live Math Summary")
    cm1, cm2, cm3 = st.columns(3)
    cm1.metric("LITER Volume", f"{liter:.3f} L")
    cm2.metric("Subsidy Amount", f"RM {subsidy:.2f}")
    cm3.metric("DIBAYAR (Amount Due)", f"RM {dibayar_rm:.2f}")
    
    payment_method = st.selectbox("Payment Type Chosen", ["Cash", "Credit Card", "QR Pay"])
    
    if st.button("Submit Order & Log Record", type="primary", use_container_width=True):
        if diisi_rm > 0 or liter > 0:
            prefix = "PET" if "Petrol" in fuel_category else "DSL"
            rcpt = get_next_receipt_number(prefix)
            now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            if prefix == "PET":
                t_name = f"petrol_pump_{pump_selection}"
                cursor.execute(f"INSERT INTO {t_name} (receipt_no, timestamp, diisi_rm, dibayar_rm, harga, liter, meter, qr_ac, subsidy) VALUES (?,?,?,?,?,?,?,?,?)",
                               (rcpt, now_time, diisi_rm, dibayar_rm, harga_applied, liter, calculated_meter, qr_ac, subsidy))
            else:
                t_name = f"diesel_pump_{pump_selection}"
                cursor.execute(f"INSERT INTO {t_name} (receipt_no, timestamp, diisi_rm, dibayar_rm, harga, liter, verification_check, subsidy) VALUES (?,?,?,?,?,?,?,?)",
                               (rcpt, now_time, diisi_rm, dibayar_rm, harga_applied, liter, v_check, subsidy))
                
            conn.commit()
            conn.close()
            st.success(f"✅ Record saved under {t_name.upper()} as receipt {rcpt}!")
        else:
            st.error("Please provide non-zero amounts before saving.")

# ================= PAGE 2: ADMIN LOGS & PRICE SETUP =================
else:
    st.title("⚙️ Operations Configuration & History View")
    
    # 7-Day Cycle Scheduler Splits

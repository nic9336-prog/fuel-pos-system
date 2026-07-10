import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

DB_NAME = 'fuel_station_master.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Created manually without using list loops to prevent syntax errors
    # Create Petrol Pump tables
    cursor.execute('CREATE TABLE IF NOT EXISTS petrol_pump_2 (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, meter REAL, qr_ac REAL, subsidy REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS petrol_pump_4 (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, meter REAL, qr_ac REAL, subsidy REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS petrol_pump_6 (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, meter REAL, qr_ac REAL, subsidy REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS petrol_pump_7 (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, meter REAL, qr_ac REAL, subsidy REAL)')
    
    # Create Diesel Pump tables
    cursor.execute('CREATE TABLE IF NOT EXISTS diesel_pump_1 (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, verification_check REAL, subsidy REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS diesel_pump_3 (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, verification_check REAL, subsidy REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS diesel_pump_5 (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, verification_check REAL, subsidy REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS diesel_pump_8 (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, verification_check REAL, subsidy REAL)')
    
    # System Price Settings table
    cursor.execute('CREATE TABLE IF NOT EXISTS config_prices (fuel_type TEXT PRIMARY KEY, commercial_price REAL)')
    
    # Set starting default values if table is blank
    cursor.execute("SELECT COUNT(*) FROM config_prices")
    if cursor.fetchone() == 0:
        cursor.execute("INSERT INTO config_prices (fuel_type, commercial_price) VALUES ('petrol', 3.37)")
        cursor.execute("INSERT INTO config_prices (fuel_type, commercial_price) VALUES ('diesel', 3.97)")
        
    cursor.execute('CREATE TABLE IF NOT EXISTS receipt_counter (last_id INTEGER PRIMARY KEY)')
    cursor.execute("SELECT COUNT(*) FROM receipt_counter")
    if cursor.fetchone() == 0:
        cursor.execute("INSERT INTO receipt_counter (last_id) VALUES (0)")
    conn.commit()
    conn.close()

def get_current_prices():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT fuel_type, commercial_price FROM config_prices")
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def update_price(fuel_type, new_price):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE config_prices SET commercial_price = ? WHERE fuel_type = ?", (new_price, fuel_type))
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

# Pull dynamically active pricing limits
current_prices = get_current_prices()
MARKET_PETROL = current_prices.get('petrol', 3.37)
MARKET_DIESEL = current_prices.get('diesel', 3.97)

st.set_page_config(page_title="Station POS & Admin Suite", layout="wide")

# Navigation Tabs
tab_cashier, tab_admin = st.tabs(["🛒 Cashier Counter", "📊 Admin Reporting & Setup Dashboard"])

# ================= TAB 1: CASHIER COUNTER =================
with tab_cashier:
    st.title("⛽ Fuel Transaction Terminal")
    
    # Pull current timestamp from your Windows computer clock automatically
    pc_now = datetime.now()
    st.caption(f"🕒 **Computer Clock Sync:** {pc_now.strftime('%A, %d %B %Y | %I:%M:%S %p')}")
    
    col_config1, col_config2 = st.columns(2)
    with col_config1:
        fuel_category = st.selectbox("Select Fuel Type", ["Petrol (RON95)", "Diesel"])
    with col_config2:
        # Custom non-sequential pump numbers explicitly split text-style to protect database routing
        if fuel_category == "Petrol (RON95)":
            pump_selection = st.selectbox("Select Pump", [2, 4, 6, 7], format_func=lambda x: f"Pump {x}")
        else:
            pump_selection = st.selectbox("Select Pump", [1, 3, 5, 8], format_func=lambda x: f"Pump {x}")
        
    st.markdown("---")
    col_in1, col_in2 = st.columns(2)
    
    if fuel_category == "Petrol (RON95)":
        with col_in1:
            rate_type = st.radio("Pricing Tier", [f"Normal Market (RM {MARKET_PETROL:.2f})", "Subsidized (RM 1.99)"])
            harga = 1.99 if "Subsidized" in rate_type else MARKET_PETROL
            liter = st.number_input("LITER Dispensed", min_value=0.0, step=0.001, format="%.3f")
        with col_in2:
            diisi_rm = st.number_input("Gross Filled Amount (Diisi RM)", min_value=0.0, step=0.01, format="%.2f")
            qr_ac = st.number_input("QR / Card Payment (QR/AC)", min_value=0.0, step=0.01, format="%.2f")
        
        # Formula adjustments tracking your spreadsheet layout rules
        dibayar_rm = round(harga * liter, 1)
        subsidy_rate = round(MARKET_PETROL - 1.99, 2)
        subsidy = round(abs((liter * subsidy_rate) - qr_ac), 2) if harga == 1.99 else 0.0
        prev_m = get_last_meter_reading(pump_selection)
        calculated_meter = prev_m + liter
        
    else: # Diesel Logic
        with col_in1:
            diisi_rm = st.number_input("Diisi (RM) - From Pump", min_value=0.0, step=0.01, format="%.2f")
            rate_type = st.radio("Pricing Tier", [f"Commercial Market (RM {MARKET_DIESEL:.2f})", "Subsidized (RM 2.15)"])
            harga = 2.15 if "Subsidized" in rate_type else MARKET_DIESEL
        with col_in2:
            st.info("💡 Litres and Subsidy are calculated automatically from Diisi value input.")
        
        # Replicating your Excel math matrix logic
        liter = round(diisi_rm / MARKET_DIESEL, 2) if MARKET_DIESEL > 0 else 0.0
        if harga == 2.15:
            dibayar_rm = round(liter * 2.15, 2)
            subsidy = round(diisi_rm - dibayar_rm, 2)
            subsidy_rate = round(MARKET_DIESEL - 2.15, 2)
            v_check = round(abs(liter * subsidy_rate - subsidy), 2)
        else:
            dibayar_rm = diisi_rm
            subsidy = 0.0
            v_check = 0.0
        calculated_meter = 0.0

    # UI Feedback Metric Display Cards
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
                               (rcpt, now_time, diisi_rm, dibayar_rm, harga, liter, calculated_meter, qr_ac, subsidy))
            else:
                t_name = f"diesel_pump_{pump_selection}"
                cursor.execute(f"INSERT INTO {t_name} (receipt_no, timestamp, diisi_rm, dibayar_rm, harga, liter, verification_check, subsidy) VALUES (?,?,?,?,?,?,?,?)",
                               (rcpt, now_time, diisi_rm, dibayar_rm, harga, liter, v_check, subsidy))
                
            conn.commit()
            conn.close()
            st.success(f"✅ Record saved into system backend database under {t_name.upper()} as transaction ticket ID {rcpt}!")
        else:
            st.error("Please provide non-zero amounts before saving.")

# ================= TAB 2: ADMIN LOGS & PRICE SETUP =================
with tab_admin:
    st.title("⚙️ Operations Configuration & History View")
    
    # A New Config Sub-Section to control price alterations
    with st.expander("📝 Update Weekly Commercial Market Price Tiers", expanded=False):
        st.subheader("Weekly Fuel Rate Dashboard Manager")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            new_petrol_rate = st.number_input("Set Current Petrol Base Price (RM)", min_value=0.0, value=MARKET_PETROL, step=0.01, format="%.2f")

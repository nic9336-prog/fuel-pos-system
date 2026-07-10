import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

DB_NAME = 'fuel_station_master.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create 4 Petrol Pump tables
    for i in range(1, 5):
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS petrol_pump_{i} (
                id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT,
                diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, meter REAL, qr_ac REAL, subsidy REAL
            )
        ''')
    # Create 4 Diesel Pump tables
    for i in range(1, 5):
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS diesel_pump_{i} (
                id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT,
                diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, verification_check REAL, subsidy REAL
            )
        ''')
    
    # Sequence counter table
    cursor.execute('CREATE TABLE IF NOT EXISTS receipt_counter (last_id INTEGER PRIMARY KEY)')
    cursor.execute("SELECT COUNT(*) FROM receipt_counter")
    if cursor.fetchone() == 0:
        cursor.execute("INSERT INTO receipt_counter (last_id) VALUES (0)")
    conn.commit()
    conn.close()

def get_next_receipt_number(prefix):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT last_id FROM receipt_counter")
    last_id = cursor.fetchone()[0]
    next_id = last_id + 1
    cursor.execute("UPDATE receipt_counter SET last_id = ?", (next_id,))
    conn.commit()
    conn.close()
    return f"{prefix}-{next_id:06d}"

def get_last_meter_reading(pump_no):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f"SELECT meter FROM petrol_pump_{pump_no} ORDER BY id DESC LIMIT 1")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0.0

init_db()

st.set_page_config(page_title="Station POS & Admin Suite", layout="wide")

# Navigation Tabs
tab_cashier, tab_admin = st.tabs(["🛒 Cashier Counter", "📊 Admin Reporting Dashboard"])

# ================= TAB 1: CASHIER COUNTER =================
with tab_cashier:
    st.title("⛽ Fuel Transaction Terminal")
    
    col_config1, col_config2 = st.columns(2)
    with col_config1:
        fuel_category = st.selectbox("Select Fuel Type", ["Petrol (RON95)", "Diesel"])
    with col_config2:
        pump_selection = st.selectbox("Select Pump",)
        
    st.markdown("---")
    
    col_in1, col_in2 = st.columns(2)
    
    if fuel_category == "Petrol (RON95)":
        with col_in1:
            rate_type = st.radio("Pricing Tier", ["Normal Market (RM 3.37)", "Subsidized (RM 1.99)"])
            harga = 1.99 if "Subsidized" in rate_type else 3.37
            liter = st.number_input("LITER Dispensed", min_value=0.0, step=0.001, format="%.3f")
        with col_in2:
            diisi_rm = st.number_input("Gross Filled Amount (Diisi RM)", min_value=0.0, step=0.01, format="%.2f")
            qr_ac = st.number_input("QR / Card Payment (QR/AC)", min_value=0.0, step=0.01, format="%.2f")
        
        # Formulas from Petrol Sheet
        dibayar_rm = round(harga * liter, 1)
        subsidy = round(abs((liter * 1.38) - qr_ac), 2) if harga == 1.99 else 0.0
        prev_m = get_last_meter_reading(pump_selection)
        calculated_meter = prev_m + liter
        
    else: # Diesel logic
        with col_in1:
            diisi_rm = st.number_input("Diisi (RM) - From Pump", min_value=0.0, step=0.01, format="%.2f")
            rate_type = st.radio("Pricing Tier", ["Commercial Market (RM 3.37)", "Subsidized (RM 2.15)"])
            harga = 2.15 if "Subsidized" in rate_type else 3.37
        with col_in2:
            st.info("💡 Litres and Subsidy are calculated automatically from Diisi.")
        
        # Formulas from Diesel Sheet
        liter = round(diisi_rm / 3.97, 2)
        if harga == 2.15:
            dibayar_rm = round(liter * 2.15, 2)
            subsidy = round(diisi_rm - dibayar_rm, 2)
            v_check = round(abs(liter * 1.82 - subsidy), 2)
        else:
            dibayar_rm = diisi_rm
            subsidy = 0.0
            v_check = 0.0
        calculated_meter = 0.0 # Meter logic was not requested on your diesel template

    # Metrics Display
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
            st.success(f"✅ Record saved to {t_name} as {rcpt}!")
        else:
            st.error("Please provide non-zero amounts before saving.")

# ================= TAB 2: ADMIN VIEW & EXCEL EXPORT =================
with tab_admin:
    st.title("📊 Administration & Data Export Panel")
    
    view_fuel = st.radio("Select View Category", ["Petrol Log Matrix", "Diesel Log Matrix"], horizontal=True)
    view_pump = st.selectbox("Select Pump Target Table", [1, 2, 3, 4], format_func=lambda x: f"Pump {x}")
    
    target_table = f"petrol_pump_{view_pump}" if "Petrol" in view_fuel else f"diesel_pump_{view_pump}"
    
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(f"SELECT * FROM {target_table}", conn)
    conn.close()
    
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        
        # Convert to CSV format bytes for clean excel compatibility
        csv_bytes = df.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label=f"📥 Download {target_table.upper()} Data as CSV/Excel",
            data=csv_bytes,
            file_name=f"{target_table}_export_{datetime.now().strftime('%Y%m%d')}.csv",
            mime='text/csv',
            use_container_width=True
        )
    else:
        st.info(f"No records discovered inside the database table: `{target_table}` yet.")

import streamlit as st, sqlite3, pandas as pd
from datetime import datetime, timedelta

DB_NAME = 'fuel_station_v9.db'

def init_db():
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    for i in (2, 4, 6, 7):
        c.execute(f'CREATE TABLE IF NOT EXISTS petrol_pump_{i} (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, meter REAL, qr_ac REAL, subsidy REAL)')
    for i in (1, 3, 5, 8):
        c.execute(f'CREATE TABLE IF NOT EXISTS diesel_pump_{i} (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT, timestamp TEXT, diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, verification_check REAL, subsidy REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS config_prices (fuel_type TEXT, start_date TEXT, end_date TEXT, commercial_price REAL, PRIMARY KEY (fuel_type, start_date))')
    c.execute("SELECT COUNT(*) FROM config_prices")
    if c.fetchone() == 0:
        c.executemany("INSERT INTO config_prices VALUES (?,?,?,?)", [
            ('petrol', '2026-07-01', '2026-07-08', 3.37), ('diesel', '2026-07-01', '2026-07-08', 3.97),
            ('petrol', '2026-07-09', '2026-07-15', 3.37), ('diesel', '2026-07-09', '2026-07-15', 3.97)
        ])
    c.execute('CREATE TABLE IF NOT EXISTS receipt_counter (last_id INTEGER PRIMARY KEY)')
    c.execute("SELECT COUNT(*) FROM receipt_counter")
    if c.fetchone() == 0: c.execute("INSERT INTO receipt_counter VALUES (0)")
    conn.commit(); conn.close()

def get_price_for_date(f_type, d_str):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT commercial_price FROM config_prices WHERE fuel_type = ? AND ? BETWEEN start_date AND end_date", (f_type, d_str[:10]))
    res = c.fetchone(); conn.close()
    return res[0] if res else (3.37 if f_type == 'petrol' else 3.97)

def update_weekly_price(f_type, s_d, e_d, p):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO config_prices VALUES (?, ?, ?, ?)", (f_type, s_d, e_d, p))
    conn.commit(); conn.close()

def get_next_receipt_number(prefix):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT last_id FROM receipt_counter"); last_id_row = c.fetchone()
    last_id = last_id_row[0] if last_id_row else 0
    next_id = last_id + 1
    c.execute("UPDATE receipt_counter SET last_id = ?", (next_id,))
    conn.commit(); conn.close()
    return f"{prefix}-{next_id:06d}"

def get_last_meter_reading(pump_no):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    try:
        c.execute(f"SELECT meter FROM petrol_pump_{pump_no} ORDER BY id DESC LIMIT 1")
        res = c.fetchone()
        return res[0] if res else 0.0
    except: return 0.0
    finally: conn.close()

init_db()
st.set_page_config(page_title="Station POS Suite", layout="wide")
pc_now = datetime.now(); current_date_str = pc_now.strftime('%Y-%m-%d')
active_market_petrol = get_price_for_date('petrol', current_date_str)
active_market_diesel = get_price_for_date('diesel', current_date_str)

st.sidebar.title("Compass Navigation")
page = st.sidebar.radio("Go to:", ["🛒 Cashier Counter", "📊 Admin Reporting & Prices"])

if page == "🛒 Cashier Counter":
    st.title("⛽ Fuel Transaction Terminal")
    st.caption(f"🕒 **Computer Clock Sync:** {pc_now.strftime('%A, %d %B %Y | %I:%M:%S %p')}")
    col1, col2 = st.columns(2)
    fuel_category = col1.selectbox("Select Fuel Type", ["Petrol (RON95)", "Diesel"])
    pump_selection = col2.selectbox("Select Pump", (2, 4, 6, 7) if fuel_category == "Petrol (RON95)" else (1, 3, 5, 8), format_func=lambda x: f"Pump {x}")
    st.markdown("---"); col_in1, col_in2 = st.columns(2)
    
    if fuel_category == "Petrol (RON95)":
        rate_type = col_in1.radio("Pricing Tier", [f"Normal Market (RM {active_market_petrol:.2f})", "Subsidized (RM 1.99)"])
        harga_applied = 1.99 if "Subsidized" in rate_type else active_market_petrol
        liter = col_in1.number_input("LITER Dispensed", min_value=0.0, step=0.001, format="%.3f")
        diisi_rm = col_in2.number_input("Gross Filled Amount (Diisi RM)", min_value=0.0, step=0.01, format="%.2f")
        qr_ac = col_in2.number_input("QR / Card Payment (QR/AC)", min_value=0.0, step=0.01, format="%.2f")
        dibayar_rm = round(harga_applied * liter, 1)
        subsidy = round(abs((liter * round(active_market_petrol - 1.99, 2)) - qr_ac), 2) if harga_applied == 1.99 else 0.0
        calculated_meter = get_last_meter_reading(pump_selection) + liter
    else:
        diisi_rm = col_in1.number_input("Diisi (RM) - From Pump", min_value=0.0, step=0.01, format="%.2f")
        rate_type = col_in1.radio("Pricing Tier", [f"Commercial Market (RM {active_market_diesel:.2f})", "Subsidized (RM 2.15)"])
        harga_applied = 2.15 if "Subsidized" in rate_type else active_market_diesel
        col_in2.info("💡 Litres and Subsidy are calculated automatically from Diisi.")
        liter = round(diisi_rm / active_market_diesel, 2) if active_market_diesel > 0 else 0.0
        if harga_applied == 2.15:
            dibayar_rm = round(liter * 2.15, 2); subsidy = round(diisi_rm - dibayar_rm, 2)
            v_check = round(abs(liter * round(active_market_diesel - 2.15, 2) - subsidy), 2)
        else: dibayar_rm = diisi_rm; subsidy = 0.0; v_check = 0.0
        calculated_meter = 0.0

    st.markdown("### 📊 Live Math Summary"); cm1, cm2, cm3 = st.columns(3)
    cm1.metric("LITER Volume", f"{liter:.3f} L"); cm2.metric("Subsidy Amount", f"RM {subsidy:.2f}"); cm3.metric("DIBAYAR (Amount Due)", f"RM {dibayar_rm:.2f}")
    payment_method = st.selectbox("Payment Type Chosen", ["Cash", "Credit Card", "QR Pay"])
    
    if st.button("Submit Order & Log Record", type="primary", use_container_width=True):
        if diisi_rm > 0 or liter > 0:
            prefix = "PET" if "Petrol" in fuel_category else "DSL"
            rcpt = get_next_receipt_number(prefix); now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
            if prefix == "PET":
                cursor.execute(f"INSERT INTO petrol_pump_{pump_selection} (receipt_no, timestamp, diisi_rm, dibayar_rm, harga, liter, meter, qr_ac, subsidy) VALUES (?,?,?,?,?,?,?,?,?)", (rcpt, now_time, diisi_rm, dibayar_rm, harga_applied, liter, calculated_meter, qr_ac, subsidy))
            else:
                cursor.execute(f"INSERT INTO diesel_pump_{pump_selection} (receipt_no, timestamp, diisi_rm, dibayar_rm, harga, liter, verification_check, subsidy) VALUES (?,?,?,?,?,?,?,?)", (rcpt, now_time, diisi_rm, dibayar_rm, harga_applied, liter, v_check, subsidy))
            conn.commit(); conn.close()
            st.success(f"✅ Record saved under Pump {pump_selection} as receipt {rcpt}!")
        else: st.error("Please provide non-zero amounts before saving.")
else:
    st.title("⚙️ Operations Configuration & History View")
    st.markdown("---"); st.subheader("📝 Update Weekly Commercial Market Price Tiers")
    base_9_july = datetime(2026, 7, 9); days_since = (datetime.now() - base_9_july).days
    current_cycle_week = days_since // 7 if days_since >= 0 else -1
    default_start, default_end = ((base_9_july + timedelta(days=current_cycle_week*7)).strftime('%Y-%m-%d'), (base_9_july + timedelta(days=current_cycle_week*7+6)).strftime('%Y-%m-%d')) if current_cycle_week >= 0 else ("2026-07-01", "2026-07-08")
    st.info(f"📅 **Active Auto-Detected Cycle Block:** {default_start} to {default_end}")
    
    col_setup1, col_setup2 = st.columns(2)
    p_start = col_setup1.text_input("Petrol Start Date (YYYY-MM-DD)", value=default_start, key="p_start")
    p_end = col_setup1.text_input("Petrol End Date (YYYY-MM-DD)", value=default_end, key="p_end")
    p_price = col_setup1.number_input("New Commercial Petrol Price (RM)", min_value=0.0, value=active_market_petrol, step=0.01, format="%.2f", key="p_val")
    if col_setup1.button("Apply New Weekly Petrol Rate", use_container_width=True):
        update_weekly_price('petrol', p_start, p_end, p_price); st.success("Saved Petrol tier!"); st.rerun()
        
    d_start = col_setup2.text_input("Diesel Start Date (YYYY-MM-DD)", value=default_start, key="d_start")
    d_end = col_setup2.text_input("Diesel End Date (YYYY-MM-DD)", value=default_end, key="d_end")
    d_price = col_setup2.number_input("New Commercial Diesel Price (RM)", min_value=0.0, value=active_market_diesel, step=0.01, format="%.2f", key="d_val")
    if col_setup2.button("Apply New Weekly Diesel Rate", use_container_width=True):
        update_weekly_price('diesel', d_start, d_end, d_price); st.success("Saved Diesel tier!"); st.rerun()
            
    st.markdown("---"); st.subheader("📊 Saved Price Logs Database")
    conn = sqlite3.connect(DB_NAME); df_prices = pd.read_sql_query("SELECT fuel_type, start_date, end_date, commercial_price FROM config_prices ORDER BY start_date DESC", conn); conn.close()
    if not df_prices.empty: st.dataframe(df_prices, use_container_width=True)

    st.markdown("---"); st.subheader("📋 Historical Shift Transaction Tables Log Ledger"); col_log1, col_log2 = st.columns(2)
    view_p_p = col_log1.selectbox("Select Petrol Pump", (2, 4, 6, 7), key="view_p_pump")
    conn = sqlite3.connect(DB_NAME); df_p = pd.read_sql_query(f"SELECT * FROM petrol_pump_{view_p_p}", conn); conn.close()
    if not df_p.empty:
        col_log1.dataframe(df_p, use_container_width=True)
        col_log1.download_button(label="📥 Download Petrol CSV", data=df_p.to_csv(index=False).encode('utf-8'), file_name=f"petrol_{view_p_p}.csv", mime='text/csv')
    else: col_log1.info("No records recorded yet.")

    view_d_p = col_log2.selectbox("Select Diesel Pump", (1, 3, 5, 8), key="view_d_pump")
    conn = sqlite3.connect(DB_NAME); df_d = pd.read_sql_query(f"SELECT * FROM diesel_pump_{view_d_p}", conn); conn.close()
    if not df_d.empty:
        col_log2.dataframe(df_d, use_container_width=True)
        col_log2.download_button(label="📥 Download Diesel CSV", data=df_d.to_csv(index=False).encode('utf-8'), file_name=f"diesel_{view_d_p}.csv", mime='text/csv')
    else: col_log2.info("No records recorded yet.")

import streamlit as st, sqlite3, pandas as pd
import streamlit.components.v1 as components
from datetime import datetime, timedelta

# Upgraded database architecture to v29 to deploy the auto-increment transaction tracker safely
DB_NAME = 'fuel_station_v29.db'

def init_db():
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    for i in (2, 4, 6, 7):
        c.execute(f'''CREATE TABLE IF NOT EXISTS petrol_pump_{i} (
            id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT UNIQUE, timestamp TEXT, 
            diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, meter REAL, subsidy REAL, 
            payment_method TEXT, customer_name TEXT, original_prepaid REAL, cash_refund REAL)''')
    for i in (1, 3, 5, 8):
        c.execute(f'''CREATE TABLE IF NOT EXISTS diesel_pump_{i} (
            id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT UNIQUE, timestamp TEXT, 
            diisi_rm REAL, dibayar_rm REAL, harga REAL, liter REAL, verification_check REAL, subsidy REAL, 
            payment_method TEXT, customer_name TEXT, original_prepaid REAL, cash_refund REAL)''')
    c.execute('CREATE TABLE IF NOT EXISTS config_prices (fuel_type TEXT, start_date TEXT, end_date TEXT, commercial_price REAL, PRIMARY KEY (fuel_type, start_date))')
    c.execute('CREATE TABLE IF NOT EXISTS account_customers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, credit_balance REAL DEFAULT 0.0, created_at TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS shift_settlements (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, supervisor_name TEXT,
        sys_cash REAL, phys_cash REAL, var_cash REAL, sys_cc REAL, phys_cc REAL, var_cc REAL,
        sys_qr REAL, phys_qr REAL, var_qr REAL, sys_ac REAL, phys_ac REAL, var_ac REAL)''')
    c.execute('CREATE TABLE IF NOT EXISTS receipt_counter (id INTEGER PRIMARY KEY, last_id INTEGER)')
    c.execute("SELECT COUNT(*) FROM receipt_counter")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO receipt_counter (id, last_id) VALUES (1, 0)")
    c.execute("SELECT COUNT(*) FROM config_prices")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO config_prices VALUES (?,?,?,?)", [
            ('petrol', '2026-07-01', '2026-07-08', 3.37), ('diesel', '2026-07-01', '2026-07-08', 3.97),
            ('petrol', '2026-07-09', '2026-07-15', 3.37), ('diesel', '2026-07-09', '2026-07-15', 3.97)
        ])
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
    c.execute("SELECT last_id FROM receipt_counter WHERE id = 1")
    last_id = c.fetchone()[0]
    next_id = last_id + 1
    # Complete fix applied here: switched from replace insertion to direct incremental column row updating
    c.execute("UPDATE receipt_counter SET last_id = ? WHERE id = 1", (next_id,))
    conn.commit(); conn.close()
    return f"{prefix}-{next_id:06d}"

def get_last_meter_reading(pump_no):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    try:
        c.execute(f"SELECT meter FROM petrol_pump_{pump_no} ORDER BY id DESC LIMIT 1")
        res = c.fetchone()
        return float(res[0]) if res and res[0] is not None else 0.0
    except: return 0.0
    finally: conn.close()

def add_customer(name, initial_credit):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    try:
        c.execute("INSERT INTO account_customers (name, credit_balance, created_at) VALUES (?, ?, ?)", (name.strip().upper(), initial_credit, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit(); return True
    except: return False
    finally: conn.close()

def topup_customer_credit(name, amount):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("UPDATE account_customers SET credit_balance = credit_balance + ? WHERE name = ?", (amount, name))
    conn.commit(); conn.close()

def deduct_customer_credit(name, amount):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("UPDATE account_customers SET credit_balance = credit_balance - ? WHERE name = ?", (amount, name))
    conn.commit(); conn.close()

def get_customers():
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT name, credit_balance FROM account_customers ORDER BY name ASC")
    rows = c.fetchall(); conn.close()
    return rows

init_db()
st.set_page_config(page_title="Fuel Station POS Terminal", layout="wide")
pc_now = datetime.now(); current_date_str = pc_now.strftime('%Y-%m-%d')
active_market_petrol = get_price_for_date('petrol', current_date_str)
active_market_diesel = get_price_for_date('diesel', current_date_str)

st.sidebar.title("Compass Navigation")
page = st.sidebar.radio("Go to:", ["🛒 Cashier Counter", "👤 AC Customer Wallet Manager", "🔏 Shift Settlement Desk", "📊 Admin Reporting & Prices"])
if page == "🛒 Cashier Counter":
    st.title("🛒 Fuel Cashier Terminal")
    st.caption(f"🕒 **System Clock:** {pc_now.strftime('%A, %d %B %Y | %I:%M:%S %p')}")
    col1, col2 = st.columns(2)
    fuel_category = col1.selectbox("Select Fuel Type", ["Petrol (RON95)", "Diesel"])
    pump_selection = col2.selectbox("Select Pump", (2, 4, 6, 7) if fuel_category == "Petrol (RON95)" else (1, 3, 5, 8), format_func=lambda x: f"Pump {x}")
    st.markdown("---"); col_in1, col_in2 = st.columns(2)
    
    diisi_rm = col_in1.number_input("Diisi (RM) - From Pump Display Screen", min_value=0.0, step=1.0, format="%.2f")
    
    if fuel_category == "Petrol (RON95)":
        rate_type = col_in2.radio("Pricing Tier", [f"Normal Market (RM {active_market_petrol:.2f})", "Subsidized (RM 1.99)"])
        harga_applied = 1.99 if "Subsidized" in rate_type else active_market_petrol
        liter = round(diisi_rm / active_market_petrol, 2) if active_market_petrol > 0 else 0.0
        dibayar_rm = round(harga_applied * liter, 1)
        subsidy_rate = round(active_market_petrol - 1.99, 2)
        subsidy = round(abs((liter * subsidy_rate) - diisi_rm), 2) if harga_applied == 1.99 else 0.0
        calculated_meter = get_last_meter_reading(pump_selection) + liter
        v_check = 0.0
    else:
        rate_type = col_in2.radio("Pricing Tier", [f"Commercial Market (RM {active_market_diesel:.2f})", "Subsidized (RM 2.15)"])
        harga_applied = 2.15 if "Subsidized" in rate_type else active_market_diesel
        liter = round(diisi_rm / active_market_diesel, 2) if active_market_diesel > 0 else 0.0
        if harga_applied == 2.15:
            dibayar_rm = round(liter * 2.15, 2); subsidy = round(diisi_rm - dibayar_rm, 2)
            v_check = round(abs(liter * round(active_market_diesel - 2.15, 2) - subsidy), 2)
        else: dibayar_rm = diisi_rm; subsidy = 0.0; v_check = 0.0
        calculated_meter = 0.0

    st.markdown("### 📊 Live Math Summary"); cm1, cm2, cm3 = st.columns(3)
    cm1.metric("LITER Volume", f"{liter:.2f} L"); cm2.metric("Subsidy Amount", f"RM {subsidy:.2f}"); cm3.metric("DIBAYAR (Amount Due)", f"RM {dibayar_rm:.2f}")
    
    payment_method = st.selectbox("Payment Type Chosen", ["Cash", "Credit Card", "QR Pay", "AC (Account Customer)"])
    
    is_refund = st.checkbox("🔄 Is there a Card/QR overpayment refund for this sale?")
    original_prepaid = 0.0; cash_refund = 0.0
    if is_refund:
        st.markdown("#### 💵 Overpayment Cash Refund Desk")
        original_prepaid = st.number_input("Enter Original Prepaid Amount (RM)", min_value=diisi_rm, step=10.0, format="%.2f")
        cash_refund = round(original_prepaid - dibayar_rm, 2)
        st.warning(f"💵 **Cash Refund to Customer:** RM {cash_refund:.2f}")

    chosen_customer = "-"
    current_wallet_credit = 0.0
    if payment_method == "AC (Account Customer)":
        st.markdown("#### 👤 Active Prepaid Balance Verification")
        existing_customers = get_customers()
        if existing_customers:
            cust_names = [r[0] for r in existing_customers]
            chosen_customer = st.selectbox("Select Account Customer", cust_names)
            current_wallet_credit = next(b for n, b in existing_customers if n == chosen_customer)
            if current_wallet_credit < dibayar_rm: st.error(f"❌ **INSUFFICIENT STATION CREDIT!** Balance is RM {current_wallet_credit:.2f}.")
            else: st.success(f"✅ **CREDIT APPROVED:** Balance: RM {current_wallet_credit:.2f}.")
        else: st.warning("No customers registered yet.")
    
    if "print_trigger" not in st.session_state: st.session_state.print_trigger = None

    if st.button("Submit Order & Log Record", type="primary", use_container_width=True):
        if diisi_rm > 0:
            if payment_method == "AC (Account Customer)" and current_wallet_credit < dibayar_rm: st.error("Cannot submit transaction. Insufficient credit.")
            else:
                prefix = "PET" if "Petrol" in fuel_category else "DSL"
                rcpt = get_next_receipt_number(prefix); now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
                if prefix == "PET":
                    cursor.execute(f"INSERT INTO petrol_pump_{pump_selection} (receipt_no, timestamp, diisi_rm, dibayar_rm, harga, liter, meter, subsidy, payment_method, customer_name, original_prepaid, cash_refund) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (rcpt, now_time, diisi_rm, dibayar_rm, harga_applied, liter, calculated_meter, subsidy, payment_method, chosen_customer, original_prepaid, cash_refund))
                else:
                    cursor.execute(f"INSERT INTO diesel_pump_{pump_selection} (receipt_no, timestamp, diisi_rm, dibayar_rm, harga, liter, verification_check, subsidy, payment_method, customer_name, original_prepaid, cash_refund) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (rcpt, now_time, diisi_rm, dibayar_rm, harga_applied, liter, v_check, subsidy, payment_method, chosen_customer, original_prepaid, cash_refund))
                conn.commit(); conn.close()
                if payment_method == "AC (Account Customer)": deduct_customer_credit(chosen_customer, dibayar_rm)
                
                b_prc = active_market_petrol if "Petrol" in fuel_category else active_market_diesel
                refund_receipt_line = f"PREPAID : RM {original_prepaid:.2f}\nCASH REF: RM {cash_refund:.2f}\n" if is_refund else ""
                
                receipt_html = f"""
                <html><body style="font-family:monospace; font-size:12px; width:220px; margin:0; padding:10px;">
                <div style="text-align:center; font-weight:bold;">========================<br>  MADANI FUEL STATION  <br>========================</div>
                <br>DATE: {now_time}<br>RECEIPT: {rcpt}<br>PUMP ID: Pump {pump_selection} ({fuel_category})<br>PAYMENT: {payment_method}<br>CLIENT : {chosen_customer}<br>
                ------------------------<br>VOLUME : {liter:.2f} Litres<br>PRICE  : RM {b_prc:.2f}/L<br>GROSS  : RM {diisi_rm:.2f}<br>
                ------------------------<br>{refund_receipt_line}MADANI SAVINGS: RM -{subsidy:.2f}<br>
                ------------------------<br><div style="font-size:14px; font-weight:bold; text-align:center;">FINAL PAID:<br>RM {dibayar_rm:.2f}</div>
                ------------------------<br><div style="text-align:center;">Thank You / Terima Kasih<br>Pandu Cermat</div>
                </body></html>
                """
                st.session_state.print_trigger = receipt_html
                st.success(f"✅ Transaction Logged under Ticket #{rcpt}!")
                st.rerun()
        else: st.error("Please provide non-zero amounts.")

    if st.session_state.print_trigger:
        components.html(f"""
        <iframe id="print_frame" style="display:none;"></iframe>
        <script>
            var doc = document.getElementById('print_frame').contentWindow.document;
            doc.open(); doc.write(`{st.session_state.print_trigger}`); doc.close();
            setTimeout(function() {{ document.getElementById('print_frame').contentWindow.print(); }}, 500);
        </script>
        """, height=0)
        st.session_state.print_trigger = None
elif page == "👤 AC Customer Wallet Manager":
    st.title("👤 Account Customer Wallet & Credit Manager")
    st.markdown("---")
    adm_col1, adm_col2 = st.columns(2)
    with adm_col1.form("register_profile_form", clear_on_submit=True):
        st.subheader("📝 Register New AC Client Profile")
        new_name = st.text_input("Company or Customer Name")
        initial_pay = st.number_input("Advance Pre-paid Deposit Amount (RM)", min_value=0.0, step=10.0, format="%.2f")
        if st.form_submit_button("Create Customer Profile"):
            if new_name and add_customer(new_name, initial_pay): st.success(f"Configured ledger profile for {new_name.upper()}!"); st.rerun()
            else: st.error("Error creating profile.")
    with adm_col2.form("topup_credit_form", clear_on_submit=True):
        st.subheader("💵 Log Advance Cash Payment (Top-Up)")
        customer_list_raw = get_customers()
        if customer_list_raw:
            customer_list = [n[0] for n in customer_list_raw]
            target_topup = st.selectbox("Select Client Target Account", customer_list)
            topup_amt = st.number_input("Cash Payment Top-Up Received (RM)", min_value=1.0, step=10.0, format="%.2f")
            if st.form_submit_button("Confirm Payment Top-Up"):
                topup_customer_credit(target_topup, topup_amt); st.success("Topup added!"); st.rerun()
        else: st.info("No active accounts registered to top up yet.")
        
    st.markdown("---"); st.subheader("📊 Live Prepaid Balance Ledger & Usage Report")
    conn = sqlite3.connect(DB_NAME); customers_data = get_customers(); final_report = []
    for name, bal in customers_data:
        p_liters = pd.read_sql_query(f"SELECT SUM(liter) as lit, SUM(dibayar_rm) as amt FROM petrol_pump_2 WHERE customer_name='{name}' UNION ALL SELECT SUM(liter), SUM(dibayar_rm) FROM petrol_pump_4 WHERE customer_name='{name}' UNION ALL SELECT SUM(liter), SUM(dibayar_rm) FROM petrol_pump_6 WHERE customer_name='{name}' UNION ALL SELECT SUM(liter), SUM(dibayar_rm) FROM petrol_pump_7 WHERE customer_name='{name}'", conn)
        d_liters = pd.read_sql_query(f"SELECT SUM(liter) as lit, SUM(dibayar_rm) as amt FROM diesel_pump_1 WHERE customer_name='{name}' UNION ALL SELECT SUM(liter), SUM(dibayar_rm) FROM diesel_pump_3 WHERE customer_name='{name}' UNION ALL SELECT SUM(liter), SUM(dibayar_rm) FROM diesel_pump_5 WHERE customer_name='{name}' UNION ALL SELECT SUM(liter), SUM(dibayar_rm) FROM diesel_pump_8 WHERE customer_name='{name}'", conn)
        total_lit = float(p_liters['lit'].fillna(0).sum() + d_liters['lit'].fillna(0).sum())
        total_spent = float(p_liters['amt'].fillna(0).sum() + d_liters['amt'].fillna(0).sum())
        status = "⚠️ LOW CREDIT" if bal <= 150.0 else "✅ Good Standing"
        final_report.append({"Customer Name": name, "Current Balance (RM)": round(bal, 2), "Total Fuel Litres Pumped": round(total_lit, 2), "Total Fuel Expenditures (RM)": round(total_spent, 2), "Account Status": status})
    conn.close()
    if final_report: st.dataframe(pd.DataFrame(final_report), use_container_width=True)
elif page == "🔏 Shift Settlement Desk":
    st.title("🔏 Shift Settlement & Counter Audit Desk")
    st.markdown("---")
    
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    sys_cash = 0.0; sys_cc = 0.0; sys_qr = 0.0; sys_ac = 0.0
    active_tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    
    for i in (2, 4, 6, 7):
        if f"petrol_pump_{i}" in active_tables:
            c.execute(f"SELECT IFNULL(SUM(dibayar_rm), 0.0) FROM petrol_pump_{i} WHERE payment_method='Cash'"); sys_cash += float(c.fetchone()[0])
            c.execute(f"SELECT IFNULL(SUM(dibayar_rm), 0.0) FROM petrol_pump_{i} WHERE payment_method='Credit Card'"); sys_cc += float(c.fetchone()[0])
            c.execute(f"SELECT IFNULL(SUM(dibayar_rm), 0.0) FROM petrol_pump_{i} WHERE payment_method='QR Pay'"); sys_qr += float(c.fetchone()[0])
            c.execute(f"SELECT IFNULL(SUM(dibayar_rm), 0.0) FROM petrol_pump_{i} WHERE payment_method='AC (Account Customer)'"); sys_ac += float(c.fetchone()[0])
            c.execute(f"SELECT IFNULL(SUM(cash_refund), 0.0) FROM petrol_pump_{i}"); sys_cash -= float(c.fetchone()[0])
        
    for i in (1, 3, 5, 8):
        if f"diesel_pump_{i}" in active_tables:
            c.execute(f"SELECT IFNULL(SUM(dibayar_rm), 0.0) FROM diesel_pump_{i} WHERE payment_method='Cash'"); sys_cash += float(c.fetchone()[0])
            c.execute(f"SELECT IFNULL(SUM(dibayar_rm), 0.0) FROM diesel_pump_{i} WHERE payment_method='Credit Card'"); sys_cc += float(c.fetchone()[0])
            c.execute(f"SELECT IFNULL(SUM(dibayar_rm), 0.0) FROM diesel_pump_{i} WHERE payment_method='QR Pay'"); sys_qr += float(c.fetchone()[0])
            c.execute(f"SELECT IFNULL(SUM(dibayar_rm), 0.0) FROM diesel_pump_{i} WHERE payment_method='AC (Account Customer)'"); sys_ac += float(c.fetchone()[0])
            c.execute(f"SELECT IFNULL(SUM(cash_refund), 0.0) FROM diesel_pump_{i}"); sys_cash -= float(c.fetchone()[0])
    conn.close()

    with st.expander("🛠️ Open Supervisor Data Override & Correction Terminal", expanded=False):
        st.subheader("Modify Cashier Transaction Entries Manually")
        ov_fuel = st.selectbox("Override Target Fuel", ["Petrol", "Diesel"], key="ov_fuel")
        ov_pump = st.selectbox("Select Target Pump", (2, 4, 6, 7) if ov_fuel == "Petrol" else (1, 3, 5, 8), key="ov_pump")
        t_target = f"petrol_pump_{ov_pump}" if ov_fuel == "Petrol" else f"diesel_pump_{ov_pump}"
        
        conn = sqlite3.connect(DB_NAME); rcpt_list = []
        if t_target in active_tables:
            try:
                rcpt_df = pd.read_sql_query(f"SELECT receipt_no FROM {t_target} ORDER BY timestamp DESC", conn)
                rcpt_list = rcpt_df['receipt_no'].tolist()
            except: pass
        conn.close()
        
        if rcpt_list:
            target_rcpt = st.selectbox("Choose Receipt Number to Correct", rcpt_list)
            conn = sqlite3.connect(DB_NAME)
            orig_row = pd.read_sql_query(f"SELECT * FROM {t_target} WHERE receipt_no='{target_rcpt}'", conn).iloc[0]
            conn.close()
            
            col_ed1, col_ed2 = st.columns(2)
            new_diisi = col_ed1.number_input("Correct Diisi (RM) Gross Value", min_value=0.0, value=float(orig_row['diisi_rm']), step=1.0)
            new_pay_method = col_ed2.selectbox("Correct Payment Type", ["Cash", "Credit Card", "QR Pay", "AC (Account Customer)"], index=["Cash", "Credit Card", "QR Pay", "AC (Account Customer)"].index(orig_row['payment_method']))
            
            if ov_fuel == "Petrol":
                calc_lit = round(new_diisi / active_market_petrol, 2)
                calc_paid = round(orig_row['harga'] * calc_lit, 1)
                calc_sub = round(abs((calc_lit * round(active_market_petrol - 1.99, 2)) - new_diisi), 2) if orig_row['harga'] == 1.99 else 0.0
            else:
                calc_lit = round(new_diisi / active_market_diesel, 2)
                calc_paid = round(2.15 * calc_lit, 2) if orig_row['harga'] == 2.15 else new_diisi
                calc_sub = round(new_diisi - calc_paid, 2) if orig_row['harga'] == 2.15 else 0.0
                
            if st.button("Apply Supervisor Correction Override", type="secondary", use_container_width=True):
                conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
                cursor.execute(f"UPDATE {t_target} SET diisi_rm=?, dibayar_rm=?, liter=?, subsidy=?, payment_method=? WHERE receipt_no=?", (new_diisi, calc_paid, calc_lit, calc_sub, new_pay_method, target_rcpt))
                conn.commit(); conn.close()
                st.success(f"📊 Modified entry {target_rcpt} successfully!"); st.rerun()
        else: st.info("No transaction logs recorded under this pump yet.")

    st.subheader("📝 Supervisor Shift Entry Closing Form")
    sv_name = st.text_input("Enter Supervisor Name")
    col_input1, col_col2 = st.columns(2)
    phys_cash = col_input1.number_input("Physical Cash Counted Drawer Total (RM)", min_value=0.0, step=10.0, format="%.2f")
    phys_cc = col_input1.number_input("Physical Credit Card Slips Total Value (RM)", min_value=0.0, step=10.0, format="%.2f")
    phys_qr = col_col2.number_input("Physical QR/E-Wallet Terminals Settlement (RM)", min_value=0.0, step=10.0, format="%.2f")
    phys_ac = col_col2.number_input("Physical Corporate AC Delivery Slips Value (RM)", min_value=0.0, step=10.0, format="%.2f")

    v_cash = round(phys_cash - sys_cash, 2); v_cc = round(phys_cc - sys_cc, 2); v_qr = round(phys_qr - sys_qr, 2); v_ac = round(phys_ac - sys_ac, 2)
    st.markdown("### 📊 Live Shift Variance Reconciliation Grid")
    recon_data = [
        {"Payment Method": "Cash Drawer (Net of Refunds)", "System Expected (RM)": sys_cash, "Supervisor Count (RM)": phys_cash, "Variance (RM)": v_cash},
        {"Payment Method": "Credit Card Terminal", "System Expected (RM)": sys_cc, "Supervisor Count (RM)": phys_cc, "Variance (RM)": v_cc},
        {"Payment Method": "QR Pay / E-Wallet", "System Expected (RM)": sys_qr, "Supervisor Count (RM)": phys_qr, "Variance (RM)": v_qr},
        {"Payment Method": "AC (Account Customer Slips)", "System Expected (RM)": sys_ac, "Supervisor Count (RM)": phys_ac, "Variance (RM)": v_ac}
    ]
    df_recon = pd.DataFrame(recon_data)
    def color_variance(val):
        if val < 0: return 'background-color: #ffcccc; color: #cc0000; font-weight: bold'
        elif val > 0: return 'background-color: #c9f7f5; color: #277973; font-weight: bold'
        return 'background-color: #e2f0d9; color: #2e75b6;'
    st.dataframe(df_recon.style.map(color_variance, subset=['Variance (RM)']), use_container_width=True)

    if st.button("Commit & Lock Shift Proceed Settlement Report", type="primary", use_container_width=True):
        if sv_name:
            conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
            cursor.execute('''INSERT INTO shift_settlements (timestamp, supervisor_name, sys_cash, phys_cash, var_cash, sys_cc, phys_cc, var_cc, sys_qr, phys_qr, var_qr, sys_ac, phys_ac, var_ac) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sv_name, sys_cash, phys_cash, v_cash, sys_cc, phys_cc, v_cc, sys_qr, phys_qr, v_qr, sys_ac, phys_ac, v_ac))
            conn.commit(); conn.close(); st.success("✅ Shift settlement successfully saved!"); st.rerun()
        else: st.error("Please enter Supervisor Name.")
else:
    st.title("⚙️ Operations Configuration & History View")
    st.markdown("---"); st.subheader("📝 Update Weekly Commercial Market Price Tiers")
    base_9_july = datetime(2026, 7, 9); days_since = (datetime.now() - base_9_july).days
    current_cycle_week = days_since // 7 if days_since >= 0 else -1
    default_start, default_end = ((base_9_july + timedelta(days=current_cycle_week*7)).strftime('%Y-%m-%d'), (base_9_july + timedelta(days=current_cycle_week*7+6)).strftime('%Y-%m-%d')) if current_cycle_week >= 0 else ("2026-07-01", "2026-07-08")
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
    
    st.markdown("---"); st.subheader("📋 Locked Shift Settlement Proceed Reports History")
    conn = sqlite3.connect(DB_NAME); df_settle = pd.read_sql_query("SELECT * FROM shift_settlements ORDER BY id DESC", conn); conn.close()
    if not df_settle.empty:
        st.dataframe(df_settle, use_container_width=True)
        st.download_button(label="📥 Download Shift Settlement History CSV", data=df_settle.to_csv(index=False).encode('utf-8'), file_name="shift_settlements_history.csv", mime='text/csv', use_container_width=True)
    
    st.markdown("---"); st.subheader("📋 Consolidated Station Pump Extract Engine")
    dt_col1, dt_col2 = st.columns(2)
    start_filter = dt_col1.date_input("Start Date Filter", pc_now.date() - timedelta(days=7))
    end_filter = dt_col2.date_input("End Date Filter", pc_now.date())
    s_filter_str = start_filter.strftime("%Y-%m-%d 00:00:00"); e_filter_str = end_filter.strftime("%Y-%m-%d 23:59:59")
    
    conn = sqlite3.connect(DB_NAME); c = conn.cursor(); active_tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]; conn.close()
    conn = sqlite3.connect(DB_NAME); all_rows = []
    for i in (2, 4, 6, 7):
        if f"petrol_pump_{i}" in active_tables:
            try:
                df_tmp = pd.read_sql_query(f"SELECT * FROM petrol_pump_{i} WHERE timestamp BETWEEN '{s_filter_str}' AND '{e_filter_str}'", conn)
                if not df_tmp.empty: df_tmp['Fuel Type'] = 'Petrol'; df_tmp['Pump No'] = i; all_rows.append(df_tmp)
            except: pass
    for i in (1, 3, 5, 8):
        if f"diesel_pump_{i}" in active_tables:
            try:
                df_tmp = pd.read_sql_query(f"SELECT * FROM diesel_pump_{i} WHERE timestamp BETWEEN '{s_filter_str}' AND '{e_filter_str}'", conn)
                if not df_tmp.empty:
                    df_tmp['Fuel Type'] = 'Diesel'; df_tmp['Pump No'] = i
                    df_tmp = df_tmp.rename(columns={'verification_check': 'subsidy'}); all_rows.append(df_tmp)
            except: pass
    conn.close()
    if all_rows:
        master_df = pd.concat(all_rows, ignore_index=True).sort_values(by=['Pump No', 'timestamp'], ascending=[True, True])
        ordered_cols = ['Pump No', 'Fuel Type', 'receipt_no', 'timestamp', 'diisi_rm', 'dibayar_rm', 'harga', 'liter', 'subsidy', 'payment_method', 'customer_name', 'original_prepaid', 'cash_refund']
        master_df = master_df[ordered_cols]
        st.dataframe(master_df, use_container_width=True)
        st.download_button(label="📥 Download Sorted Consolidated CSV", data=master_df.to_csv(index=False).encode('utf-8'), file_name="station_master_report.csv", mime='text/csv', use_container_width=True)

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import date

def save_amount():
    # Use the key from st.number_input
    if "amt_widget" in st.session_state:
        # Grab the value and save it to our main form_data dictionary
        st.session_state.form_data['amount'] = float(st.session_state.amt_widget)
        # Move to the next screen
        st.session_state.step = 2

def restart():
    st.session_state.step = 1
    # Clear the cache so new categories show up next time
    get_dropdown_options.clear()
    st.rerun()

def save_what():
    if "what_widget" in st.session_state:
        st.session_state.form_data['what'] = st.session_state.what_widget
        st.session_state.step = 3

def save_where():
    if "where_widget" in st.session_state:
        st.session_state.form_data['where'] = st.session_state.where_widget
        st.session_state.step = 4

# --- INITIALIZATION ---
if 'step' not in st.session_state:
    st.session_state.step = 1

# Initialize form_data with clear numeric types
if 'form_data' not in st.session_state:
    st.session_state.form_data = {
        'amount': 0.0,
        'what': '',
        'where': '',
        'main_cat': 'General Spending',
        'sub_cat': '',
        'payment': 'Credit Card',
        'date': date.today()
    }

# --- AUTHENTICATION ---
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(st.secrets["google_credentials"], scopes=scope)
client = gspread.authorize(creds)

SHEET_ID = "15vlb7mA7pENePJ7Sl1YLITmM6r9eEXn2LLVAxGKWZlI"
spreadsheet = client.open_by_key(SHEET_ID)
entry_sheet = spreadsheet.get_worksheet(0)
budget_sheet = spreadsheet.get_worksheet(1)


# --- HELPER: GET DROPDOWNS ---
# We'll cache this so it doesn't slow down the app every time you click a button
@st.cache_data(ttl=600)
def get_dropdown_options():
    # Fetch all data from the first tab to find unique categories
    data = entry_sheet.get_all_records()
    main_cats = sorted(list(set(row['Main Category'] for row in data if row['Main Category'])))
    sub_cats = sorted(list(set(row['Sub-Category'] for row in data if row['Sub-Category'])))
    payments = sorted(list(set(row['Payment Method'] for row in data if row['Payment Method'])))
    return main_cats, sub_cats, payments


main_options, sub_options, pay_options = get_dropdown_options()

st.title("💰 Vulosiraptor")

# --- PASSWORD PROTECTION ---
def check_password():
    """Returns True if the user had the correct password."""
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password in state
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password
        st.text_input("Please enter the password", type="password",
                      on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error
        st.text_input("Please enter the password", type="password",
                      on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct
        return True

if not check_password():
    st.stop()  # Do not run anything below this line if password isn't correct

# --- STEP 1: AMOUNT ---
if st.session_state.step == 1:
    st.number_input("How much?", min_value=0.0, step=0.01, format="%.2f",
                    key="amt_widget", on_change=save_amount)
    if st.button("Next"): save_amount()

# --- STEP 2: WHAT ---
elif st.session_state.step == 2:
    st.text_input("What was it?", key="what_widget", on_change=save_what)
    if st.button("Next"): save_what()

# --- STEP 3: WHERE ---
elif st.session_state.step == 3:
    st.text_input("Where at?", key="where_widget", on_change=save_where)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Next"): save_where()
    with col2:
        # Quick Save still works as a regular button
        if st.button("⚡ Quick Save"):
            # (Insert your existing Quick Save logic here)
            pass

# --- STEP 4: FULL DETAILS ---
elif st.session_state.step == 4:
    with st.form("step4_form"):
        m_cat = st.selectbox("Main Category", options=main_options)
        s_cat = st.selectbox("Sub-Category", options=sub_options)
        pay = st.selectbox("Payment Method", options=pay_options)
        dt_obj = st.date_input("Date", value=date.today())

        finalize = st.form_submit_button("Finalize & Save")

        if finalize:
            final_amt = float(st.session_state.form_data['amount'])
            formatted_date = dt_obj.strftime("%m/%d/%y")

            # Define the row data once
            new_row = [
                st.session_state.form_data['what'],  # Column A
                st.session_state.form_data['where'],  # Column B
                m_cat,  # Column C
                s_cat,  # Column D
                pay,  # Column E
                final_amt,  # Column F
                formatted_date  # Column G
            ]

            # --- SMART APPEND LOGIC ---
            # 1. Get all values in Column A to find the last entry
            col_a = entry_sheet.col_values(1)

            # 2. DEFINE next_row (This was the missing piece!)
            next_row = len(col_a) + 1

            # 3. Update the specific range for that row
            entry_sheet.update(
                range_name=f"A{next_row}:G{next_row}",
                values=[new_row],
                value_input_option="USER_ENTERED"
            )

            #sorty by column G which is the date
            entry_sheet.sort((7, 'asc'))

            st.success(f"Logged ${final_amt:,.2f} to row {next_row}!")
            restart()

# --- BUDGET DASHBOARD ---
st.divider()
with st.expander("📊 Monthly Budget Status", expanded=False):
    try:
        # Pull 3 rows (A6:D8) to get General Spending + 2 more categories
        budget_data = budget_sheet.get("A6:D8")

        for row in budget_data:
            category_name = row[0]
            spent = row[1]
            limit = row[2]

            # Create a nice layout for each category
            st.markdown(f"#### {category_name}")
            c1, c2 = st.columns(2)
            c1.metric("Spent", spent)
            c2.metric("Limit", limit)

            # Progress Bar Logic
            prog_raw = row[3].replace('%', '')
            prog = float(prog_raw) / 100

            # Color coding the progress bar
            if prog >= 1.0:
                st.error("Budget Exceeded!")
            elif prog >= 0.8:
                st.warning("Approaching Limit")

            st.progress(min(prog, 1.0))
            st.caption(f"{int(prog * 100)}% of monthly limit used")
            st.divider()

        # --- DIRECT LINK ---
        spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
        st.caption(f"Access the spreadsheet directly [by clicking here]({spreadsheet_url})")

    except Exception as e:
        st.write("Click to refresh budget stats...")
        # st.error(f"Error: {e}") # Uncomment to debug if it stays blank


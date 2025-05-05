import streamlit as st
import datetime
import pandas as pd
from collections import defaultdict

# --- Configuration ---
PRICES = {
    "Elder Day Care": 800,
    "Child Day Care": 600
}
SERVICE_NAMES = list(PRICES.keys())
CURRENCY_SYMBOL = "Rs."
MAX_CAPACITY = 25  # Per service, per day

# --- Helper Function: Get Weekdays in a Date Range ---
def get_weekdays_in_range(start_date, end_date):
    """
    Generates a list of weekdays (Mon-Fri) between start_date and end_date (inclusive).
    Returns an empty list if range is invalid or contains no weekdays.
    """
    weekdays_list = []
    # Ensure dates are valid date objects before proceeding
    if isinstance(start_date, datetime.date) and isinstance(end_date, datetime.date) and start_date <= end_date:
        try:
            # Use pandas for easy date range generation and weekday filtering
            all_dates = pd.date_range(start=start_date, end=end_date, freq='D')
            # pandas weekday: Monday=0, Sunday=6
            weekdays_only = all_dates[all_dates.weekday < 5] # Keep Monday (0) to Friday (4)
            weekdays_list = weekdays_only.to_pydatetime().tolist() # Convert back to list of datetime objects
            # Convert datetime.datetime back to datetime.date
            weekdays_list = [dt.date() for dt in weekdays_list]
        except Exception as e:
            st.error(f"Error generating date range: {e}")
            return []
    return weekdays_list

# --- Initialize Session State ---
# Use session_state to preserve data across Streamlit script reruns.

if 'daily_bookings' not in st.session_state:
    st.session_state.daily_bookings = defaultdict(lambda: defaultdict(int))
if 'booking_details' not in st.session_state:
    st.session_state.booking_details = {}
if 'total_cost' not in st.session_state:
    st.session_state.total_cost = 0
if 'availability_checked' not in st.session_state:
    st.session_state.availability_checked = False
if 'is_available' not in st.session_state:
    st.session_state.is_available = False
if 'payment_status' not in st.session_state:
    st.session_state.payment_status = None


# --- App Layout ---
st.set_page_config(layout="wide")
st.title("☀️ Day Care Booking Service")

# --- Sidebar for Inputs ---
with st.sidebar:
    st.header("Step 1: Select Service(s) & Dates")
    st.markdown("---")

    # Service Selection
    select_elder = st.checkbox("Book Elder Day Care?", key="cb_elder", value=st.session_state.get('cb_elder', False)) # Persist checkbox state
    elder_date_range = None
    if select_elder:
        # FIX: Use value=[] for empty range default instead of (None, None)
        elder_date_range = st.date_input(
            "Select Elder Day Care Date Range:",
            value=[], # Use empty list for default empty range
            min_value=datetime.date.today() + datetime.timedelta(days=1),
            format="YYYY-MM-DD",
            key="dr_elder"
        )

    st.markdown("---")
    select_child = st.checkbox("Book Child Day Care?", key="cb_child", value=st.session_state.get('cb_child', True)) # Default checked & persist
    child_date_range = None
    if select_child:
        # FIX: Use value=[] for empty range default instead of (None, None)
        child_date_range = st.date_input(
            "Select Child Day Care Date Range:",
            value=[], # Use empty list for default empty range
            min_value=datetime.date.today() + datetime.timedelta(days=1),
            format="YYYY-MM-DD",
            key="dr_child"
        )

    st.markdown("---")

    # Confirmation Button
    confirm_button = st.button("Check Availability & Calculate Cost", type="primary")

    # Display status and summary in sidebar after check
    st.markdown("---")
    availability_placeholder = st.empty()
    summary_placeholder = st.empty()

# --- Main Area for Results & Payment ---
st.header("Step 2: Review and Proceed")
st.markdown("---")
payment_placeholder = st.empty()

# Expander for demo bookings
with st.expander("Show Current Simulated Bookings (Demo)"):
    display_bookings = {date: dict(counts) for date, counts in st.session_state.daily_bookings.items()}
    if not display_bookings:
        st.write("No bookings recorded yet.")
    else:
        sorted_dates = sorted(display_bookings.keys())
        sorted_display_bookings = {date: display_bookings[date] for date in sorted_dates}
        st.json(sorted_display_bookings)

# --- Logic for Confirmation Button Click ---
if confirm_button:
    # 1. Reset previous attempt state
    st.session_state.booking_details = {}
    st.session_state.total_cost = 0
    st.session_state.is_available = False
    st.session_state.availability_checked = True
    st.session_state.payment_status = None

    # 2. Input Validation
    processing_errors = []
    valid_elder_range = False
    valid_child_range = False

    if not select_elder and not select_child:
        processing_errors.append("Please select at least one service type.")

    if select_elder:
        # st.date_input returns a list/tuple for range, check length
        if isinstance(elder_date_range, (list, tuple)) and len(elder_date_range) == 2:
            start_dt, end_dt = elder_date_range
            if start_dt is None or end_dt is None:
                 processing_errors.append("Please select BOTH a start and end date for Elder Day Care.")
            elif start_dt > end_dt:
                 processing_errors.append("Elder Care: Start date cannot be after end date.")
            else:
                 valid_elder_range = True
        else: # Handle case where it's not a list/tuple or wrong length (e.g., initially [])
             processing_errors.append("Please select a start and end date for Elder Day Care.")


    if select_child:
        if isinstance(child_date_range, (list, tuple)) and len(child_date_range) == 2:
            start_dt, end_dt = child_date_range
            if start_dt is None or end_dt is None:
                 processing_errors.append("Please select BOTH a start and end date for Child Day Care.")
            elif start_dt > end_dt:
                 processing_errors.append("Child Care: Start date cannot be after end date.")
            else:
                 valid_child_range = True
        else:
             processing_errors.append("Please select a start and end date for Child Day Care.")


    if processing_errors:
        availability_placeholder.error("Please fix the following issues:\n\n* " + "\n* ".join(processing_errors))
        st.session_state.availability_checked = False # Validation failed
    else:
        # 3. Process Selections and Check Capacity (Only if ranges were valid)
        overall_availability = True
        temp_elder_details = None
        temp_child_details = None
        current_booking_counts = st.session_state.daily_bookings

        # --- Process Elder Care ---
        if select_elder and valid_elder_range: # Ensure range was valid from step 2
            elder_weekdays = get_weekdays_in_range(elder_date_range[0], elder_date_range[1])
            overbooked_elder_dates = []

            if not elder_weekdays:
                processing_errors.append("Elder Care: Selected range contains no weekdays (Mon-Fri).")
                overall_availability = False
            else:
                for dt in elder_weekdays:
                    # get_weekdays_in_range now returns date objects
                    date_str = dt.strftime("%Y-%m-%d")
                    if current_booking_counts[date_str]["Elder Day Care"] >= MAX_CAPACITY:
                        overbooked_elder_dates.append(dt.strftime("%Y-%m-%d (%a)"))
                if overbooked_elder_dates:
                    overall_availability = False
                    processing_errors.append(f"Elder Care: Capacity limit ({MAX_CAPACITY}) reached on: {', '.join(overbooked_elder_dates)}")

            if overall_availability and elder_weekdays:
                num_days_elder = len(elder_weekdays)
                temp_elder_details = {
                    "dates": elder_weekdays, "num_days": num_days_elder,
                    "cost": num_days_elder * PRICES["Elder Day Care"]
                }

        # --- Process Child Care ---
        if select_child and valid_child_range and overall_availability: # Check overall avail. too
            child_weekdays = get_weekdays_in_range(child_date_range[0], child_date_range[1])
            overbooked_child_dates = []

            if not child_weekdays:
                if not any("Elder Care" in err and "no weekdays" in err for err in processing_errors):
                     processing_errors.append("Child Care: Selected range contains no weekdays (Mon-Fri).")
                overall_availability = False
            else:
                for dt in child_weekdays:
                    date_str = dt.strftime("%Y-%m-%d")
                    if current_booking_counts[date_str]["Child Day Care"] >= MAX_CAPACITY:
                        overbooked_child_dates.append(dt.strftime("%Y-%m-%d (%a)"))
                if overbooked_child_dates:
                    overall_availability = False
                    processing_errors.append(f"Child Care: Capacity limit ({MAX_CAPACITY}) reached on: {', '.join(overbooked_child_dates)}")

            if overall_availability and child_weekdays:
                num_days_child = len(child_weekdays)
                temp_child_details = {
                    "dates": child_weekdays, "num_days": num_days_child,
                    "cost": num_days_child * PRICES["Child Day Care"]
                }

        # 4. Finalize Booking State
        st.session_state.is_available = overall_availability

        if st.session_state.is_available:
            calculated_total_cost = 0
            if temp_elder_details:
                st.session_state.booking_details["Elder Day Care"] = temp_elder_details
                calculated_total_cost += temp_elder_details["cost"]
            if temp_child_details:
                st.session_state.booking_details["Child Day Care"] = temp_child_details
                calculated_total_cost += temp_child_details["cost"]
            st.session_state.total_cost = calculated_total_cost

            if st.session_state.total_cost <= 0:
                st.session_state.is_available = False
                if not processing_errors:
                    processing_errors.append("Selected range(s) resulted in zero valid booking days (Mon-Fri).")

        # 5. Update UI Placeholders based on results
        if not st.session_state.is_available:
            # Display errors collected during processing
            if processing_errors:
                 availability_placeholder.error("Booking Check Failed:\n\n* " + "\n* ".join(processing_errors))
            else: # Should not happen if validation passed, but as fallback
                 availability_placeholder.error("Booking Check Failed for an unknown reason.")

            summary_placeholder.empty()
            payment_placeholder.empty()
            st.session_state.booking_details = {}
            st.session_state.total_cost = 0
        else:
            availability_placeholder.success("Dates available! Please review the summary.")
            # Render Summary (in sidebar)
            summary_md = "#### Booking Summary:\n\n"
            for service_name, details in st.session_state.booking_details.items():
                 dates_str = ", ".join([d.strftime('%Y-%m-%d (%a)') for d in details['dates']])
                 summary_md += f"**{service_name}:**\n"
                 summary_md += f"- Dates: `{dates_str}`\n"
                 summary_md += f"- Weekdays: {details['num_days']}\n"
                 summary_md += f"- Cost: {CURRENCY_SYMBOL} {details['cost']:.2f}\n\n"
            summary_md += f"---\n#### Total Amount Payable: {CURRENCY_SYMBOL} {st.session_state.total_cost:.2f}"
            summary_placeholder.markdown(summary_md)

            # Render Payment Button (in main area)
            with payment_placeholder.container():
                st.subheader("Ready to Pay?")
                st.write(f"**Total Amount:** {CURRENCY_SYMBOL} {st.session_state.total_cost:.2f}")

                # Payment button action
                if st.button("Proceed to Payment (Simulated)", key="btn_pay"):
                    # --- PAYMENT API INTEGRATION SIMULATION ---
                    st.session_state.payment_status = "Success" # Simulate success
                    st.toast("Simulating successful payment...", icon="✅")

                    # Update simulated daily bookings
                    booked_services = st.session_state.booking_details
                    current_bookings = st.session_state.daily_bookings
                    for service_name, details in booked_services.items():
                        for dt in details['dates']:
                            date_str = dt.strftime("%Y-%m-%d")
                            current_bookings[date_str][service_name] += 1
                    st.session_state.daily_bookings = current_bookings

                    # Clear state & trigger rerun for UI update
                    st.session_state.booking_details = {}
                    st.session_state.total_cost = 0
                    st.session_state.availability_checked = False
                    st.session_state.is_available = False
                    # Reset checkbox states (optional, might depend on desired flow)
                    st.session_state.cb_elder = False
                    st.session_state.cb_child = True # Back to default
                    # Use rerun to clear inputs and update UI correctly after state reset
                    st.experimental_rerun()

# --- Display Payment Status Message (after payment attempt) ---
if st.session_state.payment_status:
    status_to_display = st.session_state.payment_status # Store before potentially clearing
    st.session_state.payment_status = None # Clear status after displaying once

    if status_to_display == "Success":
         st.success("Payment Successful! Your booking is confirmed (Simulation). Capacity updated.")
         st.balloons()
    else:
         st.error(f"Payment Failed: {status_to_display}")

# --- Default message in payment area if nothing else is shown ---
elif not st.session_state.is_available and st.session_state.availability_checked:
    pass # Error shown in sidebar by confirm_button logic
elif not st.session_state.availability_checked:
     payment_placeholder.info("Select service(s)/date(s) and click 'Check Availability' to proceed.")

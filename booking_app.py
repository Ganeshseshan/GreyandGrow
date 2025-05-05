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
    if start_date and end_date and start_date <= end_date:
        # Use pandas for easy date range generation and weekday filtering
        try:
            all_dates = pd.date_range(start=start_date, end=end_date, freq='D')
            # pandas weekday: Monday=0, Sunday=6
            weekdays_only = all_dates[all_dates.weekday < 5] # Keep Monday (0) to Friday (4)
            weekdays_list = weekdays_only.to_pydatetime().tolist() # Convert back to list of datetime objects
        except Exception as e:
            st.error(f"Error generating date range: {e}") # Should not happen with valid dates
            return []
    return weekdays_list

# --- Initialize Session State ---
# Streamlit reruns the script on interaction, so we use session_state
# to preserve data across runs.

# Initialize daily_bookings if it doesn't exist (simulates persistent storage)
if 'daily_bookings' not in st.session_state:
    # Structure: { "YYYY-MM-DD": { "Service Name": count } }
    st.session_state.daily_bookings = defaultdict(lambda: defaultdict(int))

# Initialize state for the current booking attempt
if 'booking_details' not in st.session_state:
    st.session_state.booking_details = {} # Will hold details per service
if 'total_cost' not in st.session_state:
    st.session_state.total_cost = 0
if 'availability_checked' not in st.session_state:
    st.session_state.availability_checked = False
if 'is_available' not in st.session_state:
    st.session_state.is_available = False
if 'payment_status' not in st.session_state:
    st.session_state.payment_status = None


# --- App Layout ---
st.set_page_config(layout="wide") # Use wider layout
st.title("☀️ Day Care Booking Service")

# --- Sidebar for Inputs ---
with st.sidebar:
    st.header("Step 1: Select Service(s) & Dates")
    st.markdown("---")

    # Service Selection
    select_elder = st.checkbox("Book Elder Day Care?", key="cb_elder")
    elder_date_range = None
    if select_elder:
        elder_date_range = st.date_input(
            "Select Elder Day Care Date Range:",
            value=(None, None), # Use tuple for range input
            min_value=datetime.date.today() + datetime.timedelta(days=1),
            format="YYYY-MM-DD",
            key="dr_elder"
        )

    st.markdown("---")
    select_child = st.checkbox("Book Child Day Care?", value=True, key="cb_child") # Default checked
    child_date_range = None
    if select_child:
        child_date_range = st.date_input(
            "Select Child Day Care Date Range:",
            value=(None, None),
            min_value=datetime.date.today() + datetime.timedelta(days=1),
            format="YYYY-MM-DD",
            key="dr_child"
        )

    st.markdown("---")

    # Confirmation Button
    confirm_button = st.button("Check Availability & Calculate Cost", type="primary")

    # Display status and summary in sidebar after check
    st.markdown("---")
    availability_placeholder = st.empty() # Placeholder for status message
    summary_placeholder = st.empty()      # Placeholder for summary details

# --- Main Area for Results & Payment ---
st.header("Step 2: Review and Proceed")
st.markdown("---")
payment_placeholder = st.empty() # Placeholder for payment button/status

# Expander to show current simulated bookings (for demo)
with st.expander("Show Current Simulated Bookings (Demo)"):
    # Convert defaultdicts to regular dicts for clean JSON display
    display_bookings = {date: dict(counts) for date, counts in st.session_state.daily_bookings.items()}
    if not display_bookings:
        st.write("No bookings recorded yet.")
    else:
        # Sort by date for readability
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
    st.session_state.payment_status = None # Clear previous payment status

    # 2. Input Validation
    processing_errors = []
    if not select_elder and not select_child:
        processing_errors.append("Please select at least one service type.")

    if select_elder and (not elder_date_range or len(elder_date_range) != 2 or not elder_date_range[0] or not elder_date_range[1]):
        processing_errors.append("Please select a valid start AND end date for Elder Day Care.")
    elif select_elder and elder_date_range[0] > elder_date_range[1]:
         processing_errors.append("Elder Care: Start date cannot be after end date.")

    if select_child and (not child_date_range or len(child_date_range) != 2 or not child_date_range[0] or not child_date_range[1]):
        processing_errors.append("Please select a valid start AND end date for Child Day Care.")
    elif select_child and child_date_range[0] > child_date_range[1]:
         processing_errors.append("Child Care: Start date cannot be after end date.")

    if processing_errors:
        availability_placeholder.error("Please fix the following issues:\n\n* " + "\n* ".join(processing_errors))
        st.session_state.availability_checked = False # Validation failed, so check wasn't really complete
    else:
        # 3. Process Selections and Check Capacity
        overall_availability = True
        temp_elder_details = None
        temp_child_details = None
        current_booking_counts = st.session_state.daily_bookings # Get current counts

        # --- Process Elder Care ---
        if select_elder:
            elder_weekdays = get_weekdays_in_range(elder_date_range[0], elder_date_range[1])
            overbooked_elder_dates = []

            if not elder_weekdays:
                processing_errors.append("Elder Care: Selected range contains no weekdays (Mon-Fri).")
                overall_availability = False
            else:
                for dt in elder_weekdays:
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
        # Only proceed if still available overall
        if select_child and overall_availability:
            child_weekdays = get_weekdays_in_range(child_date_range[0], child_date_range[1])
            overbooked_child_dates = []

            if not child_weekdays:
                # Avoid duplicate error message if elder care also had no weekdays
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
                st.session_state.is_available = False # Treat as unavailable if cost is zero
                if not processing_errors: # Add message if none exists
                    processing_errors.append("Selected range(s) resulted in zero valid booking days (Mon-Fri).")

        # 5. Update UI Placeholders based on results
        if not st.session_state.is_available:
            availability_placeholder.error("Booking Check Failed:\n\n* " + "\n* ".join(processing_errors))
            summary_placeholder.empty() # Clear summary if failed
            payment_placeholder.empty() # Clear payment section
            # Clear potentially partial details
            st.session_state.booking_details = {}
            st.session_state.total_cost = 0
        else:
            availability_placeholder.success("Dates available! Please review the summary.")
            # Render Summary (in sidebar)
            summary_md = "#### Booking Summary:\n\n"
            if "Elder Day Care" in st.session_state.booking_details:
                details = st.session_state.booking_details["Elder Day Care"]
                dates_str = ", ".join([d.strftime('%Y-%m-%d (%a)') for d in details['dates']])
                summary_md += f"**Elder Day Care:**\n"
                summary_md += f"- Dates: `{dates_str}`\n"
                summary_md += f"- Weekdays: {details['num_days']}\n"
                summary_md += f"- Cost: {CURRENCY_SYMBOL} {details['cost']:.2f}\n\n"
            if "Child Day Care" in st.session_state.booking_details:
                details = st.session_state.booking_details["Child Day Care"]
                dates_str = ", ".join([d.strftime('%Y-%m-%d (%a)') for d in details['dates']])
                summary_md += f"**Child Day Care:**\n"
                summary_md += f"- Dates: `{dates_str}`\n"
                summary_md += f"- Weekdays: {details['num_days']}\n"
                summary_md += f"- Cost: {CURRENCY_SYMBOL} {details['cost']:.2f}\n\n"
            summary_md += f"---\n#### Total Amount Payable: {CURRENCY_SYMBOL} {st.session_state.total_cost:.2f}"
            summary_placeholder.markdown(summary_md)

            # Render Payment Button (in main area)
            with payment_placeholder.container():
                st.subheader("Ready to Pay?")
                st.write(f"**Total Amount:** {CURRENCY_SYMBOL} {st.session_state.total_cost:.2f}")
                if st.button("Proceed to Payment (Simulated)", key="btn_pay"):
                    # --- THIS IS WHERE REAL PAYMENT API INTEGRATION WOULD START ---
                    # 1. Generate unique transaction ID
                    # 2. Prepare payload (amount, currency, description, callback URLs)
                    # 3. Make POST request using 'requests' library to payment gateway API
                    # 4. Handle response: Often involves redirecting user or using a JS library
                    # 5. Set up a separate webhook endpoint (maybe using Flask/FastAPI)
                    #    to receive payment confirmation from the gateway.
                    # 6. Update persistent storage (database) based on webhook.
                    # --- SIMULATION ---
                    st.session_state.payment_status = "Success" # Simulate success for now
                    st.toast("Simulating successful payment...", icon="✅")

                    # Update simulated daily bookings
                    booked_services = st.session_state.booking_details
                    current_bookings = st.session_state.daily_bookings
                    for service_name, details in booked_services.items():
                        for dt in details['dates']:
                            date_str = dt.strftime("%Y-%m-%d")
                            current_bookings[date_str][service_name] += 1
                    st.session_state.daily_bookings = current_bookings # Store updated counts

                    # Clear state and inputs after successful booking
                    st.session_state.booking_details = {}
                    st.session_state.total_cost = 0
                    st.session_state.availability_checked = False
                    st.session_state.is_available = False
                    # We can't directly clear input widgets easily without rerunning fully
                    # or complex callbacks. Usually, letting Streamlit rerun after success
                    # and clearing the state is sufficient as conditional UI will hide.
                    # Forcing a rerun might be possible using st.experimental_rerun() if needed.
                    availability_placeholder.empty()
                    summary_placeholder.empty()
                    st.experimental_rerun() # Rerun script to clear UI properly

# --- Display Payment Status Message ---
# This runs on every rerun if payment_status is set
if st.session_state.payment_status:
    if st.session_state.payment_status == "Success":
         # Show success message in main area (payment_placeholder is now empty)
         st.success("Payment Successful! Your booking is confirmed (Simulation). Capacity updated.")
         st.balloons()
    else:
         # Could handle failure simulation here if implemented
         st.error(f"Payment Failed: {st.session_state.payment_status}")
    # Clear status after displaying once? Optional.
    # st.session_state.payment_status = None

# Display default message in payment area if nothing else shown
elif not st.session_state.is_available and st.session_state.availability_checked:
    pass # Error shown in sidebar
elif not st.session_state.availability_checked:
     payment_placeholder.info("Select service(s)/date(s) and click 'Check Availability' to proceed.")

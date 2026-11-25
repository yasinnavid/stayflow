from datetime import date, timedelta
from decimal import Decimal
import html
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="StayFlow Athens", page_icon="🏨", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root { --navy:#102a43; --blue:#1473e6; --light:#f5f8fc; --muted:#66788a; --green:#16825d; --red:#c94141; }
[data-testid="stAppViewContainer"] { background:#f7f9fc; }
[data-testid="stHeader"] { background:rgba(0,0,0,0); }
.block-container { max-width:1180px; padding-top:2rem; padding-bottom:4rem; }
.sf-hero { background:linear-gradient(135deg,#102a43 0%,#1769aa 65%,#1f8ac0 100%); color:white; border-radius:24px; padding:34px 38px; margin-bottom:24px; box-shadow:0 16px 35px rgba(16,42,67,.13); }
.sf-hero h1 { margin:0; font-size:2.4rem; color:white; }
.sf-hero p { margin:.55rem 0 0; color:#e8f3ff; font-size:1.05rem; }
.sf-card { background:white; border:1px solid #e4eaf1; border-radius:18px; padding:20px 22px; margin:8px 0 14px; box-shadow:0 5px 18px rgba(16,42,67,.05); min-height:180px; }
.sf-card h3 { color:#102a43; margin:0 0 7px; }
.sf-chip { display:inline-block; padding:4px 9px; border-radius:99px; background:#eef6ff; color:#1668a8; font-size:.82rem; font-weight:700; margin-right:5px; }
.sf-price { font-size:1.55rem; font-weight:800; color:#102a43; margin-top:8px; }
.sf-muted { color:#66788a; }
.sf-status-ok { display:inline-block; background:#e8f6f0; color:#157355; border-radius:99px; padding:4px 10px; font-size:.8rem; font-weight:800; }
.sf-status-cancel { display:inline-block; background:#fdeeee; color:#ad3030; border-radius:99px; padding:4px 10px; font-size:.8rem; font-weight:800; }
div[data-testid="stForm"] { background:white; border:1px solid #e2e8f0; padding:22px; border-radius:18px; box-shadow:0 5px 18px rgba(16,42,67,.05); }
.stButton > button, .stFormSubmitButton > button { border-radius:10px; min-height:42px; font-weight:700; }
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] { background:#1473e6; border-color:#1473e6; }
[data-testid="stSidebar"] { background:#102a43; }
[data-testid="stSidebar"] * { color:#f3f7fb; }
[data-testid="stSidebar"] [role="radiogroup"] label { padding:.35rem 0; }
[data-testid="stSidebar"] button { color:#102a43 !important; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase()

DEFAULTS = {"user": None, "profile": None, "page": "Search hotels", "selected_hotel_id": None}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def safe(v):
    return html.escape(str(v or ""))


def load_profile():
    if not st.session_state.user:
        st.session_state.profile = None
        return None
    r = supabase.table("customers").select("*").eq("auth_user_id", st.session_state.user.id).maybe_single().execute()
    st.session_state.profile = r.data
    return r.data


@st.cache_data(ttl=60)
def get_hotels():
    return supabase.table("hotels").select("*").order("hotel_name").execute().data or []


def get_bookings():
    """Load the signed-in user's bookings, then attach hotel details locally.

    We deliberately use two simple queries instead of a nested PostgREST relationship
    query. This is more robust with the RLS/GRANT setup used by this learning app.
    """
    if not st.session_state.profile:
        return []

    booking_rows = (
        supabase.table("bookings")
        .select("booking_id,customer_id,hotel_id,check_in,check_out,guests,total_price,status,created_at")
        .eq("customer_id", st.session_state.profile["customer_id"])
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )

    hotel_lookup = {h["hotel_id"]: h for h in get_hotels()}
    for booking in booking_rows:
        booking["hotels"] = hotel_lookup.get(booking["hotel_id"], {})

    return booking_rows


def go_to_booking(hotel_id):
    # Callback executes before Streamlit reruns, which fixes the occasional dead-looking Book click.
    st.session_state.selected_hotel_id = int(hotel_id)
    st.session_state.page = "Book hotel"


def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    st.rerun()


def hero(title, subtitle):
    st.markdown(f'<div class="sf-hero"><h1>{safe(title)}</h1><p>{safe(subtitle)}</p></div>', unsafe_allow_html=True)


def auth_page():
    hero("StayFlow Athens", "Find a simple stay in Athens. This fictional booking app feeds our real data-engineering project.")
    left, middle, right = st.columns([1, 1.6, 1])
    with middle:
        login, register = st.tabs(["Sign in", "Create account"])
        with login:
            st.write("### Welcome back")
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="name@example.com")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Sign in", type="primary", use_container_width=True)
            if submit:
                try:
                    r = supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": password})
                    st.session_state.user = r.user
                    load_profile()
                    st.rerun()
                except Exception:
                    st.error("Sign-in failed. Check your email and password.")
        with register:
            st.write("### Create your StayFlow account")
            with st.form("register_form"):
                c1, c2 = st.columns(2)
                first = c1.text_input("First name")
                last = c2.text_input("Last name")
                country = st.text_input("Country", value="Greece")
                email = st.text_input("Email", key="register_email")
                password = st.text_input("Password", type="password", key="register_password")
                confirm = st.text_input("Confirm password", type="password")
                submit = st.form_submit_button("Create account", type="primary", use_container_width=True)
            if submit:
                if not all([first.strip(), last.strip(), country.strip(), email.strip(), password, confirm]):
                    st.error("Complete all fields.")
                elif password != confirm:
                    st.error("Passwords do not match.")
                elif len(password) < 6:
                    st.error("Password must contain at least 6 characters.")
                else:
                    try:
                        r = supabase.auth.sign_up({"email": email.strip().lower(), "password": password,
                            "options": {"data": {"first_name": first.strip(), "last_name": last.strip(), "country": country.strip()}}})
                        if r.session:
                            st.session_state.user = r.user
                            load_profile()
                            st.rerun()
                        else:
                            st.success("Account created. Confirm your email if requested, then sign in.")
                    except Exception as e:
                        st.error("Account creation failed.")
                        st.caption(str(e))


def search_page():
    hero("Find your stay in Athens", "Browse our 20 fictional Athens hotels and create real booking records in PostgreSQL.")
    hs = get_hotels()
    if not hs:
        st.warning("No hotels found in the database.")
        return
    areas = sorted({h["area"] for h in hs if h.get("area")})
    st.write("### Search & filter")
    c1, c2, c3 = st.columns([1.4, 1, 1])
    q = c1.text_input("Hotel or area", placeholder="Try Plaka or Acropolis")
    area = c2.selectbox("Area", ["All areas"] + areas)
    highest = max(int(float(h["price_per_night"])) for h in hs)
    max_price = c3.slider("Maximum nightly price", 50, max(350, highest), max(350, highest), 10, format="€%d")
    needle = q.strip().lower()
    shown = [h for h in hs if (not needle or needle in h["hotel_name"].lower() or needle in h["area"].lower())
             and (area == "All areas" or h["area"] == area) and float(h["price_per_night"]) <= max_price]
    st.write(f"### {len(shown)} stays found")
    for h in shown:
        a, b = st.columns([3.4, 1.2], vertical_alignment="center")
        with a:
            st.markdown(f"""<div class="sf-card">
                <span class="sf-chip">{safe(h['area'])}</span><span class="sf-chip">{'★' * int(h['stars'])}</span>
                <h3>{safe(h['hotel_name'])}</h3>
                <p class="sf-muted">📍 {safe(h['area'])}, Athens</p>
                <p>{safe(h.get('description') or 'A comfortable stay in Athens.')}</p>
            </div>""", unsafe_allow_html=True)
        with b:
            st.markdown(f'<div class="sf-price">€{float(h["price_per_night"]):,.0f}</div><div class="sf-muted">per night</div><br>', unsafe_allow_html=True)
            st.button("View & book", key=f"book_{h['hotel_id']}", type="primary", use_container_width=True,
                      on_click=go_to_booking, args=(h["hotel_id"],))


def booking_page():
    hero("Complete your booking", "Choose the hotel, dates and number of guests. StayFlow calculates the transaction value automatically.")
    hs = get_hotels()
    ids = [h["hotel_id"] for h in hs]
    if not ids:
        st.warning("No hotels available.")
        return
    idx = ids.index(st.session_state.selected_hotel_id) if st.session_state.selected_hotel_id in ids else 0
    hid = st.selectbox("Hotel", ids, index=idx,
                       format_func=lambda x: next(f"{h['hotel_name']} · {h['area']} · €{float(h['price_per_night']):,.0f}/night" for h in hs if h['hotel_id'] == x))
    h = next(h for h in hs if h["hotel_id"] == hid)
    st.markdown(f"""<div class="sf-card"><span class="sf-chip">{safe(h['area'])}</span><span class="sf-chip">{'★' * int(h['stars'])}</span>
    <h3>{safe(h['hotel_name'])}</h3><p>{safe(h.get('description'))}</p><div class="sf-price">€{float(h['price_per_night']):,.2f} <span class="sf-muted" style="font-size:.9rem;font-weight:500">/ night</span></div></div>""", unsafe_allow_html=True)
    with st.form("booking_form"):
        c1, c2, c3 = st.columns(3)
        checkin = c1.date_input("Check-in", date.today() + timedelta(days=1), min_value=date.today())
        checkout = c2.date_input("Check-out", date.today() + timedelta(days=3), min_value=date.today() + timedelta(days=1))
        guests = c3.number_input("Guests", min_value=1, max_value=10, value=2, step=1)
        nights = max((checkout - checkin).days, 0)
        total = Decimal(str(h["price_per_night"])) * nights
        st.info(f"**Booking summary:** {nights} night{'s' if nights != 1 else ''} × €{float(h['price_per_night']):,.2f} = **€{float(total):,.2f}**")
        submit = st.form_submit_button("Confirm booking", type="primary", use_container_width=True)
    if submit:
        if checkout <= checkin:
            st.error("Check-out must be after check-in.")
        else:
            try:
                supabase.table("bookings").insert({"customer_id": st.session_state.profile["customer_id"], "hotel_id": hid,
                    "check_in": checkin.isoformat(), "check_out": checkout.isoformat(), "guests": int(guests),
                    "total_price": float(total), "status": "confirmed"}).execute()
                st.session_state.selected_hotel_id = None
                st.success(f"Booking confirmed at {h['hotel_name']} for €{float(total):,.2f}.")
                st.balloons()
            except Exception as e:
                st.error("Booking failed.")
                st.caption(str(e))


def bookings_page():
    hero("My bookings", "Review active and cancelled stays. We keep cancellations as history instead of deleting the transaction.")
    bs = get_bookings()
    if not bs:
        st.info("You have no bookings yet. Visit Search hotels to create your first one.")
        return
    active = sum(1 for b in bs if b["status"] == "confirmed")
    cancelled = sum(1 for b in bs if b["status"] == "cancelled")
    c1, c2, c3 = st.columns(3)
    c1.metric("Bookings", len(bs)); c2.metric("Confirmed", active); c3.metric("Cancelled", cancelled)
    st.write("")
    for b in bs:
        h = b.get("hotels") or {}
        status_html = '<span class="sf-status-ok">CONFIRMED</span>' if b["status"] == "confirmed" else '<span class="sf-status-cancel">CANCELLED</span>'
        a, c = st.columns([4, 1.1], vertical_alignment="center")
        with a:
            st.markdown(f"""<div class="sf-card">{status_html}<h3>{safe(h.get('hotel_name','Hotel'))}</h3>
            <p class="sf-muted">📍 {safe(h.get('area','Athens'))}, Athens</p>
            <p><b>{safe(b['check_in'])}</b> → <b>{safe(b['check_out'])}</b> &nbsp; · &nbsp; {int(b['guests'])} guest{'s' if int(b['guests']) != 1 else ''}</p>
            <div class="sf-price">€{float(b['total_price']):,.2f}</div></div>""", unsafe_allow_html=True)
        with c:
            if b["status"] == "confirmed" and date.fromisoformat(b["check_in"]) > date.today():
                if st.button("Cancel booking", key=f"cancel_{b['booking_id']}", use_container_width=True):
                    try:
                        supabase.table("bookings").update({"status": "cancelled"}).eq("booking_id", b["booking_id"]).eq("customer_id", st.session_state.profile["customer_id"]).execute()
                        st.success("Booking cancelled.")
                        st.rerun()
                    except Exception as e:
                        st.error("Cancellation failed."); st.caption(str(e))


def reviews_page():
    hero("Share your stay", "Reviews become available after a confirmed stay's check-out date.")
    reviewed = supabase.table("reviews").select("booking_id").eq("customer_id", st.session_state.profile["customer_id"]).execute().data or []
    reviewed_ids = {x["booking_id"] for x in reviewed}
    eligible = [b for b in get_bookings() if b["status"] == "confirmed" and date.fromisoformat(b["check_out"]) <= date.today() and b["booking_id"] not in reviewed_ids]
    if not eligible:
        st.info("No completed, unreviewed stays are available yet.")
        return
    bid = st.selectbox("Completed stay", [b["booking_id"] for b in eligible],
                       format_func=lambda x: next(f"{(b.get('hotels') or {}).get('hotel_name','Hotel')} · {b['check_in']} to {b['check_out']}" for b in eligible if b['booking_id'] == x))
    b = next(b for b in eligible if b["booking_id"] == bid)
    with st.form("review_form"):
        rating = st.slider("Rating", 1, 5, 5)
        comment = st.text_area("Your review", placeholder="What was good about the stay?", max_chars=1000)
        submit = st.form_submit_button("Submit review", type="primary", use_container_width=True)
    if submit:
        if not comment.strip():
            st.error("Please write a short review.")
        else:
            try:
                supabase.table("reviews").insert({"customer_id": st.session_state.profile["customer_id"], "hotel_id": b["hotel_id"],
                    "booking_id": b["booking_id"], "rating": int(rating), "comment": comment.strip()}).execute()
                st.success("Review submitted. Thank you!"); st.rerun()
            except Exception as e:
                st.error("Review submission failed."); st.caption(str(e))


def main():
    if st.session_state.user is None:
        auth_page(); return
    if not st.session_state.profile:
        load_profile()
    if not st.session_state.profile:
        st.error("Customer profile could not be loaded.")
        if st.button("Sign out"): logout()
        return
    with st.sidebar:
        st.markdown("## 🏨 StayFlow")
        st.caption("ATHENS")
        st.write(f"Welcome, **{st.session_state.profile['first_name']}**")
        st.caption(st.session_state.profile["email"])
        st.divider()
        pages = ["Search hotels", "Book hotel", "My bookings", "Leave a review"]
        chosen = st.radio("Navigation", pages, index=pages.index(st.session_state.page), label_visibility="collapsed")
        # Only overwrite page when radio itself changed; callbacks can set page safely before rerun.
        if chosen != st.session_state.page:
            st.session_state.page = chosen
        st.divider()
        if st.button("Sign out", use_container_width=True): logout()
    page = st.session_state.page
    {"Search hotels": search_page, "Book hotel": booking_page, "My bookings": bookings_page, "Leave a review": reviews_page}[page]()

main()

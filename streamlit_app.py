from datetime import date, timedelta
from decimal import Decimal
import streamlit as st
from supabase import create_client

st.set_page_config(page_title='StayFlow Athens', page_icon='🏨', layout='wide')

@st.cache_resource
def get_supabase():
    return create_client(st.secrets['SUPABASE_URL'], st.secrets['SUPABASE_KEY'])

supabase = get_supabase()

for key, value in {'user': None, 'profile': None, 'page': 'Search hotels', 'selected_hotel_id': None}.items():
    if key not in st.session_state:
        st.session_state[key] = value

def load_profile():
    if not st.session_state.user:
        return None
    r = supabase.table('customers').select('*').eq('auth_user_id', st.session_state.user.id).maybe_single().execute()
    st.session_state.profile = r.data
    return r.data

def hotels():
    return supabase.table('hotels').select('*').order('hotel_name').execute().data or []

def bookings():
    if not st.session_state.profile:
        return []
    return (supabase.table('bookings')
            .select('booking_id,customer_id,hotel_id,check_in,check_out,guests,total_price,status,created_at,hotels(hotel_name,area,stars,price_per_night)')
            .eq('customer_id', st.session_state.profile['customer_id'])
            .order('created_at', desc=True).execute().data or [])

def logout():
    try: supabase.auth.sign_out()
    except Exception: pass
    st.session_state.user = None
    st.session_state.profile = None
    st.session_state.page = 'Search hotels'
    st.rerun()

def auth_page():
    st.title('🏨 StayFlow Athens')
    st.caption('A fictional Athens hotel-booking app for our data engineering project.')
    login, register = st.tabs(['Sign in', 'Create account'])
    with login:
        with st.form('login'):
            email = st.text_input('Email')
            password = st.text_input('Password', type='password')
            submit = st.form_submit_button('Sign in', use_container_width=True)
        if submit:
            try:
                r = supabase.auth.sign_in_with_password({'email': email.strip().lower(), 'password': password})
                st.session_state.user = r.user
                load_profile()
                st.rerun()
            except Exception as e:
                st.error('Sign-in failed. Check your email and password.')
                st.caption(str(e))
    with register:
        with st.form('register'):
            first = st.text_input('First name')
            last = st.text_input('Last name')
            country = st.text_input('Country', value='Greece')
            email = st.text_input('Email', key='reg_email')
            password = st.text_input('Password', type='password', key='reg_password')
            confirm = st.text_input('Confirm password', type='password')
            submit = st.form_submit_button('Create account', use_container_width=True)
        if submit:
            if not all([first.strip(), last.strip(), email.strip(), password, confirm]):
                st.error('Complete all fields.')
            elif password != confirm:
                st.error('Passwords do not match.')
            elif len(password) < 6:
                st.error('Password must contain at least 6 characters.')
            else:
                try:
                    r = supabase.auth.sign_up({'email': email.strip().lower(), 'password': password,
                        'options': {'data': {'first_name': first.strip(), 'last_name': last.strip(), 'country': country.strip()}}})
                    if r.session:
                        st.session_state.user = r.user
                        load_profile()
                        st.rerun()
                    else:
                        st.success('Account created. Confirm your email if required, then sign in.')
                except Exception as e:
                    st.error('Account creation failed.')
                    st.caption(str(e))

def search_page():
    st.header('🔎 Search hotels')
    hs = hotels()
    areas = sorted({h['area'] for h in hs})
    c1, c2, c3 = st.columns(3)
    q = c1.text_input('Hotel name or area')
    area = c2.selectbox('Area', ['All areas'] + areas)
    max_price = c3.slider('Maximum price per night', 50, 350, 350, 10, format='€%d')
    shown = [h for h in hs if (not q or q.lower() in h['hotel_name'].lower() or q.lower() in h['area'].lower()) and (area == 'All areas' or h['area'] == area) and float(h['price_per_night']) <= max_price]
    st.write(f'**{len(shown)} hotels found**')
    for h in shown:
        a,b = st.columns([4,1])
        with a:
            st.subheader(h['hotel_name'])
            st.write(f"📍 {h['area']}, Athens  |  {'⭐' * int(h['stars'])}")
            st.write(h.get('description') or '')
        with b:
            st.metric('Per night', f"€{float(h['price_per_night']):,.2f}")
            if st.button('Book', key=f"book{h['hotel_id']}", use_container_width=True):
                st.session_state.selected_hotel_id = h['hotel_id']
                st.session_state.page = 'Book hotel'
                st.rerun()
        st.divider()

def booking_page():
    st.header('📅 Book hotel')
    hs = hotels()
    ids = [h['hotel_id'] for h in hs]
    idx = ids.index(st.session_state.selected_hotel_id) if st.session_state.selected_hotel_id in ids else 0
    hid = st.selectbox('Hotel', ids, index=idx, format_func=lambda x: next(h['hotel_name'] for h in hs if h['hotel_id']==x))
    h = next(h for h in hs if h['hotel_id']==hid)
    st.write(f"📍 {h['area']}, Athens | {'⭐' * int(h['stars'])} | €{float(h['price_per_night']):,.2f}/night")
    with st.form('booking'):
        c1,c2,c3 = st.columns(3)
        checkin = c1.date_input('Check-in', date.today()+timedelta(days=1), min_value=date.today())
        checkout = c2.date_input('Check-out', date.today()+timedelta(days=3), min_value=date.today()+timedelta(days=1))
        guests = c3.number_input('Guests', 1, 10, 2)
        nights = max((checkout-checkin).days,0)
        total = Decimal(str(h['price_per_night'])) * nights
        st.info(f'{nights} nights × €{float(h["price_per_night"]):,.2f} = €{float(total):,.2f}')
        submit = st.form_submit_button('Confirm booking', use_container_width=True)
    if submit:
        if checkout <= checkin:
            st.error('Check-out must be after check-in.')
        else:
            try:
                supabase.table('bookings').insert({'customer_id': st.session_state.profile['customer_id'], 'hotel_id': hid,
                    'check_in': checkin.isoformat(), 'check_out': checkout.isoformat(), 'guests': int(guests),
                    'total_price': float(total), 'status': 'confirmed'}).execute()
                st.success('Booking confirmed.')
                st.balloons()
            except Exception as e:
                st.error('Booking failed.')
                st.caption(str(e))

def my_bookings_page():
    st.header('🧳 My bookings')
    bs = bookings()
    if not bs:
        st.info('You have no bookings yet.')
    for b in bs:
        h = b.get('hotels') or {}
        st.subheader(h.get('hotel_name','Hotel'))
        c1,c2,c3 = st.columns(3)
        c1.write(f"**Check-in:** {b['check_in']}\n\n**Check-out:** {b['check_out']}")
        c2.write(f"**Guests:** {b['guests']}\n\n**Area:** {h.get('area','Athens')}")
        c3.write(f"**Total:** €{float(b['total_price']):,.2f}\n\n**Status:** {b['status'].title()}")
        if b['status'] == 'confirmed' and date.fromisoformat(b['check_in']) > date.today():
            if st.button('Cancel booking', key=f"cancel{b['booking_id']}"):
                try:
                    supabase.table('bookings').update({'status':'cancelled'}).eq('booking_id',b['booking_id']).eq('customer_id',st.session_state.profile['customer_id']).execute()
                    st.rerun()
                except Exception as e:
                    st.error('Cancellation failed.')
                    st.caption(str(e))
        st.divider()

def review_page():
    st.header('⭐ Leave a review')
    reviewed = supabase.table('reviews').select('booking_id').eq('customer_id',st.session_state.profile['customer_id']).execute().data or []
    reviewed_ids = {x['booking_id'] for x in reviewed}
    eligible = [b for b in bookings() if b['status']=='confirmed' and date.fromisoformat(b['check_out']) <= date.today() and b['booking_id'] not in reviewed_ids]
    if not eligible:
        st.info('No completed unreviewed stays are available yet.')
        return
    bid = st.selectbox('Completed stay', [b['booking_id'] for b in eligible], format_func=lambda x: next((b.get('hotels') or {}).get('hotel_name','Hotel') for b in eligible if b['booking_id']==x))
    b = next(b for b in eligible if b['booking_id']==bid)
    with st.form('review'):
        rating = st.slider('Rating',1,5,5)
        comment = st.text_area('Review')
        submit = st.form_submit_button('Submit review', use_container_width=True)
    if submit:
        if not comment.strip():
            st.error('Please write a short review.')
        else:
            try:
                supabase.table('reviews').insert({'customer_id':st.session_state.profile['customer_id'], 'hotel_id':b['hotel_id'], 'booking_id':b['booking_id'], 'rating':rating, 'comment':comment.strip()}).execute()
                st.success('Review submitted.')
                st.rerun()
            except Exception as e:
                st.error('Review submission failed.')
                st.caption(str(e))

def main():
    if st.session_state.user is None:
        auth_page(); return
    if not st.session_state.profile:
        load_profile()
    if not st.session_state.profile:
        st.error('Customer profile could not be loaded. Check the Supabase trigger and RLS setup.')
        if st.button('Sign out'): logout()
        return
    with st.sidebar:
        st.title('🏨 StayFlow')
        st.write(f"Welcome, **{st.session_state.profile['first_name']}**")
        pages = ['Search hotels','Book hotel','My bookings','Leave a review']
        page = st.radio('Navigation', pages, index=pages.index(st.session_state.page))
        st.session_state.page = page
        if st.button('Sign out', use_container_width=True): logout()
    st.title('StayFlow Athens')
    st.caption('Simple booking app • Fictional hotels • Real PostgreSQL data')
    {'Search hotels':search_page,'Book hotel':booking_page,'My bookings':my_bookings_page,'Leave a review':review_page}[page]()

main()

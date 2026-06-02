from datetime import datetime, timezone

def send_auto_message(db, sender_id, recipient_id, content):
    """
    Sends an automated message from sender_id to recipient_id.
    If a 1-to-1 conversation doesn't exist, it creates one first.
    """
    if not sender_id or not recipient_id or not content:
        return None

    try:
        # 1. Fetch conversations of the sender
        mine_resp = db.table('conversation_participants').select('conversation_id').eq('profile_id', sender_id).execute()
        mine_ids = [r['conversation_id'] for r in (mine_resp.data or [])]

        convo_id = None
        if mine_ids:
            # 2. Check if recipient shares any of those conversation IDs
            shared_resp = db.table('conversation_participants').select('conversation_id').eq('profile_id', recipient_id).in_('conversation_id', mine_ids).execute()
            if shared_resp.data:
                convo_id = shared_resp.data[0]['conversation_id']

        # 3. Create conversation if it doesn't exist
        if not convo_id:
            new_convo_resp = db.table('conversations').insert({}).execute()
            if not new_convo_resp.data:
                print(f"[send_auto_message] Failed to create new conversation between {sender_id} and {recipient_id}")
                return None
            convo_id = new_convo_resp.data[0]['id']

            # Insert both participants
            db.table('conversation_participants').insert([
                {'conversation_id': convo_id, 'profile_id': sender_id},
                {'conversation_id': convo_id, 'profile_id': recipient_id}
            ]).execute()

        # 4. Insert message
        msg_resp = db.table('messages').insert({
            'conversation_id': convo_id,
            'sender_id': sender_id,
            'content': content
        }).execute()

        # 5. Update updated_at on the conversation to bubble it up
        now_str = datetime.now(timezone.utc).isoformat()
        db.table('conversations').update({'updated_at': now_str}).eq('id', convo_id).execute()

        return msg_resp.data
    except Exception as e:
        print(f"[send_auto_message] Error sending auto chat from {sender_id} to {recipient_id}: {e}")
        return None


def trigger_booking_autochat(db, reservation_id, player_id):
    """
    Triggers automated chats from the facility owner and assigned staff to the player who booked.
    """
    if not reservation_id or not player_id:
        return

    try:
        # Fetch reservation details with facility and court info
        res_resp = db.table('court_reservations').select(
            'id, date, start_time, end_time, facility_id, '
            'facilities(name, owner_id), courts(name)'
        ).eq('id', reservation_id).single().execute()

        res = res_resp.data
        if not res:
            print(f"[trigger_booking_autochat] Reservation {reservation_id} not found.")
            return

        facility_id = res.get('facility_id')
        facility = res.get('facilities') or {}
        court = res.get('courts') or {}

        facility_name = facility.get('name', 'our facility')
        owner_id = facility.get('owner_id')
        court_name = court.get('name', 'Court')
        date_val = res.get('date')
        start_time = res.get('start_time')
        end_time = res.get('end_time')

        # Format times for cleaner display (HH:MM)
        time_range = f"{start_time} - {end_time}"
        try:
            if start_time and len(start_time) >= 5:
                start_formatted = start_time[:5]
            else:
                start_formatted = start_time
            if end_time and len(end_time) >= 5:
                end_formatted = end_time[:5]
            else:
                end_formatted = end_time
            time_range = f"{start_formatted} - {end_formatted}"
        except Exception:
            pass

        # 1. Message from Facility Owner
        if owner_id:
            owner_message = (
                f"Thank you for booking at {facility_name}! "
                f"Your reservation for {court_name} on {date_val} ({time_range}) has been confirmed. "
                f"If you have any questions, feel free to message me here."
            )
            send_auto_message(db, owner_id, player_id, owner_message)

        # 2. Messages from Facility Staff members
        if facility_id:
            # Fetch staff profile IDs associated with this facility
            staff_resp = db.table('facility_staff').select(
                'staff_id, profiles(first_name, last_name)'
            ).eq('facility_id', facility_id).execute()

            staff_list = staff_resp.data or []
            for item in staff_list:
                staff_id = item.get('staff_id')
                profile = item.get('profiles') or {}
                first_name = profile.get('first_name', 'Staff')
                last_name = profile.get('last_name', '')
                staff_name = f"{first_name} {last_name}".strip()

                # Avoid sending duplicate message if the owner is also registered as staff
                if staff_id and staff_id != owner_id:
                    staff_message = (
                        f"Hi! I'm {staff_name}, one of the facility staff members on duty. "
                        f"I will handle your queue for this booking, and I will notify you when it's your next."
                    )
                    send_auto_message(db, staff_id, player_id, staff_message)

    except Exception as e:
        print(f"[trigger_booking_autochat] Error triggering autochat for reservation {reservation_id}: {e}")

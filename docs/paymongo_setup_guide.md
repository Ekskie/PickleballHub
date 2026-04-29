# PayMongo Setup Guide for PickleballHub

This guide outlines the steps required to integrate PayMongo into the PickleballHub platform to handle GCash payments securely and efficiently, especially considering the multi-vendor (multiple facility owners) structure.

## 1. Account Creation and Keys

1.  **Register**: Go to [PayMongo](https://paymongo.com/) and create a business account. You will start in **Test Mode**.
2.  **API Keys**: Navigate to the **Developers** section in the PayMongo dashboard.
3.  **Secure Keys**: You will find a `Public Key` and a `Secret Key`.
    -   *Never* expose the Secret Key in the frontend JavaScript. It should only be used in the Flask backend.
    -   Add these keys to your `.env` file:
        ```env
        PAYMONGO_PUBLIC_KEY=pk_test_xxxxxxxxxxxxx
        PAYMONGO_SECRET_KEY=sk_test_xxxxxxxxxxxxx
        ```

## 2. The Checkout Workflow (Multi-Vendor)

Since PickleballHub has multiple Facility Owners, we need to make sure the funds are tracked correctly. The recommended approach for this marketplace-like setup using PayMongo is:

1.  **Centralized Collection**: PickleballHub collects the payment directly using a PayMongo **Payment Link** or **Checkout Session API**.
2.  **Database Tracking**: When the payment is confirmed, the system logs the earnings to the specific `Facility Owner` associated with the booked court in Supabase.
3.  **Payouts**: The Super Admin or System handles scheduled payouts (e.g., weekly or monthly) to the Facility Owners' respective bank accounts or GCash numbers based on the earnings tracked in Supabase.

### Step-by-Step API Flow

1.  **Player Clicks "Pay with GCash"**:
    -   The frontend sends a `fetch` request to your Flask backend with the booking details (Facility ID, Court ID, Amount).
2.  **Flask Creates a Checkout Session**:
    -   Flask uses the `PAYMONGO_SECRET_KEY` to call the PayMongo API: `POST https://api.paymongo.com/v1/checkout_sessions`
    -   Specify the payment method (`gcash`), amount, currency (`PHP`), and a `reference_number` (this should be the Booking ID from Supabase).
3.  **Redirection**:
    -   PayMongo responds with a Checkout URL.
    -   Flask sends this URL back to the frontend.
    -   The frontend redirects the player to the PayMongo/GCash portal to scan or log in and pay.
4.  **Payment Completion**:
    -   After paying, the player is redirected back to the PickleballHub success page.

## 3. Handling Webhooks (Crucial Step)

Webhooks are automated messages sent from PayMongo to your Flask server when a payment is successful. You *must* rely on webhooks to confirm bookings, not the user returning to the success page (because they might close the tab early).

1.  **Create a Webhook Endpoint in Flask**:
    ```python
    @app.route('/api/webhooks/paymongo', methods=['POST'])
    def paymongo_webhook():
        payload = request.json
        # 1. Verify the webhook signature (security)
        # 2. Check if the event type is 'payment.paid'
        # 3. Extract the reference_number (Booking ID)
        # 4. Update the booking status in Supabase to 'Confirmed'
        # 5. Return 200 OK
    ```
2.  **Register the Webhook in PayMongo Dashboard**:
    -   Go to Developers -> Webhooks in PayMongo.
    -   Add your deployed URL (e.g., `https://your-pickleball-hub-url.com/api/webhooks/paymongo`).
    -   Select the events to listen for (e.g., `payment.paid`, `payment.failed`).

## 4. Local Testing (ngrok)

To test webhooks locally (since PayMongo cannot reach `http://localhost:5000`):
1.  Download and install [ngrok](https://ngrok.com/).
2.  Run `ngrok http 5000` in your terminal.
3.  ngrok will give you a public HTTPS URL (e.g., `https://a1b2c3d4.ngrok.io`).
4.  Use this ngrok URL as your Webhook URL in the PayMongo dashboard during development.

## Next Steps for Development

1.  **Install Requests Library**: Ensure `requests` is installed in your Flask environment to make API calls to PayMongo.
2.  **Database Update**: Ensure the Supabase `reservations` table has fields for `payment_status` (pending, paid, failed) and `paymongo_reference_id`.
3.  **Build the Checkout Endpoint**: Implement the Flask route that initiates the PayMongo Checkout Session.

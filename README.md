# CRASH Analyzer

A mobile-friendly Streamlit dashboard for analyzing recorded CRASH multipliers and tracking a hypothetical coin balance.

## Run locally

1. Install Python 3.10+.
2. In this folder, run:

   ```bash
   python -m venv .venv
   # Windows: .venv\Scripts\activate
   # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   streamlit run app.py
   ```

3. Open the local URL shown by Streamlit. On a phone, use the same Wi-Fi network and the computer's LAN address if you launch Streamlit with `--server.address 0.0.0.0`.

## Live history feed

The app accepts an HTTPS JSON endpoint that you are authorized to access and polls it at the selected interval while the dashboard is open. Supported response shapes:

```json
[
  {"round_id": "abc123", "timestamp": "2026-11-08T00:00:00Z", "multiplier": 1.82},
  {"round_id": "abc124", "timestamp": "2026-11-08T00:01:00Z", "multiplier": 3.41}
]
```

or:

```json
{"rounds": [{"id": "abc123", "multiplier": "1.82x"}]}
```

The feed must return JSON. If the platform does not provide an authorized API/feed, use CSV import or manual entry. This app does not scrape protected pages, bypass authentication, or automate bets.

## Starting balance

The default current balance is 500 coins and the default target is 770,899 coins. The dashboard calculates the remaining 770,399 coins and shows progress. These are tracking values only; the app does not connect to or modify any casino wallet.

## Limitations

- Historical frequencies are descriptive, not predictive.
- No 98% accuracy or guaranteed recovery is claimed.
- The simple historical simulation ignores fees, bet limits, and provider-specific settlement rules.
- API token is entered in the current Streamlit session; do not use your account password or wallet secrets.

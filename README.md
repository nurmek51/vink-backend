# Vink Backend

## Architecture Overview

This backend serves two client applications:
1. **Vink Wallet** (External App)
2. **Vink eSIM Management** (Internal App)

It uses a **Single Identity Model** where users are shared across both apps, but domain data is isolated.

### Stack
- **Framework**: FastAPI
- **Database**: Firebase Firestore
- **Auth**: JWT + Mocked OTP (Twilio ready)
- **Provider**: Imsimarket (eSIM)

### Project Structure
- `app/core`: Configuration, Security, JWT
- `app/modules`: Feature modules (Auth, Users, Wallet, eSIM)
- `app/providers`: External API integrations (Isolated)
- `app/infrastructure`: Database connections
- `app/common`: Shared utilities

## Authentication Flow

1. **Request OTP**: `POST /api/v1/otp/whatsapp` with `phone_number`.
2. **Verify OTP**: `POST /api/v1/otp/verify` with `phone_number` and `otp_code`.
3. **Receive Token**: JWT token returned.
4. **Access Protected Routes**: Send `Authorization: Bearer <token>` header.

### Token Sharing
The JWT contains `apps: ["vink", "vink-sim"]`.
- If a user logs in via Vink, they get a token valid for Vink.
- If they access Vink SIM, the same token works (if they have permission).
- `require_app_permission` dependency enforces access control.

## Database Schema (Firestore)

- `users/{user_id}`: Shared user profile.
- `vink_wallet_accounts/{wallet_id}`: Wallet data (Isolated).
- `vink_sim_esims/{esim_id}`: eSIM data (Isolated).

## Provider Integration

The `app/providers/esim_provider` module handles communication with Imsimarket.
- **Client**: Handles Auth and HTTP requests.
- **Mapper**: Converts Provider responses to Domain entities.
- **Schemas**: Pydantic models for Provider API.

To add a new provider:
1. Create `app/providers/new_provider/`.
2. Implement `client.py`, `mapper.py`, `schemas.py`.
3. Use it in the relevant Service.

## Security

- **JWT**: Validated on every protected request.
- **Domain Isolation**: Wallet logic cannot access eSIM data directly and vice versa.
- **Secrets**: Managed via `.env` (pydantic-settings).

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Set environment variables in `.env`.
3. Run: `uvicorn app.main:app --reload`

## Mock OTP
Currently, OTP is mocked.
- Code: `123456`
- Allowed Phone: `+77777777751`

To replace with Twilio:
1. Update `app/modules/auth/service.py`.
2. Add Twilio credentials to `app/core/config.py`.

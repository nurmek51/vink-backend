# VinkSIM API Integration Documentation

## Overview

This document provides comprehensive API integration details for the VinkSIM application.
Use this as a reference when integrating the real backend API.

**Current Status:** Backend Ready
**Mock Data Location:** `lib/core/mock/mock_data.dart` (Client side)

---

## API Configuration

### Base URLs

| Environment | URL                                    |
|-------------|----------------------------------------|
| Development | `http://localhost:8000/api/v1`         |
| Production  | From `Environment.apiUrl` (.env file)  |

### Authentication

All authenticated endpoints require:
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
Accept: application/json
```

### Response Format Wrapper

Most successful data responses are wrapped in a standard structure:
```json
{
  "success": true,
  "message": "Success",
  "data": { ... }
}
```

Empty successful responses (actions etc):
```json
{
  "success": true,
  "message": "Success"
}
```

---

## API Endpoints

### Payment APIs (ePay)

Unified entrypoint for both one-time top-up and card-save:

#### Initiate Payment / Card Save

Endpoint: POST /payments/initiate

Request (one-time top-up):
```json
{
  "amount": 5,
  "description": "Top-up",
  "save_card": false,
  "language": "rus"
}
```

Request (save card):
```json
{
  "save_card": true,
  "language": "rus"
}
```

Notes:
- back_link and failure_back_link are no longer passed by client.
- Redirect links are taken from backend env:
  - EPAY_DEFAULT_BACK_LINK
  - EPAY_DEFAULT_FAILURE_BACK_LINK

Response (200):
```json
{
  "success": true,
  "message": "Payment session created",
  "data": {
    "invoice_id": "760532487",
    "payment_id": "67677ca6-e3c2-48b8-bcd6-abb25bf41687",
    "payment_type": "one_time",
    "checkout_url": "https://your-domain/api/v1/payments/checkout/<payment_id>?token=<token>",
    "amount": 5,
    "currency": "KZT"
  }
}
```

Frontend must open only checkout_url (WebView/browser).

#### Get Payment Status

Endpoint: GET /payments/status/{payment_id}?sync=true

- sync=true: backend attempts live reconciliation with ePay before returning.
- sync=false: returns local DB status only.

#### Recurrent Payment (saved card)

Endpoint: POST /payments/recurrent

Request:
```json
{
  "card_id": "<saved_card_id>",
  "amount": 5,
  "description": "Subscription",
  "currency": "KZT"
}
```

#### Saved cards

- GET /payments/saved-cards
- DELETE /payments/saved-cards/{card_id}

#### Webhook

Endpoint: POST /payments/webhook

Webhook verifies status with ePay and updates payment state. For successful one-time/recurrent payments, user balance is increased once (idempotent).

### 1. Authentication APIs

#### 1.1 Send OTP via WhatsApp

**Endpoint:** `POST /otp/whatsapp`

**Request:**
```json
{
  "phone_number": "+1234567890"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "OTP sent successfully",
  "meta": {
      "expires_in": 300
  }
}
```

#### 1.2 Verify OTP

**Endpoint:** `POST /otp/verify`

**Request:**
```json
{
  "phone_number": "+1234567890",
  "otp_code": "123456"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Authentication successful",
  "data": {
    "access_token": "jwt_token_here",
    "token_type": "bearer",
    "expires_in": 3600,
    "user_id": "user_id_here",
    "firebase_custom_token": "firebase_token_here_if_applicable"
  }
}
```

#### 1.3 Login by Email

**Endpoint:** `POST /api/login/by-email`

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Success",
  "data": {
    "token": "jwt_token_here"
  }
}
```


#### 1.4 Confirm Login

**Endpoint:** `POST /api/login/{endpoint}/confirm`

**Request:**
```json
{
  "token": "confirmation_token",
  "ticketCode": "123456"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Success"
}
```

---

### 2. Subscriber APIs

#### 2.1 Get Subscriber Info

**Endpoint:** `GET /subscriber`

**Headers:**
```
Authorization: Bearer <token>
```

**Response (200):**
*Note: This endpoint returns a direct dictionary object, not wrapped in `data`.*
```json
{
  "balance": 50.00,
  "imsi": [
    {
      "imsi": "250991234567890",
      "iccid": "8922222220000000001",
      "balance": 25.00,
      "country": "Germany",
      "iso": "DE",
      "brand": "Imsimarket",
      "rate": 0.05,
      "qr": "LPA:1$smdp.example.com$ACTIVATION_CODE",
      "smdpServer": "smdp.example.com",
      "activationCode": "ACTIVATION_CODE"
    }
  ]
}
```

---

### 3. User Profile APIs

#### 3.1 Get Current User

**Endpoint:** `GET /user/profile`

**Response (200):**
```json
{
  "success": true,
  "message": "Success",
  "data": {
    "id": "user_001",
    "email": "test@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "phone_number": "+1234567890",
    "avatar_url": null,
    "balance": 50.00,
    "currency": "USD",
    "created_at": "2024-10-28T10:00:00Z",
    "updated_at": "2024-11-27T10:00:00Z",
    "is_email_verified": true,
    "is_phone_verified": true,
    "preferred_language": "en",
    "preferred_currency": "USD",
    "favorite_countries": ["US", "GB", "DE"],
    "apps_enabled": ["vink", "vink-sim"]
  }
}
```

#### 3.2 Update User Profile

**Endpoint:** `PUT /user/profile`

**Request:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "preferred_language": "en",
  "preferred_currency": "USD"
}
```

**Response (200):** Same as Get Current User (Wrapped in DataResponse)

#### 3.3 Top Up Balance

**Endpoint:** `POST /user/balance/top-up`

**Request:**
```json
{
  "amount": 25.00,
  "imsi": "optional_imsi_to_top_up_directly"
}
```

**Response (200):** Standard Success Response

#### 3.4 Get Balance History

**Endpoint:** `GET /user/balance/history`

**Response (200):**
```json
{
  "success": true,
  "message": "Success",
  "data": {
    "transactions": [
      {
        "id": "txn_001",
        "type": "top_up",
        "amount": 25.00,
        "currency": "USD",
        "date": "2024-11-20T10:00:00Z",
        "status": "completed",
        "description": "Account top-up"
      }
    ],
    "total_top_up": 60.00,
    "total_spent": 10.00
  }
}
```

#### 3.5 Delete User

**Endpoint:** `DELETE /user/profile`

**Response (200):** Standard Success Response

#### 3.6 Change Password

**Endpoint:** `POST /user/change-password`

**Request:**
```json
{
  "old_password": "oldpass123",
  "new_password": "newpass456"
}
```

**Response (200):** Standard Success Response

#### 3.7 Verify Email / Phone

**Endpoint:** `POST /user/verify-email` or `POST /user/verify-phone`

**Request:**
```json
{
  "verification_code": "123456"
}
```

**Response (200):** Standard Success Response

#### 3.8 Upload Avatar

**Endpoint:** `POST /user/avatar`

**Request:**
```json
{
  "avatar_path": "/path/to/avatar.jpg"
}
```

**Response (200):** Same as Get Current User (Wrapped in DataResponse)

---

### 4. eSIM Management APIs

#### 4.1 Get All eSIMs

**Endpoint:** `GET /esims`

**Response (200):**
```json
{
  "success": true,
  "message": "Success",
  "data": [
    {
      "id": "esim_001",
      "name": "Germany Travel eSIM",
      "provider": "Imsimarket",
      "country": "Germany",
      "iso": "DE",
      "is_active": true,
      "data_used": 1.5,
      "data_limit": 5.0,
      "activation_date": "2024-11-24T10:00:00Z",
      "status": "active",
      "price": 0.0,
      "currency": "USD",
      "rate": 0.05,
      "imsi": "26001...",
      "iccid": "89...",
      "msisdn": "161..."
    }
  ]
}
```

#### 4.2 Get eSIM by ID

**Endpoint:** `GET /esims/{id}`

**Response (200):** Single eSIM object wrapped in DataResponse.

#### 4.3 Activate eSIM

**Endpoint:** `POST /esims/{id}/activate`

**Request:**
```json
{
  "activation_code": "ACTIVATION_CODE"
}
```

**Response (200):** eSIM object wrapped in DataResponse.

#### 4.4 Deactivate eSIM

**Endpoint:** `POST /esims/{id}/deactivate`

**Response (200):** Standard Success Response

#### 4.5 Update eSIM Settings

**Endpoint:** `PUT /esims/{id}/settings`

**Request:**
```json
{
  "name": "My Germany eSIM",
  "data_alert_threshold": 80
}
```

**Response (200):** eSIM object wrapped in DataResponse.

#### 4.6 Get eSIM Usage Data

**Endpoint:** `GET /esims/{id}/usage`

**Response (200):**
```json
{
  "success": true,
  "message": "Success",
  "data": {
    "esim_id": "esim_001",
    "period": {
      "start": "2026-01-22",
      "end": "2026-01-22"
    },
    "usage": {
      "data_used_mb": 1536.0,
      "data_limit_mb": 5120.0,
      "data_remaining_mb": 3584.0,
      "percentage_used": 30.0
    },
    "daily_breakdown": []
  }
}
```

#### 4.7 Get Tariffs

**Endpoint:** `GET /tariffs`

**Response (200):**
```json
{
  "success": true,
  "message": "Success",
  "data": [
    {
      "plmn": "26201",
      "network_name": "Telekom",
      "country_name": "Germany",
      "data_rate": 0.05
    }
  ]
}
```

#### 4.8 Purchase eSIM

**Endpoint:** `POST /esims/purchase`

**Request:** (Empty Body)

**Response (200):** New eSIM object wrapped in DataResponse.

#### 4.9 Unassign IMSI (Admin)

**Endpoint:** `POST /esims/unassign`

**Request:**
```json
{
  "imsi": "26001..."
}
```

**Response (200):** Standard Success Response

---

## Error Responses

All endpoints may return these error responses:

### 400 Bad Request / 401 Unauthorized / 404 Not Found / 500 Server Error

```json
{
  "error": {
      "message": "Description of the error",
      "code": 400
  }
}
```

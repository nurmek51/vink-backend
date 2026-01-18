# FlexTravelSIM API Integration Documentation

## Overview

This document provides comprehensive API integration details for the FlexTravelSIM application.
Use this as a reference when integrating the real backend API.

**Current Status:** Backend returning 503 - Using Mock Data
**Mock Data Location:** `lib/core/mock/mock_data.dart`

---

## API Configuration

### Base URLs

| Environment | URL                                    |
|-------------|----------------------------------------|
| Development | `https://dev-api.flextravelsim.com`    |
| Production  | From `Environment.apiUrl` (.env file)  |

### Authentication

All authenticated endpoints require:
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
Accept: application/json
```

---

## API Endpoints

### 1. Authentication APIs

#### 1.1 Send OTP via WhatsApp

**Endpoint:** `POST /otp/whatsapp`

**Request:**
```json
{
  "phone": "+1234567890"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "OTP sent successfully",
  "expires_in": 300
}
```

**Mock Implementation:** `lib/core/mock/mock_data.dart` → `MockAuthData.otpSendResponse`

**Data Source:** `OtpAuthDataSourceImpl.sendOtpSms()`

---

#### 1.2 Verify OTP

**Endpoint:** `POST /otp/verify`

**Request:**
```json
{
  "phone": "+1234567890",
  "code": "123456"
}
```

**Response (200):**
```json
{
  "token": "jwt_token_here",
  "user_id": "user_001",
  "firebase_custom_token": "firebase_token_here"
}
```

**Mock Implementation:** `MockAuthData.otpVerifyResponse`

**Data Source:** `OtpAuthDataSourceImpl.verifyOtp()`

---

#### 1.3 Login by Email

**Endpoint:** `POST /api/login/by-email`

**Headers:**
```
Authorization: Basic base64(LOGIN_PASSWORD)
```

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response (200):**
```json
{
  "token": "jwt_token_here"
}
```

**Mock Implementation:** Returns mock token for phone credentials

**Data Source:** `AuthRemoteDataSourceImpl.login()`

---

#### 1.4 Confirm Login

**Endpoint:** `POST /api/login/{endpoint}/confirm`

**Request:**
```json
{
  "token": "confirmation_token",
  "ticketCode": "123456"
}
```

**Response (200):** Empty body (success)

**Mock Implementation:** Always returns success after 500ms delay

**Data Source:** `ConfirmRemoteDataSourceImpl.confirm()`

---

### 2. Subscriber APIs

#### 2.1 Get Subscriber Info

**Endpoint:** `GET /subscriber`

**Headers:**
```
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "balance": 50.00,
  "imsi": [
    {
      "imsi": "250991234567890",
      "balance": 25.00,
      "country": "Germany",
      "iso": "DE",
      "brand": "FlexSIM",
      "rate": 0.05,
      "qr": "LPA:1$smdp.example.com$ACTIVATION_CODE",
      "smdpServer": "smdp.example.com",
      "activationCode": "ACTIVATION_CODE"
    }
  ]
}
```

**Mock Implementation:** `MockSubscriberData.subscriberJson`

**Data Source:** `SubscriberRemoteDataSourceImpl.getSubscriberInfo()`

---

### 3. User Profile APIs

#### 3.1 Get Current User

**Endpoint:** `GET /user/profile`

**Response (200):**
```json
{
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
    "favorite_countries": ["US", "GB", "DE"]
  }
}
```

**Mock Implementation:** `MockUserData.currentUserJson`

**Data Source:** `UserRemoteDataSourceImpl.getCurrentUser()`

---

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

**Response (200):** Same as Get Current User

**Mock Implementation:** Returns updated user with merged fields

**Data Source:** `UserRemoteDataSourceImpl.updateUserProfile()`

---

#### 3.3 Top Up Balance

**Endpoint:** `POST /user/balance/top-up`

**Request:**
```json
{
  "amount": 25.00
}
```

**Response (200):** Empty body (success)

**Mock Implementation:** Returns success

**Data Source:** `UserRemoteDataSourceImpl.updateBalance()`

---

#### 3.4 Get Balance History

**Endpoint:** `GET /user/balance/history`

**Response (200):**
```json
{
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

**Mock Implementation:** `MockUserData.balanceHistory`

**Data Source:** `UserRemoteDataSourceImpl.getBalanceHistory()`

---

#### 3.5 Delete User

**Endpoint:** `DELETE /user/profile`

**Response (200):** Empty body (success)

**Data Source:** `UserRemoteDataSourceImpl.deleteUser()`

---

#### 3.6 Change Password

**Endpoint:** `POST /user/change-password`

**Request:**
```json
{
  "old_password": "oldpass123",
  "new_password": "newpass456"
}
```

**Response (200):** Empty body (success)

**Data Source:** `UserRemoteDataSourceImpl.changePassword()`

---

#### 3.7 Verify Email

**Endpoint:** `POST /user/verify-email`

**Request:**
```json
{
  "verification_code": "123456"
}
```

**Response (200):** Empty body (success)

**Data Source:** `UserRemoteDataSourceImpl.verifyEmail()`

---

#### 3.8 Verify Phone

**Endpoint:** `POST /user/verify-phone`

**Request:**
```json
{
  "verification_code": "123456"
}
```

**Response (200):** Empty body (success)

**Data Source:** `UserRemoteDataSourceImpl.verifyPhone()`

---

#### 3.9 Upload Avatar

**Endpoint:** `POST /user/avatar`

**Request:**
```json
{
  "avatar_path": "/path/to/avatar.jpg"
}
```

**Response (200):** Same as Get Current User

**Data Source:** `UserRemoteDataSourceImpl.uploadAvatar()`

---

### 4. eSIM Management APIs

#### 4.1 Get All eSIMs

**Endpoint:** `GET /esims`

**Response (200):**
```json
{
  "data": [
    {
      "id": "esim_001",
      "name": "Germany Travel eSIM",
      "provider": "FlexSIM",
      "country": "Germany",
      "region": "Europe",
      "is_active": true,
      "data_used": 1.5,
      "data_limit": 5.0,
      "activation_date": "2024-11-24T10:00:00Z",
      "expiration_date": "2024-12-24T10:00:00Z",
      "status": "active",
      "qr_code": "LPA:1$smdp.example.com$CODE",
      "activation_code": "ACTIVATION_CODE",
      "price": 15.00,
      "currency": "USD",
      "supported_networks": ["Vodafone", "T-Mobile", "O2"]
    }
  ]
}
```

**Mock Implementation:** `MockEsimData.esimListJson`

**Data Source:** `EsimRemoteDataSourceImpl.getEsims()`

---

#### 4.2 Get eSIM by ID

**Endpoint:** `GET /esims/{id}`

**Response (200):**
```json
{
  "data": {
    "id": "esim_001",
    ...
  }
}
```

**Mock Implementation:** `MockEsimData.getEsimById(id)`

**Data Source:** `EsimRemoteDataSourceImpl.getEsimById()`

---

#### 4.3 Activate eSIM

**Endpoint:** `POST /esims/{id}/activate`

**Request:**
```json
{
  "activation_code": "ACTIVATION_CODE"
}
```

**Response (200):** eSIM object with status="active"

**Data Source:** `EsimRemoteDataSourceImpl.activateEsim()`

---

#### 4.4 Purchase eSIM

**Endpoint:** `POST /esims/purchase`

**Request:**
```json
{
  "tariff_id": "tariff_001",
  "payment_data": {
    "payment_method_id": "pm_001",
    "amount": 15.00,
    "currency": "USD"
  }
}
```

**Response (200):** New eSIM object

**Data Source:** `EsimRemoteDataSourceImpl.purchaseEsim()`

---

#### 4.5 Deactivate eSIM

**Endpoint:** `POST /esims/{id}/deactivate`

**Response (200):** Empty body (success)

**Data Source:** `EsimRemoteDataSourceImpl.deactivateEsim()`

---

#### 4.6 Update eSIM Settings

**Endpoint:** `PUT /esims/{id}/settings`

**Request:**
```json
{
  "name": "My Germany eSIM",
  "data_alert_threshold": 80
}
```

**Response (200):** Updated eSIM object

**Data Source:** `EsimRemoteDataSourceImpl.updateEsimSettings()`

---

#### 4.7 Get eSIM Usage Data

**Endpoint:** `GET /esims/{id}/usage`

**Response (200):**
```json
{
  "data": {
    "esim_id": "esim_001",
    "period": {
      "start": "2024-11-20T00:00:00Z",
      "end": "2024-11-27T00:00:00Z"
    },
    "usage": {
      "data_used_mb": 1536.0,
      "data_limit_mb": 5120.0,
      "data_remaining_mb": 3584.0,
      "percentage_used": 30.0
    },
    "daily_breakdown": [
      {"date": "2024-11-21", "data_mb": 200.0}
    ]
  }
}
```

**Mock Implementation:** `MockEsimData.getUsageData(id)`

**Data Source:** `EsimRemoteDataSourceImpl.getEsimUsageData()`

---

### 5. Tariffs API (External)

#### 5.1 Get Network Operators

**Endpoint:** `GET https://imsimarket.com/js/data/alternative.rates.json`

**Response (200):**
```json
[
  {
    "PLMN": "26201",
    "NetworkName": "Telekom",
    "CountryName": "Germany",
    "DataRate": 0.05
  }
]
```

**Mock Implementation:** `MockTariffsData.networkOperators`

**Data Source:** `TariffsRemoteDataSourceImpl.getNetworkOperators()`

---

## Error Responses

All endpoints may return these error responses:

### 400 Bad Request
```json
{
  "message": "Validation error description"
}
```

### 401 Unauthorized
```json
{
  "message": "Invalid or expired token"
}
```

### 404 Not Found
```json
{
  "message": "Resource not found"
}
```

### 500+ Server Error
```json
{
  "message": "Internal server error"
}
```

---

## Mock Mode Toggle

To switch between mock and real API:

1. **In `MockConfig` class:**
```dart
static bool useMockData = true;  // Set to false for real API
```

2. **Or check at runtime:**
```dart
if (MockConfig.useMockData) {
  // Return mock data
} else {
  // Make real API call
}
```

---

## Files Modified for Mock Integration

| File | Purpose | Changes |
|------|---------|---------|
| `lib/core/mock/mock_data.dart` | Central mock data | NEW FILE |
| `lib/core/network/travel_sim_api_service.dart` | Main API service | Added mock fallback |
| `lib/features/auth/data/data_sources/otp_auth_data_source.dart` | OTP handling | Added mock fallback |
| `lib/features/subscriber/data/data_sources/subscriber_remote_data_source.dart` | Subscriber info | Added mock fallback |
| `lib/features/esim_management/data/data_sources/esim_remote_data_source.dart` | eSIM operations | Added mock fallback |
| `lib/features/user_account/data/data_sources/user_remote_data_source.dart` | User profile | Added mock fallback |

---

## Testing Mock Data

### Default Test Credentials
- **Phone:** Any phone number works
- **OTP Code:** `123456` (MockConfig.defaultOtpCode)
- **User:** Pre-configured John Doe user

### Test eSIMs
- **esim_001:** Active Germany eSIM (1.5GB/5GB used)
- **esim_002:** Pending UK eSIM
- **esim_003:** Pending Japan eSIM

### Test Balance
- **Starting balance:** $50.00
- **IMSI cards:** 3 (Germany, UK, Japan)

---

## Integration Checklist

When backend is ready, update these files:

- [ ] Remove `MockConfig.useMockData = true` or set to `false`
- [ ] Update `.env` with production API URL
- [ ] Test all API endpoints
- [ ] Remove mock fallback code (optional)
- [ ] Update error handling if API response format changes

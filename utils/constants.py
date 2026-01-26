"""
Constants for the Girl Scout Cookie Tracker application.
Centralizes magic strings to prevent typos and ensure consistency.
"""

# =====================================================
# Order Types
# =====================================================
ORDER_TYPE_DIGITAL = "Digital"
ORDER_TYPE_PAPER = "Paper"
ORDER_TYPE_BOOTH = "Booth"

# =====================================================
# Order Sources
# =====================================================
ORDER_SOURCE_DOC_IMPORT = "Digital Cookie Import"
ORDER_SOURCE_MANUAL = None  # Manual entry through the app

# =====================================================
# Order Status
# =====================================================
ORDER_STATUS_NEW = "NEW"
ORDER_STATUS_IMPORTED = "IMPORTED"
ORDER_STATUS_CANCELLED = "CANCELLED"
ORDER_STATUS_COMPLETED = "COMPLETED"

# =====================================================
# Verification Status
# =====================================================
VERIFICATION_STATUS_DRAFT = "DRAFT"
VERIFICATION_STATUS_VERIFIED = "VERIFIED"

# =====================================================
# Inventory Event Types
# =====================================================
EVENT_TYPE_PICKUP = "PICKUP"
EVENT_TYPE_BOOTH = "BOOTH"
EVENT_TYPE_RETURN = "RETURN"

# =====================================================
# Payment Methods
# =====================================================
PAYMENT_METHOD_CASH = "CASH"
PAYMENT_METHOD_CHECK = "CHECK"
PAYMENT_METHOD_SQUARE = "SQUARE"
PAYMENT_METHOD_EBUDDE = "EBUDDE"

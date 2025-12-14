"""Standardized error messages for consistent user experience."""

from __future__ import annotations

from typing import Any


def get_error_message(error_type: str, **kwargs: Any) -> str:
    """
    Get formatted error message with variables.
    
    Args:
        error_type: Type of error (key from ERROR_MESSAGES)
        **kwargs: Variables to format into the message
        
    Returns:
        Formatted error message string
    """
    message_template = ERROR_MESSAGES.get(error_type, "❌ An error occurred. Please try again later.")
    
    try:
        return message_template.format(**kwargs)
    except KeyError as e:
        # If a required variable is missing, return a generic message
        return f"❌ {error_type.replace('_', ' ').title()} error occurred."


ERROR_MESSAGES = {
    "insufficient_balance": (
        "❌ **Insufficient Balance**\n\n"
        "You don't have enough balance for this purchase.\n"
        "• Current balance: {current_balance}\n"
        "• Required: {required_amount}\n"
        "• Use `/deposit` to add funds to your wallet"
    ),
    
    "invalid_product": (
        "❌ **Product Not Found**\n\n"
        "The product you're looking for doesn't exist or is no longer available.\n"
        "• Use `/buy` to browse current products\n"
        "• Contact support with `/ticket support` if you need help"
    ),
    
    "out_of_stock": (
        "🔴 **Out of Stock**\n\n"
        "This product is currently out of stock.\n"
        "• Check back later for restocks\n"
        "• Browse similar products with `/buy`\n"
        "• Contact sales for ETA: `/ticket sales`"
    ),
    
    "insufficient_stock": (
        "🔴 **Insufficient Stock**\n\n"
        "Not enough stock available for this purchase.\n"
        "• Available: {available_quantity}\n"
        "• Requested: {requested_quantity}\n"
        "• Contact sales for restock ETA: `/ticket sales`"
    ),
    
    "invalid_promo_code": (
        "❌ **Invalid Promo Code**\n\n"
        "The promo code `{code}` is invalid or expired.\n"
        "• Check the code spelling\n"
        "• Promo codes are case-insensitive\n"
        "• Use `/codeinfo {code}` to check code details (admin only)"
    ),
    
    "promo_code_expired": (
        "⏰ **Promo Code Expired**\n\n"
        "The promo code `{code}` has expired.\n"
        "• Expired on: {expired_date}\n"
        "• Check for new promo codes in announcements"
    ),
    
    "promo_code_max_uses": (
        "🚫 **Promo Code Limit Reached**\n\n"
        "The promo code `{code}` has reached its maximum usage limit.\n"
        "• Maximum uses: {max_uses}\n"
        "• Current uses: {current_uses}"
    ),
    
    "promo_code_user_limit": (
        "🚫 **Usage Limit Reached**\n\n"
        "You've already used the promo code `{code}` the maximum number of times.\n"
        "• Maximum uses per user: {max_per_user}\n"
        "• Your uses: {user_uses}"
    ),
    
    "promo_code_min_purchase": (
        "💰 **Minimum Purchase Required**\n\n"
        "This promo code requires a minimum purchase amount.\n"
        "• Your order total: {order_total}\n"
        "• Minimum required: {min_purchase}\n"
        "• Add more items to your cart to use this code"
    ),
    
    "promo_code_not_applicable": (
        "❌ **Promo Code Not Applicable**\n\n"
        "The promo code `{code}` cannot be applied to this product.\n"
        "• This code may be restricted to specific categories or products\n"
        "• Try a different promo code or proceed without one"
    ),
    
    "gift_code_invalid": (
        "❌ **Invalid Gift Code**\n\n"
        "The gift code `{code}` is invalid or has already been claimed.\n"
        "• Check the code spelling\n"
        "• Gift codes can only be used once\n"
        "• Contact support if you believe this is an error"
    ),
    
    "gift_code_expired": (
        "⏰ **Gift Code Expired**\n\n"
        "The gift code `{code}` has expired.\n"
        "• Expired on: {expired_date}\n"
        "• Contact the sender for a new gift code"
    ),
    
    "gift_already_claimed": (
        "✅ **Gift Already Claimed**\n\n"
        "This gift has already been claimed.\n"
        "• Claimed on: {claimed_date}\n"
        "• Check `/mygifts` to see all your gifts"
    ),
    
    "invalid_order": (
        "❌ **Invalid Order**\n\n"
        "The order ID `{order_id}` doesn't exist or you don't have permission to view it.\n"
        "• Use `/orders` to view your order history\n"
        "• Contact support if you need help: `/ticket support`"
    ),
    
    "order_not_found": (
        "❌ **Order Not Found**\n\n"
        "Order #{order_id} could not be found.\n"
        "• Verify the order ID is correct\n"
        "• Use `/orders` to view your order history"
    ),
    
    "invalid_amount": (
        "❌ **Invalid Amount**\n\n"
        "The amount you entered is invalid.\n"
        "• Amount must be a positive number\n"
        "• Maximum amount: {max_amount}\n"
        "• Minimum amount: {min_amount}"
    ),
    
    "invalid_user": (
        "❌ **User Not Found**\n\n"
        "The user you specified could not be found.\n"
        "• Make sure the user is in the server\n"
        "• Try mentioning the user: @username"
    ),
    
    "permission_denied": (
        "🚫 **Permission Denied**\n\n"
        "You don't have permission to use this command.\n"
        "• This command requires admin privileges\n"
        "• Contact an administrator if you need access"
    ),
    
    "rate_limit_exceeded": (
        "⏱️ **Rate Limit Exceeded**\n\n"
        "You're using this command too frequently.\n"
        "• Please wait {retry_after} before trying again\n"
        "• Remaining uses: {remaining_uses}"
    ),
    
    "database_error": (
        "⚠️ **Database Error**\n\n"
        "An error occurred while accessing the database.\n"
        "• Please try again in a few moments\n"
        "• If the problem persists, contact support: `/ticket support`"
    ),
    
    "operation_failed": (
        "❌ **Operation Failed**\n\n"
        "The operation could not be completed.\n"
        "• {reason}\n"
        "• Please try again or contact support: `/ticket support`"
    ),
    
    "invalid_input": (
        "❌ **Invalid Input**\n\n"
        "The information you provided is invalid.\n"
        "• {field}: {error}\n"
        "• Please check your input and try again"
    ),
    
    "dm_disabled": (
        "📬 **Direct Messages Disabled**\n\n"
        "I couldn't send you a direct message.\n"
        "• Please enable DMs from server members\n"
        "• Server Settings → Privacy → Allow direct messages from server members"
    ),
}


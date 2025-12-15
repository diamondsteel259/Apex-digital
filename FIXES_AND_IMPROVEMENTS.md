# Fixes and Improvements Plan

## Issues Identified

### 1. Supplier Info Privacy ✅
- **Problem**: Supplier information should not be visible to users
- **Solution**: 
  - Hide supplier fields from product displays
  - Add admin-only order view with supplier links
  - Store supplier order URLs for admin use only

### 2. Channel/Category Organization ⚠️
- **Problem**: Channels not properly organized, some should be under sub-categories
- **Solution**: 
  - Reorganize blueprint with proper hierarchy
  - Fix channel positions and categories
  - Ensure staff channels are properly categorized

### 3. Duplicate Roles/Categories ⚠️
- **Problem**: Old duplicate roles and categories not deleted
- **Solution**: 
  - Add cleanup step to delete roles/categories not in blueprint
  - Improve duplicate detection

### 4. Product Import/Display ⚠️
- **Problem**: Too many products (4999 imported), hard to find
- **Solution**: 
  - Add pagination to product listings
  - Add filtering by quantity/amount (e.g., "1000 views")
  - Group similar products together
  - Add search functionality

### 5. New Features to Add
- **Tip User**: Wallet to wallet transfers
- **Airdrop**: One user sends funds, multiple users can claim
- **New channels/roles**: For tip/airdrop features

## Implementation Priority

1. ✅ Supplier privacy (critical)
2. ⚠️ Channel/category organization
3. ⚠️ Duplicate cleanup
4. ⚠️ Product pagination/filtering
5. ⚠️ Tip/Airdrop features


# Enhancement Changelog - Accounting (記帳系統)

## Overview
This is a Streamlit-based accounting system designed for parsing semi-structured Chinese accounting text. It features a calendar-based input interface, person management, and expense reporting.

## Date: 2026-02-04

## Summary of Changes
- Added database connection context manager to prevent resource leaks
- Improved input validation across all database operations
- Enhanced error handling with meaningful return values
- Added transaction rollback support for data integrity
- Improved documentation with Chinese and English docstrings
- Fixed date tracking to include memos (not just expenses)

## Detailed Changes

### Logic Improvements

#### database.py - Connection Management
- **Before**: Manual `conn.close()` calls scattered throughout, potential for resource leaks on exceptions
- **After**: Added `db_connection()` context manager with automatic rollback on error and guaranteed connection closure
- **Impact**: Prevents database connection leaks and ensures data integrity on errors

#### database.py - Input Validation for add_person()
- **Before**: No validation, could add empty names or duplicate persons silently
- **After**: Validates non-empty names, checks for duplicates, raises `ValueError` with clear messages
- **Impact**: Prevents data corruption and provides better user feedback

#### database.py - Input Validation for add_expense()
- **Before**: No validation, could add negative amounts or empty required fields
- **After**: Validates all required fields, ensures amount >= 0 and quantity > 0
- **Impact**: Maintains data integrity and prevents invalid financial records

#### database.py - update_category_price()
- **Before**: No validation, could set negative prices
- **After**: Validates price >= 0, returns boolean indicating success
- **Impact**: Prevents invalid pricing data

#### database.py - get_dates_with_data()
- **Before**: Only checked expenses table for dates with data
- **After**: Now uses UNION query to check both expenses AND memos tables
- **Impact**: Calendar view now correctly shows dates that have memos but no expenses

#### database.py - delete_day_data()
- **Before**: Only deleted expenses and memos
- **After**: Now also deletes pending_review items for the specified date
- **Impact**: Complete cleanup of all data for a given date

### Code Quality Improvements

1. **Consistent context manager usage**: All database operations now use `with db_connection() as conn:` pattern
2. **Return value consistency**: Functions that modify data now return boolean success indicators
3. **Type hints preserved**: All existing type hints maintained and enhanced
4. **Documentation**: Added comprehensive docstrings with Chinese context
5. **Input sanitization**: Added `.strip()` calls on text inputs to prevent whitespace issues
6. **PRAGMA foreign_keys**: Enabled foreign key constraints in database connection

### UI/UX Improvements
- No direct UI changes in this update (database layer improvements will provide better error messages to UI)

## Technical Notes
- All changes are backward compatible
- The new `db_connection()` context manager can be used alongside the original `get_connection()` for gradual migration
- Added `timeout=30` to database connections to prevent hanging on locked databases

## Future Recommendations
1. Consider adding database migrations system for schema changes
2. Add data export/import functionality
3. Consider adding expense categories management UI
4. Add unit tests for database operations
5. Consider adding a backup/restore feature

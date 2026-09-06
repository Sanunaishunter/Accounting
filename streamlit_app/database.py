"""資料庫模組 - SQLite 操作"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "accounting.db"

DEFAULT_CATEGORIES = {
    "早餐": 70,
    "中餐": 150,
    "晚餐": 150,
    "牛奶": 40,
    "點心": 0,
    "飲料": 0,
    "文具": 0,
}

DEFAULT_PERSONS = ["阿鵰", "泰禎", "紫緹", "牧恩", "咏恩", "傑森", "崴崴"]


def get_connection() -> sqlite3.Connection:
    """取得資料庫連線"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    # 啟用外鍵約束
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


from contextlib import contextmanager

@contextmanager
def db_connection():
    """資料庫連線的 context manager，確保連線正確關閉

    Usage:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
            conn.commit()
    """
    conn = get_connection()
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_db() -> None:
    """初始化資料庫結構"""
    conn = get_connection()
    cursor = conn.cursor()

    # persons 人名詞庫
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS persons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            aliases TEXT DEFAULT ''
        )
    """)

    # category_prices 類別單價
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS category_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT UNIQUE NOT NULL,
            default_price INTEGER NOT NULL DEFAULT 0
        )
    """)

    # expenses 支出記錄
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            person TEXT NOT NULL,
            amount INTEGER NOT NULL,
            quantity REAL NOT NULL DEFAULT 1,
            note TEXT DEFAULT ''
        )
    """)

    # pending_review 待審核
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_review (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_text TEXT NOT NULL,
            source_line TEXT NOT NULL,
            date TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # memos 備忘
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            content TEXT NOT NULL
        )
    """)

    # memos.person 欄位 migration（舊 DB 若已存在則忽略）
    try:
        cursor.execute("ALTER TABLE memos ADD COLUMN person TEXT DEFAULT NULL")
    except Exception:
        pass

    # memo_person_mapping 關鍵字→人名對應表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memo_person_mapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE NOT NULL,
            person TEXT NOT NULL
        )
    """)

    # 預設對應
    default_mappings = [("台北媽媽", "牧恩"), ("米媽媽", "傑森")]
    for keyword, person in default_mappings:
        cursor.execute(
            "INSERT OR IGNORE INTO memo_person_mapping (keyword, person) VALUES (?, ?)",
            (keyword, person),
        )

    # person_proxy 關鍵字→代理人對應表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS person_proxy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE NOT NULL,
            proxy_for TEXT NOT NULL,
            note TEXT DEFAULT ''
        )
    """)

    # 預設代理關係
    default_proxies = [
        ("台北媽媽", "牧恩", "牧恩的媽媽"),
        ("米媽媽", "傑森", "傑森的媽媽"),
    ]
    for keyword, proxy_for, note in default_proxies:
        cursor.execute(
            "INSERT OR IGNORE INTO person_proxy (keyword, proxy_for, note) VALUES (?, ?, ?)",
            (keyword, proxy_for, note),
        )

    # 建立索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_person ON expenses(person)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)")

    # 初始化預設類別單價
    for category, price in DEFAULT_CATEGORIES.items():
        cursor.execute(
            "INSERT OR IGNORE INTO category_prices (category, default_price) VALUES (?, ?)",
            (category, price),
        )

    # 初始化預設人員
    for person in DEFAULT_PERSONS:
        cursor.execute(
            "INSERT OR IGNORE INTO persons (name, aliases) VALUES (?, '')",
            (person,),
        )

    conn.commit()
    conn.close()


# ========== Persons 操作 ==========


def get_all_persons() -> list[dict]:
    """取得所有人員（按名稱排序）"""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, aliases FROM persons ORDER BY name")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def add_person(name: str, aliases: str = "") -> int:
    """新增人員，回傳 id

    Args:
        name: 人員名稱（必須唯一）
        aliases: 別名（逗號分隔）

    Returns:
        新增人員的 ID

    Raises:
        ValueError: 如果名稱為空或已存在
    """
    if not name or not name.strip():
        raise ValueError("人員名稱不可為空")

    name = name.strip()
    with db_connection() as conn:
        cursor = conn.cursor()
        # 檢查是否已存在
        cursor.execute("SELECT id FROM persons WHERE name = ?", (name,))
        if cursor.fetchone():
            raise ValueError(f"人員「{name}」已存在")

        cursor.execute(
            "INSERT INTO persons (name, aliases) VALUES (?, ?)", (name, aliases.strip())
        )
        conn.commit()
        return cursor.lastrowid


def update_person_aliases(person_id: int, aliases: str) -> bool:
    """更新人員別名

    Returns:
        True 如果更新成功，False 如果人員不存在
    """
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE persons SET aliases = ? WHERE id = ?", (aliases.strip(), person_id))
        conn.commit()
        return cursor.rowcount > 0


def add_alias_to_person(person_id: int, new_alias: str) -> bool:
    """為人員新增別名

    Args:
        person_id: 人員 ID
        new_alias: 要新增的別名

    Returns:
        True 如果新增成功，False 如果人員不存在或別名已存在
    """
    if not new_alias or not new_alias.strip():
        return False

    new_alias = new_alias.strip()

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT aliases FROM persons WHERE id = ?", (person_id,))
        row = cursor.fetchone()

        if not row:
            return False

        existing = row["aliases"]
        if existing:
            aliases_list = [a.strip() for a in existing.split(",") if a.strip()]
            if new_alias in aliases_list:
                return False  # 別名已存在
            aliases_list.append(new_alias)
            new_aliases = ",".join(aliases_list)
        else:
            new_aliases = new_alias

        cursor.execute("UPDATE persons SET aliases = ? WHERE id = ?", (new_aliases, person_id))
        conn.commit()
        return True


def delete_person(person_id: int) -> bool:
    """刪除人員

    Returns:
        True 如果刪除成功，False 如果人員不存在
    """
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM persons WHERE id = ?", (person_id,))
        conn.commit()
        return cursor.rowcount > 0


# ========== Category Prices 操作 ==========


def get_all_category_prices() -> dict[str, int]:
    """取得所有類別單價（按類別名稱排序）"""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT category, default_price FROM category_prices ORDER BY category")
        rows = cursor.fetchall()
        return {row["category"]: row["default_price"] for row in rows}


def update_category_price(category: str, price: int) -> bool:
    """更新類別單價

    Args:
        category: 類別名稱
        price: 新單價（必須 >= 0）

    Returns:
        True 如果更新成功，False 如果類別不存在

    Raises:
        ValueError: 如果價格為負數
    """
    if price < 0:
        raise ValueError("單價不可為負數")

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE category_prices SET default_price = ? WHERE category = ?",
            (price, category),
        )
        conn.commit()
        return cursor.rowcount > 0


# ========== Expenses 操作 ==========


def add_expense(
    date: str,
    category: str,
    person: str,
    amount: int,
    quantity: float = 1,
    note: str = "",
) -> int:
    """新增支出記錄

    Args:
        date: 日期（格式：YYYY-MM-DD）
        category: 類別
        person: 人員名稱
        amount: 單價金額
        quantity: 數量（預設為 1）
        note: 備註

    Returns:
        新增記錄的 ID

    Raises:
        ValueError: 如果必要欄位為空或金額為負數
    """
    # 輸入驗證
    if not date or not category or not person:
        raise ValueError("日期、類別、人員皆為必填")
    if amount < 0:
        raise ValueError("金額不可為負數")
    if quantity <= 0:
        raise ValueError("數量必須大於 0")

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO expenses (date, category, person, amount, quantity, note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (date, category, person, amount, quantity, note),
        )
        conn.commit()
        return cursor.lastrowid


def expense_exists(date: str, category: str, person: str) -> bool:
    """檢查是否已有相同記錄（同日期、類別、人員）"""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM expenses WHERE date = ? AND category = ? AND person = ?",
            (date, category, person),
        )
        return cursor.fetchone() is not None


def get_expenses(
    year: Optional[int] = None,
    month: Optional[int] = None,
    persons: Optional[list[str]] = None,
) -> list[dict]:
    """查詢支出記錄

    Args:
        year: 篩選年份（可選）
        month: 篩選月份（可選，需與 year 搭配使用）
        persons: 篩選人員列表（可選）

    Returns:
        符合條件的支出記錄列表，按日期、類別、人員排序
    """
    with db_connection() as conn:
        cursor = conn.cursor()

        query = "SELECT * FROM expenses WHERE 1=1"
        params = []

        if year is not None:
            query += " AND substr(date, 1, 4) = ?"
            params.append(str(year))

        if month is not None:
            query += " AND CAST(substr(date, 6, 2) AS INTEGER) = ?"
            params.append(month)

        if persons:
            placeholders = ",".join("?" * len(persons))
            query += f" AND person IN ({placeholders})"
            params.extend(persons)

        query += " ORDER BY date, category, person"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def delete_expense(expense_id: int) -> bool:
    """刪除支出記錄

    Returns:
        True 如果刪除成功，False 如果記錄不存在
    """
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_expense_years() -> list[int]:
    """取得所有有資料的年份（降序排列）"""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT substr(date, 1, 4) as year FROM expenses ORDER BY year DESC")
        rows = cursor.fetchall()
        return [int(row["year"]) for row in rows]


def get_expense_months(year: int) -> list[int]:
    """取得指定年份有資料的月份（升序排列）"""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT DISTINCT CAST(substr(date, 6, 2) AS INTEGER) as month
               FROM expenses
               WHERE substr(date, 1, 4) = ?
               ORDER BY month""",
            (str(year),),
        )
        rows = cursor.fetchall()
        return [row["month"] for row in rows]


def get_dates_with_data(year: int, month: int) -> set[int]:
    """取得指定年月有資料的日期（回傳日期數字的集合）

    同時檢查支出記錄和備忘，任一有資料的日期都會包含在結果中
    """
    with db_connection() as conn:
        cursor = conn.cursor()
        # 合併查詢支出和備忘的日期
        cursor.execute(
            """SELECT DISTINCT CAST(substr(date, 9, 2) AS INTEGER) as day
               FROM expenses
               WHERE substr(date, 1, 4) = ? AND CAST(substr(date, 6, 2) AS INTEGER) = ?
               UNION
               SELECT DISTINCT CAST(substr(date, 9, 2) AS INTEGER) as day
               FROM memos
               WHERE substr(date, 1, 4) = ? AND CAST(substr(date, 6, 2) AS INTEGER) = ?""",
            (str(year), month, str(year), month),
        )
        rows = cursor.fetchall()
        return {row["day"] for row in rows}


def get_expenses_by_date(date: str) -> list[dict]:
    """取得指定日期的所有支出（按類別、人員排序）"""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM expenses WHERE date = ? ORDER BY category, person",
            (date,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def find_expenses_by_date_and_amount(date: str, amount: int) -> list[dict]:
    """查詢指定日期和金額已存在的支出記錄（用於重複偵測）"""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM expenses WHERE date = ? AND amount = ? ORDER BY category, person",
            (date, amount),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def delete_expenses_by_date(date: str) -> int:
    """刪除指定日期的所有支出

    Returns:
        刪除的記錄筆數
    """
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM expenses WHERE date = ?", (date,))
        count = cursor.rowcount
        conn.commit()
        return count


def delete_day_data(date: str) -> dict:
    """刪除指定日期的所有資料（支出+備忘+待審核）

    Returns:
        包含各類別刪除筆數的字典: {"expenses": int, "memos": int, "pending": int}
    """
    with db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("DELETE FROM expenses WHERE date = ?", (date,))
        expenses_count = cursor.rowcount

        cursor.execute("DELETE FROM memos WHERE date = ?", (date,))
        memos_count = cursor.rowcount

        cursor.execute("DELETE FROM pending_review WHERE date = ?", (date,))
        pending_count = cursor.rowcount

        conn.commit()

        return {
            "expenses": expenses_count,
            "memos": memos_count,
            "pending": pending_count
        }


# ========== Pending Review 操作 ==========


def add_pending_review(raw_text: str, source_line: str, date: str) -> int:
    """新增待審核項目

    Args:
        raw_text: 無法識別的原始文字
        source_line: 來源行
        date: 日期

    Returns:
        新增項目的 ID
    """
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO pending_review (raw_text, source_line, date, created_at)
               VALUES (?, ?, ?, ?)""",
            (raw_text.strip(), source_line.strip(), date, datetime.now().isoformat()),
        )
        conn.commit()
        return cursor.lastrowid


def get_all_pending_reviews() -> list[dict]:
    """取得所有待審核項目（按建立時間降序排列）"""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pending_review ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def delete_pending_review(review_id: int) -> bool:
    """刪除待審核項目

    Returns:
        True 如果刪除成功，False 如果項目不存在
    """
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pending_review WHERE id = ?", (review_id,))
        conn.commit()
        return cursor.rowcount > 0


# ========== Person Proxy 操作 ==========


def get_person_proxies() -> list[dict]:
    """取得所有代理關係（按 keyword 排序）"""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM person_proxy ORDER BY keyword")
        return [dict(row) for row in cursor.fetchall()]


def get_person_proxy_mappings() -> dict[str, str]:
    """取得 keyword→proxy_for 對應字典（供 parser 使用）"""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT keyword, proxy_for FROM person_proxy")
        return {row["keyword"]: row["proxy_for"] for row in cursor.fetchall()}


def add_person_proxy(keyword: str, proxy_for: str, note: str = "") -> int:
    """新增代理關係

    Raises:
        ValueError: keyword 或 proxy_for 為空，或 keyword 已存在
    """
    if not keyword or not keyword.strip():
        raise ValueError("關鍵字不可為空")
    if not proxy_for or not proxy_for.strip():
        raise ValueError("代理人員不可為空")

    keyword = keyword.strip()
    proxy_for = proxy_for.strip()

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM person_proxy WHERE keyword = ?", (keyword,))
        if cursor.fetchone():
            raise ValueError(f"關鍵字「{keyword}」已存在")
        cursor.execute(
            "INSERT INTO person_proxy (keyword, proxy_for, note) VALUES (?, ?, ?)",
            (keyword, proxy_for, note.strip()),
        )
        conn.commit()
        return cursor.lastrowid


def update_person_proxy(proxy_id: int, keyword: str, proxy_for: str, note: str = "") -> bool:
    """更新代理關係"""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE person_proxy SET keyword=?, proxy_for=?, note=? WHERE id=?",
            (keyword.strip(), proxy_for.strip(), note.strip(), proxy_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_person_proxy(proxy_id: int) -> bool:
    """刪除代理關係"""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM person_proxy WHERE id = ?", (proxy_id,))
        conn.commit()
        return cursor.rowcount > 0


# ========== Memos 操作 ==========


def get_memo_person_mappings() -> dict[str, str]:
    """取得所有備忘關鍵字→人名對應（keyword: person）"""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT keyword, person FROM memo_person_mapping")
        return {row["keyword"]: row["person"] for row in cursor.fetchall()}


def add_memo(date: str, content: str, person: Optional[str] = None) -> int:
    """新增備忘（如已存在相同內容則跳過）

    Args:
        date: 日期（格式：YYYY-MM-DD）
        content: 備忘內容
        person: 關聯人員（可選）

    Returns:
        新增備忘的 ID，如果已存在相同內容則回傳 -1
    """
    if not content or not content.strip():
        return -1

    content = content.strip()

    with db_connection() as conn:
        cursor = conn.cursor()

        # 檢查是否已存在相同備忘
        cursor.execute(
            "SELECT id FROM memos WHERE date = ? AND content = ?",
            (date, content)
        )
        if cursor.fetchone():
            return -1  # 已存在，跳過

        cursor.execute(
            "INSERT INTO memos (date, content, person) VALUES (?, ?, ?)",
            (date, content, person),
        )
        conn.commit()
        return cursor.lastrowid


def get_memos_by_date(date: str) -> list[dict]:
    """取得指定日期的備忘（按 ID 排序）"""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM memos WHERE date = ? ORDER BY id", (date,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_memos(year: Optional[int] = None, month: Optional[int] = None) -> list[dict]:
    """查詢備忘

    Args:
        year: 篩選年份（可選）
        month: 篩選月份（可選，需與 year 搭配使用）

    Returns:
        符合條件的備忘列表，按日期降序排列
    """
    with db_connection() as conn:
        cursor = conn.cursor()

        query = "SELECT * FROM memos WHERE 1=1"
        params = []

        if year is not None:
            query += " AND substr(date, 1, 4) = ?"
            params.append(str(year))

        if month is not None:
            query += " AND CAST(substr(date, 6, 2) AS INTEGER) = ?"
            params.append(month)

        query += " ORDER BY date DESC, id"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def delete_memo(memo_id: int) -> bool:
    """刪除備忘

    Returns:
        True 如果刪除成功，False 如果備忘不存在
    """
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memos WHERE id = ?", (memo_id,))
        conn.commit()
        return cursor.rowcount > 0


# ========== 清除資料 ==========


def clear_month_data(year: int, month: int) -> dict:
    """清除指定月份的所有資料（支出、待審核、備忘）

    Args:
        year: 年份
        month: 月份 (1-12)

    Returns:
        包含各類別刪除筆數的字典: {"expenses": int, "pending": int, "memos": int}

    Raises:
        ValueError: 如果月份不在 1-12 範圍內
    """
    if not 1 <= month <= 12:
        raise ValueError("月份必須在 1-12 之間")

    with db_connection() as conn:
        cursor = conn.cursor()

        # 清除該月支出
        cursor.execute(
            """DELETE FROM expenses
               WHERE substr(date, 1, 4) = ? AND CAST(substr(date, 6, 2) AS INTEGER) = ?""",
            (str(year), month)
        )
        expenses_count = cursor.rowcount

        # 清除該月待審核
        cursor.execute(
            """DELETE FROM pending_review
               WHERE substr(date, 1, 4) = ? AND CAST(substr(date, 6, 2) AS INTEGER) = ?""",
            (str(year), month)
        )
        pending_count = cursor.rowcount

        # 清除該月備忘
        cursor.execute(
            """DELETE FROM memos
               WHERE substr(date, 1, 4) = ? AND CAST(substr(date, 6, 2) AS INTEGER) = ?""",
            (str(year), month)
        )
        memos_count = cursor.rowcount

        conn.commit()

        return {
            "expenses": expenses_count,
            "pending": pending_count,
            "memos": memos_count
        }


# 初始化資料庫
init_db()

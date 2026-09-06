// 資料儲存層 - 以 localStorage 取代 SQLite，維持與原資料庫模組相同的操作介面
const STORAGE_KEY = "accounting_v1";

const DEFAULT_CATEGORIES = {
  早餐: 70,
  中餐: 150,
  晚餐: 150,
  牛奶: 40,
  點心: 0,
  飲料: 0,
  文具: 0,
};

const DEFAULT_PERSONS = ["阿鵰", "泰禎", "紫緹", "牧恩", "咏恩", "傑森", "崴崴"];

const DEFAULT_PROXIES = [
  { keyword: "台北媽媽", proxy_for: "牧恩", note: "牧恩的媽媽" },
  { keyword: "米媽媽", proxy_for: "傑森", note: "傑森的媽媽" },
];

function emptyState() {
  return {
    persons: DEFAULT_PERSONS.map((name, i) => ({ id: i + 1, name, aliases: "" })),
    category_prices: { ...DEFAULT_CATEGORIES },
    expenses: [],
    pending_review: [],
    memos: [],
    person_proxy: DEFAULT_PROXIES.map((p, i) => ({ id: i + 1, ...p })),
    next_id: { persons: DEFAULT_PERSONS.length + 1, expenses: 1, pending_review: 1, memos: 1, person_proxy: DEFAULT_PROXIES.length + 1 },
  };
}

let state = null;

function load() {
  if (state) return state;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    state = raw ? JSON.parse(raw) : emptyState();
  } catch (e) {
    console.error("讀取本機資料失敗，使用預設值", e);
    state = emptyState();
  }
  // 補齊可能缺少的欄位（升級舊資料用）
  const base = emptyState();
  for (const key of Object.keys(base)) {
    if (!(key in state)) state[key] = base[key];
  }
  for (const key of Object.keys(base.next_id)) {
    if (!(key in state.next_id)) state.next_id[key] = 1;
  }
  return state;
}

function save() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function nextId(table) {
  const id = state.next_id[table] || 1;
  state.next_id[table] = id + 1;
  return id;
}

export const db = {
  // ========== Persons ==========
  getAllPersons() {
    load();
    return [...state.persons].sort((a, b) => a.name.localeCompare(b.name, "zh-Hant"));
  },

  addPerson(name, aliases = "") {
    load();
    name = (name || "").trim();
    if (!name) throw new Error("人員名稱不可為空");
    if (state.persons.some((p) => p.name === name)) {
      throw new Error(`人員「${name}」已存在`);
    }
    const id = nextId("persons");
    state.persons.push({ id, name, aliases: aliases.trim() });
    save();
    return id;
  },

  updatePersonAliases(personId, aliases) {
    load();
    const p = state.persons.find((p) => p.id === personId);
    if (!p) return false;
    p.aliases = (aliases || "").trim();
    save();
    return true;
  },

  addAliasToPerson(personId, newAlias) {
    load();
    newAlias = (newAlias || "").trim();
    if (!newAlias) return false;
    const p = state.persons.find((p) => p.id === personId);
    if (!p) return false;
    const list = p.aliases ? p.aliases.split(",").map((a) => a.trim()).filter(Boolean) : [];
    if (list.includes(newAlias)) return false;
    list.push(newAlias);
    p.aliases = list.join(",");
    save();
    return true;
  },

  deletePerson(personId) {
    load();
    const before = state.persons.length;
    state.persons = state.persons.filter((p) => p.id !== personId);
    save();
    return state.persons.length < before;
  },

  // ========== Category Prices ==========
  getAllCategoryPrices() {
    load();
    return Object.fromEntries(
      Object.entries(state.category_prices).sort(([a], [b]) => a.localeCompare(b, "zh-Hant"))
    );
  },

  updateCategoryPrice(category, price) {
    load();
    if (price < 0) throw new Error("單價不可為負數");
    if (!(category in state.category_prices)) return false;
    state.category_prices[category] = price;
    save();
    return true;
  },

  // ========== Expenses ==========
  addExpense({ date, category, person, amount, quantity = 1, note = "" }) {
    load();
    if (!date || !category || !person) throw new Error("日期、類別、人員皆為必填");
    if (amount < 0) throw new Error("金額不可為負數");
    if (quantity <= 0) throw new Error("數量必須大於 0");
    const id = nextId("expenses");
    state.expenses.push({ id, date, category, person, amount, quantity, note });
    save();
    return id;
  },

  expenseExists(date, category, person) {
    load();
    return state.expenses.some((e) => e.date === date && e.category === category && e.person === person);
  },

  getExpenses({ year, month, persons } = {}) {
    load();
    let rows = state.expenses;
    if (year != null) rows = rows.filter((e) => e.date.slice(0, 4) === String(year));
    if (month != null) rows = rows.filter((e) => parseInt(e.date.slice(5, 7), 10) === month);
    if (persons && persons.length) rows = rows.filter((e) => persons.includes(e.person));
    return [...rows].sort((a, b) => (a.date + a.category + a.person).localeCompare(b.date + b.category + b.person));
  },

  deleteExpense(id) {
    load();
    const before = state.expenses.length;
    state.expenses = state.expenses.filter((e) => e.id !== id);
    save();
    return state.expenses.length < before;
  },

  getExpenseYears() {
    load();
    const years = new Set(state.expenses.map((e) => parseInt(e.date.slice(0, 4), 10)));
    return [...years].sort((a, b) => b - a);
  },

  getExpenseMonths(year) {
    load();
    const months = new Set(
      state.expenses.filter((e) => e.date.slice(0, 4) === String(year)).map((e) => parseInt(e.date.slice(5, 7), 10))
    );
    return [...months].sort((a, b) => a - b);
  },

  getDatesWithData(year, month) {
    load();
    const ym = `${year}-${String(month).padStart(2, "0")}`;
    const days = new Set();
    for (const e of state.expenses) if (e.date.startsWith(ym)) days.add(parseInt(e.date.slice(8, 10), 10));
    for (const m of state.memos) if (m.date.startsWith(ym)) days.add(parseInt(m.date.slice(8, 10), 10));
    return days;
  },

  getExpensesByDate(date) {
    load();
    return state.expenses
      .filter((e) => e.date === date)
      .sort((a, b) => (a.category + a.person).localeCompare(b.category + b.person));
  },

  findExpensesByDateAndAmount(date, amount) {
    load();
    return state.expenses.filter((e) => e.date === date && e.amount === amount);
  },

  deleteExpensesByDate(date) {
    load();
    const before = state.expenses.length;
    state.expenses = state.expenses.filter((e) => e.date !== date);
    save();
    return before - state.expenses.length;
  },

  deleteDayData(date) {
    load();
    const expensesCount = state.expenses.filter((e) => e.date === date).length;
    const memosCount = state.memos.filter((m) => m.date === date).length;
    const pendingCount = state.pending_review.filter((p) => p.date === date).length;
    state.expenses = state.expenses.filter((e) => e.date !== date);
    state.memos = state.memos.filter((m) => m.date !== date);
    state.pending_review = state.pending_review.filter((p) => p.date !== date);
    save();
    return { expenses: expensesCount, memos: memosCount, pending: pendingCount };
  },

  // ========== Pending Review ==========
  addPendingReview({ raw_text, source_line, date }) {
    load();
    const id = nextId("pending_review");
    state.pending_review.push({
      id,
      raw_text: raw_text.trim(),
      source_line: source_line.trim(),
      date,
      created_at: new Date().toISOString(),
    });
    save();
    return id;
  },

  getAllPendingReviews() {
    load();
    return [...state.pending_review].sort((a, b) => b.created_at.localeCompare(a.created_at));
  },

  deletePendingReview(id) {
    load();
    const before = state.pending_review.length;
    state.pending_review = state.pending_review.filter((p) => p.id !== id);
    save();
    return state.pending_review.length < before;
  },

  // ========== Person Proxy ==========
  getPersonProxies() {
    load();
    return [...state.person_proxy].sort((a, b) => a.keyword.localeCompare(b.keyword, "zh-Hant"));
  },

  getPersonProxyMappings() {
    load();
    return Object.fromEntries(state.person_proxy.map((p) => [p.keyword, p.proxy_for]));
  },

  addPersonProxy(keyword, proxyFor, note = "") {
    load();
    keyword = (keyword || "").trim();
    proxyFor = (proxyFor || "").trim();
    if (!keyword) throw new Error("關鍵字不可為空");
    if (!proxyFor) throw new Error("代理人員不可為空");
    if (state.person_proxy.some((p) => p.keyword === keyword)) {
      throw new Error(`關鍵字「${keyword}」已存在`);
    }
    const id = nextId("person_proxy");
    state.person_proxy.push({ id, keyword, proxy_for: proxyFor, note: (note || "").trim() });
    save();
    return id;
  },

  updatePersonProxy(id, keyword, proxyFor, note = "") {
    load();
    const p = state.person_proxy.find((p) => p.id === id);
    if (!p) return false;
    p.keyword = keyword.trim();
    p.proxy_for = proxyFor.trim();
    p.note = (note || "").trim();
    save();
    return true;
  },

  deletePersonProxy(id) {
    load();
    const before = state.person_proxy.length;
    state.person_proxy = state.person_proxy.filter((p) => p.id !== id);
    save();
    return state.person_proxy.length < before;
  },

  // ========== Memos ==========
  addMemo(date, content, person = null) {
    load();
    content = (content || "").trim();
    if (!content) return -1;
    if (state.memos.some((m) => m.date === date && m.content === content)) return -1;
    const id = nextId("memos");
    state.memos.push({ id, date, content, person: person || null });
    save();
    return id;
  },

  getMemosByDate(date) {
    load();
    return state.memos.filter((m) => m.date === date).sort((a, b) => a.id - b.id);
  },

  getMemos({ year, month } = {}) {
    load();
    let rows = state.memos;
    if (year != null) rows = rows.filter((m) => m.date.slice(0, 4) === String(year));
    if (month != null) rows = rows.filter((m) => parseInt(m.date.slice(5, 7), 10) === month);
    return [...rows].sort((a, b) => (b.date + String(b.id).padStart(10, "0")).localeCompare(a.date + String(a.id).padStart(10, "0")));
  },

  deleteMemo(id) {
    load();
    const before = state.memos.length;
    state.memos = state.memos.filter((m) => m.id !== id);
    save();
    return state.memos.length < before;
  },

  // ========== 清除資料 ==========
  clearMonthData(year, month) {
    load();
    if (month < 1 || month > 12) throw new Error("月份必須在 1-12 之間");
    const ym = `${year}-${String(month).padStart(2, "0")}`;
    const expensesCount = state.expenses.filter((e) => e.date.startsWith(ym)).length;
    const pendingCount = state.pending_review.filter((p) => p.date.startsWith(ym)).length;
    const memosCount = state.memos.filter((m) => m.date.startsWith(ym)).length;
    state.expenses = state.expenses.filter((e) => !e.date.startsWith(ym));
    state.pending_review = state.pending_review.filter((p) => !p.date.startsWith(ym));
    state.memos = state.memos.filter((m) => !m.date.startsWith(ym));
    save();
    return { expenses: expensesCount, pending: pendingCount, memos: memosCount };
  },

  // ========== 匯出 / 匯入整包資料 ==========
  exportAll() {
    load();
    return JSON.stringify(state, null, 2);
  },

  importAll(json) {
    const parsed = JSON.parse(json);
    state = parsed;
    save();
  },

  resetAll() {
    state = emptyState();
    save();
  },
};

// Tabby frontend: plain JavaScript that calls the two services directly.
// ledger (accounts, groups, expenses) and settlement (balances, payments) live
// at the URLs in config.js. After login the session token is kept in
// localStorage and sent as "Authorization: Bearer <token>" to both services.

const { ledgerUrl, settlementUrl } = window.TABBY_CONFIG;
const TOKEN_KEY = "tabby_token";

const state = {
  me: null,
  friends: [],
  groups: [],
  categories: [],
  group: null, // the open group: { id, name, members, expenses, spending, settlement, payments, settlementError }
};

// ---------- helpers ----------

async function call(baseUrl, serviceName, method, path, body) {
  const options = { method, headers: {} };
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) options.headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  // On Azure both services scale to zero. The first request after an idle
  // period starts a container (and maybe a paused database), and until it is
  // ready the platform answers 503 with no JSON body, or the request fails.
  // Reads are retried for about a minute with a visible notice; writes are
  // not repeated automatically, because the first try may still be processed.
  const tries = method === "GET" && COLD_STARTS ? STARTUP_TRIES : 1;
  for (let attempt = 1; ; attempt += 1) {
    let res = null;
    let data = null;
    try {
      res = await fetch(`${baseUrl}/api${path}`, options);
      if (res.status === 204) return null;
      data = await res.json().catch(() => null);
    } catch {
      // Network error, CORS refusal or the service being down.
    }
    if (res && res.ok) {
      startingUp(false);
      return data;
    }
    const starting = !res || ([502, 503, 504].includes(res.status) && !(data && data.detail));
    if (!starting) {
      startingUp(false);
      throw new Error(errorMessage(data, res.status));
    }
    if (attempt >= tries) {
      startingUp(false);
      throw new Error(`The ${serviceName} service is starting up or not reachable. Try again in a minute.`);
    }
    startingUp(true);
    await new Promise((resolve) => setTimeout(resolve, STARTUP_WAIT_MS));
  }
}

// Set by the deployed config.js; locally nothing scales to zero, so a service
// that does not answer is simply down and the UI says so at once.
const COLD_STARTS = Boolean((window.TABBY_CONFIG || {}).coldStarts);
const STARTUP_TRIES = 7;
const STARTUP_WAIT_MS = 10000;

// A notice that stays while a service is waking up.
function startingUp(on) {
  const box = document.getElementById("starting");
  if (box) box.hidden = !on;
}

const api = (method, path, body) => call(ledgerUrl, "ledger", method, path, body);
const settlementApi = (method, path, body) => call(settlementUrl, "settlement", method, path, body);

function errorMessage(data, status) {
  if (data && typeof data.detail === "string") return data.detail;
  if (data && Array.isArray(data.detail)) {
    return data.detail.map((d) => `${d.loc[d.loc.length - 1]}: ${d.msg}`).join("; ");
  }
  return `Request failed (${status})`;
}

// Builds DOM nodes. Text always goes in as text nodes, never as HTML.
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (key === "class") node.className = value;
    else if (key === "value") node.value = value;
    else if (value === true) node.setAttribute(key, "");
    else if (value !== false && value != null) node.setAttribute(key, value);
  }
  node.append(...children.flat().filter((c) => c != null && c !== false));
  return node;
}

const euros = (cents) => `€${(cents / 100).toFixed(2)}`;
const toCents = (text) => Math.round(parseFloat(String(text).replace(",", ".")) * 100);
const $ = (id) => document.getElementById(id);

function toast(message, isError = false) {
  const box = $("toast");
  box.textContent = message;
  box.className = isError ? "error" : "";
  box.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (box.hidden = true), 3500);
}

// Runs an action and shows any API error as a toast instead of failing silently.
async function attempt(action, successMessage) {
  try {
    await action();
    if (successMessage) toast(successMessage);
  } catch (err) {
    toast(err.message, true);
  }
}

// Reads a form field by name. (form.name would be the form's own name attribute.)
const field = (form, name) => form.elements.namedItem(name).value;

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

// ---------- loading ----------

async function start() {
  if (!localStorage.getItem(TOKEN_KEY)) {
    showAuth();
    return;
  }
  try {
    state.me = await api("GET", "/me");
  } catch (err) {
    showAuth();
    if (!err.message.includes("log in")) toast(err.message, true);
    return;
  }
  await loadHome();
}

function saveSession(session) {
  localStorage.setItem(TOKEN_KEY, session.token);
  state.me = session.user;
}

function showAuth() {
  state.me = null;
  $("auth-view").hidden = false;
  $("app-view").hidden = true;
  $("whoami").replaceChildren();
}

async function loadHome() {
  $("auth-view").hidden = true;
  $("app-view").hidden = false;
  [state.friends, state.groups, state.categories] = await Promise.all([
    api("GET", "/friends"),
    api("GET", "/groups"),
    api("GET", "/categories"),
  ]);
  renderWhoami();
  renderFriends();
  renderGroups();
}

async function openGroup(groupId) {
  const base = `/groups/${groupId}`;
  const [detail, expenses, spending] = await Promise.all([
    api("GET", base),
    api("GET", `${base}/expenses`),
    api("GET", `${base}/spending`),
  ]);
  // Settlement is the other service: if it is down, the ledger part of the
  // group still works and the balances card explains what is missing.
  let settlement = null;
  let payments = [];
  let settlementError = null;
  try {
    [settlement, payments] = await Promise.all([
      settlementApi("GET", `${base}/settlement`),
      settlementApi("GET", `${base}/payments`),
    ]);
  } catch (err) {
    settlementError = err.message;
  }
  state.group = { ...detail, expenses, spending, settlement, payments, settlementError };
  renderGroups();
  renderGroup();
}

// ---------- sidebar ----------

function renderWhoami() {
  $("whoami").replaceChildren(
    el("span", {}, `${state.me.display_name} (@${state.me.username})`),
    el("button", { class: "secondary small", onclick: logOut }, "Log out"),
  );
}

function renderFriends() {
  $("friend-list").replaceChildren(
    ...(state.friends.length
      ? state.friends.map((f) => el("li", {}, f.display_name, el("span", { class: "muted" }, `@${f.username}`)))
      : [el("li", { class: "muted" }, "No friends yet. Add someone by username.")]),
  );
  $("group-friends").replaceChildren(
    ...state.friends.map((f) =>
      el("label", {}, el("input", { type: "checkbox", name: "member", value: String(f.id) }), f.display_name),
    ),
  );
}

function renderGroups() {
  $("group-list").replaceChildren(
    ...(state.groups.length
      ? state.groups.map((g) =>
          el("li", {},
            el("button", {
              class: `group-link${state.group && state.group.id === g.id ? " active" : ""}`,
              onclick: () => attempt(() => openGroup(g.id)),
            }, g.name),
          ),
        )
      : [el("li", { class: "muted" }, "No groups yet.")]),
  );
}

// ---------- group view ----------

function nameOf(userId) {
  const member = state.group.members.find((m) => m.id === userId);
  if (!member) return `user ${userId}`;
  return member.id === state.me.id ? "You" : member.display_name;
}

function renderGroup() {
  const g = state.group;
  $("group-view").replaceChildren(
    el("div", { class: "card" }, el("h2", {}, g.name), el("div", { class: "muted" },
      g.members.map((m) => m.display_name).join(", "))),
    el("div", { class: "grid2" }, settleCard(), expenseFormCard()),
    expensesCard(),
    el("div", { class: "grid2" }, spendingCard(), membersCard()),
  );
}

function settleCard() {
  if (state.group.settlementError) {
    return el("div", { class: "card" },
      el("h2", {}, "Balances"),
      el("p", { class: "unavailable" }, "Balances and settle-up are unavailable right now."),
      el("p", { class: "muted" }, state.group.settlementError),
      el("button", { class: "secondary small", onclick: () => attempt(() => openGroup(state.group.id)) }, "Retry"),
    );
  }
  const { balances, transfers } = state.group.settlement;
  return el("div", { class: "card" },
    el("h2", {}, "Balances"),
    el("ul", { class: "plain" }, balances.map((b) =>
      el("li", {}, nameOf(b.user_id), el("span", {
        class: `amount ${b.balance_cents > 0 ? "owed" : b.balance_cents < 0 ? "owes" : ""}`,
      }, b.balance_cents > 0 ? `gets ${euros(b.balance_cents)}` : b.balance_cents < 0
        ? `owes ${euros(-b.balance_cents)}` : "settled")),
    )),
    el("h3", {}, "To settle up"),
    el("ul", { class: "plain" }, transfers.length ? transfers.map((t) =>
      el("li", {},
        el("span", {}, `${nameOf(t.from_user_id)} → ${nameOf(t.to_user_id)} `,
          el("span", { class: "amount" }, euros(t.amount_cents))),
        t.from_user_id === state.me.id
          ? el("button", { class: "small", onclick: () => recordPayment(t) }, "I paid this")
          : null,
      ),
    ) : [el("li", { class: "muted" }, "Everyone is settled up.")]),
    el("h3", {}, "Payments"),
    el("ul", { class: "plain" }, state.group.payments.length ? state.group.payments.map((p) =>
      el("li", {}, `${nameOf(p.from_user_id)} paid ${nameOf(p.to_user_id)}`,
        el("span", { class: "amount" }, euros(p.amount_cents))),
    ) : [el("li", { class: "muted" }, "No payments recorded yet.")]),
  );
}

// Today in the browser's own time zone, as YYYY-MM-DD.
function today() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function expenseFormCard() {
  const g = state.group;
  const form = el("form", { class: "split-equal", onsubmit: (e) => addExpense(e, form) },
    el("label", {}, "Description", el("input", { name: "description", required: true, maxlength: "200" })),
    el("label", {}, "Amount (€)", el("input", { name: "amount", inputmode: "decimal", required: true, placeholder: "12.50" })),
    el("label", {}, "Category", el("select", { name: "category_id" },
      state.categories.map((c) => el("option", { value: String(c.id) }, c.name)))),
    el("label", {}, "Paid by", el("select", { name: "payer_id" },
      g.members.map((m) => el("option", { value: String(m.id), selected: m.id === state.me.id }, nameOf(m.id))))),
    el("label", {}, "Spent on", el("input", { name: "spent_on", type: "date", value: today(), max: today() })),
    el("label", {}, "Split", el("select", {
      name: "split_type",
      onchange: (e) => { form.className = `split-${e.target.value}`; },
    },
      el("option", { value: "equal" }, "Equally"),
      el("option", { value: "shares" }, "By shares (weights)"),
      el("option", { value: "exact" }, "By exact amounts (€)"),
    )),
    g.members.map((m) => el("div", { class: "participant", "data-user-id": String(m.id) },
      el("input", { type: "checkbox", checked: true, "aria-label": `Include ${m.display_name}` }),
      el("span", {}, nameOf(m.id)),
      el("input", { class: "part-value", value: "1", inputmode: "decimal", "aria-label": `Value for ${m.display_name}` }),
    )),
    el("button", {}, "Add expense"),
  );
  return el("div", { class: "card" }, el("h2", {}, "Add expense"), form);
}

function expensesCard() {
  const categoryName = (id) => (state.categories.find((c) => c.id === id) || {}).name || "";
  const expenses = state.group.expenses;
  return el("div", { class: "card" },
    el("h2", {}, "Expenses"),
    el("ul", { class: "plain" }, expenses.length ? expenses.map((e) =>
      el("li", {},
        el("div", {},
          el("div", {}, e.description),
          el("div", { class: "muted" },
            `${nameOf(e.payer_id)} paid · ${categoryName(e.category_id)} · ${e.split_type} · ${e.spent_on}`),
        ),
        el("span", {},
          el("span", { class: "amount" }, euros(e.amount_cents)), " ",
          el("button", { class: "secondary small", onclick: () => deleteExpense(e), "aria-label": "Delete expense" }, "✕"),
        ),
      ),
    ) : [el("li", { class: "muted" }, "No expenses yet.")]),
  );
}

function spendingCard() {
  const rows = state.group.spending;
  const max = Math.max(1, ...rows.map((r) => r.total_cents));
  return el("div", { class: "card" },
    el("h2", {}, "Spending by category"),
    rows.length ? rows.map((r) => el("div", { class: "bar-row" },
      el("span", {}, r.name),
      el("div", { class: "bar", style: `width: ${Math.max(2, (100 * r.total_cents) / max)}%` }),
      el("span", { class: "amount" }, euros(r.total_cents)),
    )) : el("div", { class: "muted" }, "Nothing spent yet."),
  );
}

function membersCard() {
  const g = state.group;
  const memberIds = new Set(g.members.map((m) => m.id));
  const addable = state.friends.filter((f) => !memberIds.has(f.id));
  const select = el("select", { name: "user_id" }, addable.map((f) => el("option", { value: String(f.id) }, f.display_name)));
  return el("div", { class: "card" },
    el("h2", {}, "Members"),
    el("ul", { class: "plain" }, g.members.map((m) =>
      el("li", {}, nameOf(m.id), m.id === state.me.id ? null
        : el("button", { class: "secondary small", onclick: () => removeMember(m) }, "Remove")),
    )),
    addable.length
      ? el("form", { class: "inline", onsubmit: (e) => addMember(e, select) }, select, el("button", {}, "Add"))
      : el("div", { class: "muted" }, "All your friends are in this group."),
  );
}

// ---------- actions ----------

async function logIn(event) {
  event.preventDefault();
  await attempt(async () => {
    saveSession(await api("POST", "/login", formData(event.target)));
    event.target.reset();
    await loadHome();
  });
}

async function signUp(event) {
  event.preventDefault();
  await attempt(async () => {
    saveSession(await api("POST", "/signup", formData(event.target)));
    event.target.reset();
    await loadHome();
  }, "Welcome to Tabby!");
}

async function logOut() {
  await attempt(async () => {
    await api("POST", "/logout");
    localStorage.removeItem(TOKEN_KEY);
    state.group = null;
    $("group-view").replaceChildren(el("div", { class: "card empty" }, "Pick a group, or create one with your friends."));
    showAuth();
  });
}

async function addFriend(event) {
  event.preventDefault();
  const form = event.target;
  await attempt(async () => {
    const friend = await api("POST", "/friends", formData(form));
    form.reset();
    await loadHome();
    toast(`${friend.display_name} is now your friend`);
  });
}

async function createGroup(event) {
  event.preventDefault();
  const form = event.target;
  const memberIds = [...form.querySelectorAll("input[name=member]:checked")].map((i) => Number(i.value));
  await attempt(async () => {
    const group = await api("POST", "/groups", { name: field(form, "name"), member_ids: memberIds });
    form.reset();
    await loadHome();
    await openGroup(group.id);
  }, "Group created");
}

async function addExpense(event, form) {
  event.preventDefault();
  const splitType = field(form, "split_type");
  const participants = [...form.querySelectorAll(".participant")]
    .filter((row) => row.querySelector("input[type=checkbox]").checked)
    .map((row) => {
      const raw = row.querySelector(".part-value").value;
      const value = splitType === "exact" ? toCents(raw) : splitType === "shares" ? parseInt(raw, 10) : 1;
      return { user_id: Number(row.dataset.userId), value };
    });
  const amount = toCents(field(form, "amount"));
  if (Number.isNaN(amount) || participants.some((p) => Number.isNaN(p.value))) {
    toast("Please enter valid numbers", true);
    return;
  }
  await attempt(async () => {
    await api("POST", `/groups/${state.group.id}/expenses`, {
      description: field(form, "description"),
      amount_cents: amount,
      payer_id: Number(field(form, "payer_id")),
      split_type: splitType,
      category_id: Number(field(form, "category_id")),
      participants,
      spent_on: field(form, "spent_on") || null,
    });
    await openGroup(state.group.id);
  }, "Expense added");
}

async function deleteExpense(expense) {
  if (!confirm(`Delete "${expense.description}"?`)) return;
  await attempt(async () => {
    await api("DELETE", `/groups/${state.group.id}/expenses/${expense.id}`);
    await openGroup(state.group.id);
  }, "Expense deleted");
}

async function recordPayment(transfer) {
  await attempt(async () => {
    await settlementApi("POST", `/groups/${state.group.id}/payments`, {
      to_user_id: transfer.to_user_id,
      amount_cents: transfer.amount_cents,
    });
    await openGroup(state.group.id);
  }, "Payment recorded");
}

async function addMember(event, select) {
  event.preventDefault();
  await attempt(async () => {
    await api("POST", `/groups/${state.group.id}/members`, { user_id: Number(select.value) });
    await openGroup(state.group.id);
  }, "Member added");
}

async function removeMember(member) {
  await attempt(async () => {
    await api("DELETE", `/groups/${state.group.id}/members/${member.id}`);
    await openGroup(state.group.id);
  }, `${member.display_name} removed`);
}

// ---------- wire up ----------

$("login-form").addEventListener("submit", logIn);
$("signup-form").addEventListener("submit", signUp);
$("friend-form").addEventListener("submit", addFriend);
$("group-form").addEventListener("submit", createGroup);
start();

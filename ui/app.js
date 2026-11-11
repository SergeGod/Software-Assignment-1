// Tabby frontend: plain JavaScript that talks to the JSON API under /api.
// The browser sends the tabby_session cookie automatically on every request.

const state = {
  me: null,
  friends: [],
  groups: [],
  categories: [],
  group: null, // the open group: { id, name, members, expenses, settlement, payments, spending }
};

// ---------- helpers ----------

async function api(method, path, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const res = await fetch(`/api${path}`, options);
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(errorMessage(data, res.status));
  return data;
}

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
  try {
    state.me = await api("GET", "/me");
  } catch {
    showAuth();
    return;
  }
  await loadHome();
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
  const [detail, expenses, settlement, payments, spending] = await Promise.all([
    api("GET", base),
    api("GET", `${base}/expenses`),
    api("GET", `${base}/settlement`),
    api("GET", `${base}/payments`),
    api("GET", `${base}/spending`),
  ]);
  state.group = { ...detail, expenses, settlement, payments, spending };
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

function expenseFormCard() {
  const g = state.group;
  const form = el("form", { class: "split-equal", onsubmit: (e) => addExpense(e, form) },
    el("label", {}, "Description", el("input", { name: "description", required: true, maxlength: "200" })),
    el("label", {}, "Amount (€)", el("input", { name: "amount", inputmode: "decimal", required: true, placeholder: "12.50" })),
    el("label", {}, "Category", el("select", { name: "category_id" },
      state.categories.map((c) => el("option", { value: String(c.id) }, c.name)))),
    el("label", {}, "Paid by", el("select", { name: "payer_id" },
      g.members.map((m) => el("option", { value: String(m.id), selected: m.id === state.me.id }, nameOf(m.id))))),
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
            `${nameOf(e.payer_id)} paid · ${categoryName(e.category_id)} · ${e.split_type} · ${e.created_at.slice(0, 10)}`),
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
    state.me = await api("POST", "/login", formData(event.target));
    event.target.reset();
    await loadHome();
  });
}

async function signUp(event) {
  event.preventDefault();
  await attempt(async () => {
    state.me = await api("POST", "/signup", formData(event.target));
    event.target.reset();
    await loadHome();
  }, "Welcome to Tabby!");
}

async function logOut() {
  await attempt(async () => {
    await api("POST", "/logout");
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
    await api("POST", `/groups/${state.group.id}/payments`, {
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

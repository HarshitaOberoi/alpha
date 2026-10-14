const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

let org = localStorage.getItem("org") || "northwind";

export function setOrg(slug) {
  org = slug;
  localStorage.setItem("org", slug);
}

export function getOrg() {
  return org;
}

async function request(path, options = {}) {
  const headers = {
    "X-Organization": org,
    ...(options.headers || {}),
  };
  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
  let data = null;
  const text = await resp.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!resp.ok) {
    const message = (data && data.error) || `Request failed (${resp.status})`;
    const err = new Error(message);
    err.status = resp.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const api = {
  getOrganizations: () => request("/organizations/"),
  getTransactions: () => request("/transactions/"),
  getLineItems: () => request("/line-items/"),
  importCsv: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/import/", {
      method: "POST",
      body: form,
    });
  },
  approveMatch: (id) =>
    request(`/matches/${id}/approve/`, { method: "POST" }),
  rejectMatch: (id) =>
    request(`/matches/${id}/reject/`, { method: "POST" }),
  ignoreTransaction: (id) =>
    request(`/transactions/${id}/ignore/`, { method: "POST" }),
};

export function formatMoney(amount) {
  const n = Number(amount);
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

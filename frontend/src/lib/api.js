// Thin fetch wrapper — always sends the session cookie.
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

async function request(path, { method = "GET", body, headers } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(headers || {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  if (!res.ok) {
    const err = new Error(data?.detail || `Request failed (${res.status})`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const api = {
  exchangeSession: (session_id) => request("/auth/session", { method: "POST", body: { session_id } }),
  me: () => request("/auth/me"),
  logout: () => request("/auth/logout", { method: "POST" }),
  login: ({ email, password }) => request("/auth/login", { method: "POST", body: { email, password } }),
  forgotPassword: ({ email }) => request("/auth/forgot-password", { method: "POST", body: { email } }),
  resetPassword: ({ token, new_password }) =>
    request("/auth/reset-password", { method: "POST", body: { token, new_password } }),
  changePassword: ({ current_password, new_password }) =>
    request("/auth/change-password", {
      method: "POST",
      body: { current_password: current_password || null, new_password },
    }),
  // GitHub
  githubStatus: () => request("/github/status"),
  githubConnect: () => request("/github/connect"),
  githubDisconnect: () => request("/github/disconnect", { method: "POST" }),
  githubRepos: () => request("/github/repos"),
  // Projects
  listProjects: () => request("/projects"),
  trackProject: (github_repo_id) =>
    request("/projects", { method: "POST", body: { github_repo_id } }),
  getProject: (id) => request(`/projects/${id}`),
  deleteProject: (id) => request(`/projects/${id}`, { method: "DELETE" }),
  scanProject: (id) => request(`/projects/${id}/scan`, { method: "POST" }),
  toggleNextStep: (id, done) =>
    request(`/next-steps/${id}`, { method: "PATCH", body: { done } }),
};

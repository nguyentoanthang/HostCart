/**
 * HostCart API Client
 * Centralized client for communicating with the FastAPI backend.
 */

const TOKEN_KEY = "hostcart_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function removeToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export async function apiRequest(endpoint, options = {}) {
  const token = getToken();
  const headers = { ...options.headers };

  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Do not set Content-Type if body is FormData
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(endpoint, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    // If unauthorized, clear invalid token
    // removeToken();
  }

  if (!response.ok) {
    let errorDetail = "API request failed";
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || JSON.stringify(errJson);
    } catch {
      errorDetail = await response.text();
    }
    const error = new Error(errorDetail || `HTTP error ${response.status}`);
    error.status = response.status;
    throw error;
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return await response.json();
  }
  return await response.text();
}

// Auth API
export const auth = {
  async login(username, password) {
    const data = await apiRequest("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    if (data.access_token) {
      setToken(data.access_token);
    }
    return data;
  },

  async register(username, email, password) {
    const data = await apiRequest("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, email, password }),
    });
    if (data.access_token) {
      setToken(data.access_token);
    }
    return data;
  },

  async getMe() {
    return await apiRequest("/api/v1/auth/me", {
      method: "GET",
    });
  },

  logout() {
    removeToken();
  },
};

// Collection API
export const collection = {
  async list(params = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== "") {
        query.append(key, val);
      }
    });
    const qs = query.toString();
    return await apiRequest(`/api/v1/collection${qs ? `?${qs}` : ""}`, {
      method: "GET",
    });
  },

  async get(id) {
    return await apiRequest(`/api/v1/collection/${id}`, {
      method: "GET",
    });
  },

  async create(data) {
    return await apiRequest("/api/v1/collection", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async update(id, data) {
    return await apiRequest(`/api/v1/collection/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  async increment(id, amount = 1.0) {
    return await apiRequest(`/api/v1/collection/${id}/increment`, {
      method: "POST",
      body: JSON.stringify({ amount }),
    });
  },

  async remove(id) {
    return await apiRequest(`/api/v1/collection/${id}`, {
      method: "DELETE",
    });
  },

  async getStats() {
    return await apiRequest("/api/v1/collection/stats", {
      method: "GET",
    });
  },
};

// Search API
export const search = {
  async searchExternal(q, media_type) {
    const query = new URLSearchParams({
      q: q.trim(),
      media_type,
    });
    return await apiRequest(`/api/v1/search?${query.toString()}`, {
      method: "GET",
    });
  },
};

// Import / Export API
export const importExport = {
  async exportData(format = "json", media_type = null) {
    const query = new URLSearchParams({ format });
    if (media_type) {
      query.append("media_type", media_type);
    }
    const token = getToken();
    const headers = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const res = await fetch(`/api/v1/import-export/export?${query.toString()}`, {
      headers,
    });
    if (!res.ok) {
      throw new Error(`Export failed: ${res.statusText}`);
    }
    const blob = await res.blob();
    const filename = `hostcart_export_${new Date().toISOString().slice(0, 10)}.${format}`;
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    return true;
  },

  async importData(payload, isFormData = false, skipDuplicates = true) {
    const qs = new URLSearchParams({ skip_duplicates: skipDuplicates }).toString();
    const endpoint = `/api/v1/import-export/import?${qs}`;

    if (isFormData) {
      return await apiRequest(endpoint, {
        method: "POST",
        body: payload, // FormData instance
      });
    }

    // JSON or CSV string
    const headers = typeof payload === "string" ? { "Content-Type": "text/csv" } : { "Content-Type": "application/json" };
    return await apiRequest(endpoint, {
      method: "POST",
      headers,
      body: typeof payload === "string" ? payload : JSON.stringify(payload),
    });
  },
};

// Runtime Settings API
export const settings = {
  async getSettings() {
    return await apiRequest("/api/v1/settings", {
      method: "GET",
    });
  },

  async updateSettings(data) {
    return await apiRequest("/api/v1/settings", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },
};

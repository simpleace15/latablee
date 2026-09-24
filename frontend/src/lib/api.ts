// Typed API client. Single source of truth for endpoint shapes (mirrors backend /api/v1).

export const API = "/api/v1";

// ---------- auth ----------
export interface User {
  public_id: string;
  name: string;
  role: "admin" | "user";
  household_id: number | null;
}

export async function getToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("latablee_token");
}

export async function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem("latablee_token", token);
  else window.localStorage.removeItem("latablee_token");
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await getToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const res = await fetch(`${API}${path}`, { ...init, headers });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = undefined;
  try {
    data = text ? JSON.parse(text) : undefined;
  } catch {
    /* non-JSON error body */
  }
  if (!res.ok) {
    const message =
      (data && typeof data === "object" && "detail" in data && typeof (data as { detail: unknown }).detail === "string")
        ? (data as { detail: string }).detail
        : `Request failed (${res.status})`;
    throw new ApiError(res.status, message);
  }
  return data as T;
}

// ---------- models ----------
export interface Ingredient {
  name: string;
  quantity?: number | null;
  unit?: string | null;
  raw?: string | null;
}

export interface Recipe {
  id: number | null;
  title: string;
  description: string;
  servings: number;
  prep_minutes: number | null;
  cook_minutes: number | null;
  total_minutes: number | null;
  instructions: string[];
  ingredients: Ingredient[];
  tags: string[];
  source_url: string | null;
  source_name: string | null;
  image_b64?: string | null;
  image_path: string | null;
  is_favorite?: boolean;
  created_at: string;
  updated_at: string;
}

export interface Household {
  id: number;
  name: string;
  timezone: string;
  dietary_preferences: Record<string, string> | null;
  allergies: string[] | null;
  dislikes: string[] | null;
  favorites: string[] | null;
  planning_rules: string[] | null;
  things_to_remember: string;
}

export interface PlanEntry {
  id: number;
  date: string;
  slot: "breakfast" | "lunch" | "dinner" | "other";
  recipe_id: number | null;
  title_override: string | null;
  notes: string;
  recipe_title: string | null;
}

export interface ListItem {
  id: number;
  name: string;
  quantity: number | null;
  unit: string | null;
  done: boolean;
  manual: boolean;
  from_recipe_ids: number[];
}

export interface ShoppingList {
  id: number;
  name: string;
  items: ListItem[];
}

export interface InviteInfo {
  invite_url: string;
  expires_days: number;
}

// ---------- endpoints ----------
export const api = {
  // auth
  register: (name: string, password: string, inviteToken?: string) =>
    request<{ token: string; user: User }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(
        inviteToken
          ? { name, password, invite_token: inviteToken }
          : { name, password },
      ),
    }),
  login: (username: string, password: string) =>
    request<{ access_token: string; token_type: string }>("/auth/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username, password }),
    }),
  setTokenFromLogin: (token: string) => setToken(token),
  me: () => request<User>("/auth/me"),
  createInvite: () =>
    request<{ invite_url: string; expires_days: number }>("/auth/invite", { method: "POST" }),

  // household
  onboard: (payload: {
    name: string;
    timezone: string;
    dietary_preferences?: Record<string, string> | null;
    allergies?: string[] | null;
    dislikes?: string[] | null;
    favorites?: string[] | null;
    things_to_remember?: string;
  }) => request<{ id: number; name: string; timezone: string }>("/household/onboard", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  household: () => request<Household>("/household"),
  updateHousehold: (payload: Partial<Household> & { name: string }) =>
    request<{ id: number; name: string; timezone: string }>("/household", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  // migration import
  migratePreview: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ would_import: number; skipped: number; format: string; with_images: number }>(
      "/migrate/preview", { method: "POST", body: form },
    );
  },
  migrateRun: (file: File, loadImages = true) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ imported: number; failed: { title: string; error: string }[]; skipped: number; format: string }>(
      `/migrate?load_images=${loadImages ? "true" : "false"}`, { method: "POST", body: form },
    );
  },

  // admin
  seedDemo: () =>
    request<{ seeded: boolean; reason?: string; recipes?: number; admin_user?: string }>(
      "/admin/seed", { method: "POST", body: JSON.stringify({}) },
    ),

  // recipes
  recipes: (q = "", tag = "") =>
    request<Recipe[]>(`/recipes?q=${encodeURIComponent(q)}&tag=${encodeURIComponent(tag)}`),
  recipe: (id: number) => request<Recipe>(`/recipes/${id}`),
  createRecipe: (r: Partial<Recipe>) =>
    request<Recipe>("/recipes", { method: "POST", body: JSON.stringify(r) }),
  updateRecipe: (id: number, r: Partial<Recipe>) =>
    request<Recipe>(`/recipes/${id}`, { method: "PUT", body: JSON.stringify(r) }),
  deleteRecipe: (id: number) => request<void>(`/recipes/${id}`, { method: "DELETE" }),
  toggleFavorite: (id: number, favorite: boolean) =>
    request<{ id: number; is_favorite: boolean }>(`/recipes/${id}/favorite?favorite=${favorite}`, {
      method: "PUT",
    }),
  uploadRecipeImage: (id: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ image_path: string }>(`/recipes/${id}/image`, {
      method: "POST",
      body: form,
    });
  },

  // plan
  plan: (start?: string, days = 7) =>
    request<{ start: string; days: number; entries: PlanEntry[] }>(
      `/plan${start ? `?start=${start}` : ""}${start ? `&days=${days}` : `?days=${days}`}`,
    ),
  addPlanEntry: (payload: {
    date: string;
    slot: string;
    recipe_id?: number | null;
    title_override?: string | null;
    notes?: string;
  }) => request<PlanEntry>("/plan", { method: "POST", body: JSON.stringify(payload) }),
  deletePlanEntry: (id: number) => request<void>(`/plan/${id}`, { method: "DELETE" }),

  // lists
  lists: () => request<ShoppingList[]>("/lists"),
  list: (id: number) => request<ShoppingList>(`/lists/${id}`),
  createList: (name = "Groceries") =>
    request<ShoppingList>("/lists", { method: "POST", body: JSON.stringify({ name }) }),
  deleteList: (id: number) => request<void>(`/lists/${id}`, { method: "DELETE" }),
  addListItem: (listId: number, name: string, quantity?: number | null, unit?: string | null) =>
    request<ListItem>(`/lists/${listId}/items`, {
      method: "POST",
      body: JSON.stringify({ name, quantity, unit }),
    }),
  checkListItem: (listId: number, itemId: number, done: boolean) =>
    request<ListItem>(`/lists/${listId}/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify({ done }),
    }),
  removeListItem: (listId: number, itemId: number) =>
    request<void>(`/lists/${listId}/items/${itemId}`, { method: "DELETE" }),
  generateFromPlan: (listId: number) =>
    request<ShoppingList>(`/lists/${listId}/generate-from-plan`, { method: "POST" }),
  addRecipeToList: (listId: number, recipeId: number) =>
    request<ShoppingList>(`/lists/${listId}/add-recipe/${recipeId}`, { method: "POST" }),

  // import
  importFromUrl: (url: string) =>
    request<{ parsed: Partial<Recipe>; note: string }>("/import/url", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  // admin llm diagnostics
  adminLlmTest: () =>
    request<{ ok: boolean; seconds?: number; model?: string; reply?: string; error?: string }>(
      "/admin/llm/test", { method: "POST" }),
  adminLlmLog: () =>
    request<{ entries: { at: string; kind: string; status: string; seconds?: number;
      model?: string; error?: string; prompt_chars?: number; image?: boolean; note?: string }[] }>(
      "/admin/llm/log"),
  adminLlmGetTimeout: () =>
    request<{ timeout_seconds: number | null }>("/admin/llm/timeout"),
  adminLlmSetTimeout: (timeout_seconds: number) =>
    request<{ timeout_seconds: number }>("/admin/llm/timeout", {
      method: "POST",
      body: JSON.stringify({ timeout_seconds }),
    }),
  importFromUrls: (urls: string) =>
    request<{
      results: { url: string; ok: boolean; parsed?: Partial<Recipe>; error?: string }[];
      total: number;
      ok_count: number;
      note: string;
    }>("/import/urls", {
      method: "POST",
      body: JSON.stringify({ urls }),
    }),
  importFromPhoto: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ parsed: Partial<Recipe>; note: string }>("/import/photo", {
      method: "POST",
      body: form,
    });
  },
  importReel: (url: string) =>
    request<{ parsed: Partial<Recipe>; note: string }>("/llm/reel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    }),

  // llm
  llmStatus: () => request<{ configured: boolean }>("/llm/status"),
  llmSettings: () =>
    request<{ base_url: string; model: string; vision_model: string; system_prompt: string; api_key_set: boolean }>(
      "/llm/settings",
    ),
  saveLLMSettings: (payload: {
    base_url: string;
    api_key: string;
    model: string;
    vision_model: string;
    system_prompt: string;
  }) => request<{ saved: boolean }>("/llm/settings", { method: "PUT", body: JSON.stringify(payload) }),
  suggestMeals: () => request<{ suggestions: string }>("/llm/suggest-meals", { method: "POST" }),
  refillWeek: (payload?: { days?: number; slots?: string[]; start_date?: string; replace?: boolean }) =>
    request<{
      filled: { date: string; slot: string; recipe_id: number; title: string; why: string }[];
      proposals: {
        date: string; slot: string; from_book: boolean; title: string; why: string;
        recipe: Partial<Recipe> | null;
      }[];
      cleared?: { date: string; slot: string; title?: string | null; recipe_id?: number | null }[];
      message?: string;
    }>("/llm/refill-week", { method: "POST", body: JSON.stringify(payload ?? {}) }),
  saveProposal: (payload: {
    recipe: Partial<Recipe>; date?: string; slot?: string;
  }) => request<Recipe & { planned: boolean }>("/llm/save-proposal", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  discoverIdeas: (payload?: { count?: number; craving?: string }) =>
    request<{ ideas: Array<Partial<Recipe> & { cuisine?: string; why?: string }> }>(
      "/llm/discover",
      { method: "POST", body: JSON.stringify(payload ?? {}) },
    ),
  generateRecipe: (payload: { prompt?: string; ingredients?: string[] }) =>
    request<{ parsed: Partial<Recipe> }>("/llm/generate-recipe", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // device tokens (integrations)
  createToken: (name: string) =>
    request<{ id: number; name: string; token: string; note: string }>("/tokens", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  tokens: () =>
    request<{ tokens: { id: number; name: string; created_at: string; last_used_at: string | null; revoked: boolean }[] }>(
      "/tokens",
    ),
  revokeToken: (id: number) => request<void>(`/tokens/${id}`, { method: "DELETE" }),

  // backup restore
  restoreBackup: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ restored: Record<string, number> }>("/export/restore", {
      method: "POST",
      body: form,
    });
  },

  // events (poll for live sync)
  eventsSince: (afterId: number) =>
    request<{ events: Array<{ id: number; event: string; payload: Record<string, unknown>; delivered_at: string | null }> }>(
      `/events?after_id=${afterId}`,
    ),

  // voice
  voiceCommand: (transcript: string) =>
    request<Record<string, unknown>>("/voice/command", {
      method: "POST",
      body: JSON.stringify({ transcript }),
    }),

  // export
  exportJSON: () => request<Record<string, unknown>>("/export/json"),
};
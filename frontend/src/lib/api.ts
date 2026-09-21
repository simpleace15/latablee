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
  image_path: string | null;
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

  // recipes
  recipes: (q = "", tag = "") =>
    request<Recipe[]>(`/recipes?q=${encodeURIComponent(q)}&tag=${encodeURIComponent(tag)}`),
  recipe: (id: number) => request<Recipe>(`/recipes/${id}`),
  createRecipe: (r: Partial<Recipe>) =>
    request<Recipe>("/recipes", { method: "POST", body: JSON.stringify(r) }),
  updateRecipe: (id: number, r: Partial<Recipe>) =>
    request<Recipe>(`/recipes/${id}`, { method: "PUT", body: JSON.stringify(r) }),
  deleteRecipe: (id: number) => request<void>(`/recipes/${id}`, { method: "DELETE" }),
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

  // import
  importFromUrl: (url: string) =>
    request<{ parsed: Partial<Recipe>; note: string }>("/import/url", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  importFromPhoto: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ parsed: Partial<Recipe>; note: string }>("/import/photo", {
      method: "POST",
      body: form,
    });
  },

  // llm
  llmStatus: () => request<{ configured: boolean }>("/llm/status"),
  llmSettings: () =>
    request<{ base_url: string; model: string; vision_model: string; api_key_set: boolean }>(
      "/llm/settings",
    ),
  saveLLMSettings: (payload: {
    base_url: string;
    api_key: string;
    model: string;
    vision_model: string;
  }) => request<{ saved: boolean }>("/llm/settings", { method: "PUT", body: JSON.stringify(payload) }),
  suggestMeals: () => request<{ suggestions: string }>("/llm/suggest-meals", { method: "POST" }),
  generateRecipe: (payload: { prompt?: string; ingredients?: string[] }) =>
    request<{ parsed: Partial<Recipe> }>("/llm/generate-recipe", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // voice
  voiceCommand: (transcript: string) =>
    request<Record<string, unknown>>("/voice/command", {
      method: "POST",
      body: JSON.stringify({ transcript }),
    }),

  // export
  exportJSON: () => request<Record<string, unknown>>("/export/json"),
};
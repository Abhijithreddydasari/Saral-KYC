const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000/api/v1";

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface ApiResponse<T> {
  data: T;
  status: number;
}

export class ApiClient {
  constructor(private readonly baseUrl: string = API_BASE) {}

  async request<T>(path: string, options: RequestInit = {}, method: HttpMethod = "GET"): Promise<ApiResponse<T>> {
    const headers = new Headers(options.headers);
    const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
    if (!headers.has("Content-Type") && options.body && !isFormData) {
      headers.set("Content-Type", "application/json");
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      method,
      headers,
      cache: "no-store",
    });

    if (!response.ok) {
      const detail = await response.text().catch(() => response.statusText);
      throw new Error(detail || "Request failed");
    }

    const data = (await response.json().catch(() => null)) as T;
    return { data, status: response.status };
  }

  get<T>(path: string, options?: RequestInit) {
    return this.request<T>(path, options, "GET");
  }

  post<T>(path: string, body?: unknown, options?: RequestInit) {
    const payload = body instanceof FormData ? body : JSON.stringify(body ?? {});
    return this.request<T>(
      path,
      {
        ...options,
        body: payload,
        headers: body instanceof FormData ? options?.headers : { "Content-Type": "application/json", ...options?.headers },
      },
      "POST",
    );
  }
}

export const apiClient = new ApiClient();


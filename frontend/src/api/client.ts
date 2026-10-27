import axios from "axios";

const TOKEN_KEY = "admin_token";
export const getToken = () => sessionStorage.getItem(TOKEN_KEY);
export const setToken = (t: string) => sessionStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => sessionStorage.removeItem(TOKEN_KEY);

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  // Ollama chạy CPU có thể mất nhiều thời gian cho lần gọi đầu.
  timeout: 180_000,
  headers: { "Content-Type": "application/json" },
});

// Gắn token admin (nếu có) vào mọi request.
client.interceptors.request.use((config) => {
  const t = getToken();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

// Token sai/hết hạn (401) trên route admin → xóa token + về trang đăng nhập.
client.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error?.response?.status === 401) {
      clearToken();
      if (window.location.pathname.startsWith("/admin")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

export default client;

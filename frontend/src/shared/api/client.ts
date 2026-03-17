import axios, { type AxiosRequestConfig } from 'axios'

const instance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api',
  timeout: 10000,
})

/**
 * Custom Orval mutator.
 * Orval-generated response types wrap in { data, status, headers }.
 * We match that shape so TypeScript types align with runtime values.
 *
 * Auth is handled server-side via Databricks forwarded headers.
 * No browser-managed tokens are needed for same-origin requests.
 */
export const customInstance = <T>(
  url: string,
  options?: RequestInit
): Promise<T> => {
  return instance
    .request({
      url,
      method: options?.method as AxiosRequestConfig['method'],
      data: options?.body,
      headers: options?.headers as AxiosRequestConfig['headers'],
      signal: options?.signal as AxiosRequestConfig['signal'],
    })
    .then(
      (response) =>
        ({
          data: response.data as unknown,
          status: response.status,
          headers: response.headers,
        }) as T
    )
}

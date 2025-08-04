/**
 * API client for making type-safe HTTP requests
 *
 * This module provides a clean abstraction over fetch with proper error handling
 * and type safety, following hexagonal architecture principles.
 */

import { ApiError, isApiError } from '@/types/service';

/**
 * Custom error class for API errors
 */
export class ApiClientError extends Error {
  constructor(
    message: string,
    public status?: number,
    public detail?: string
  ) {
    super(message);
    this.name = 'ApiClientError';
  }
}

/**
 * Configuration for the API client
 */
export interface ApiClientConfig {
  baseUrl: string;
  timeout?: number;
  headers?: Record<string, string>;
}

/**
 * API client class following the adapter pattern
 */
export class ApiClient {
  private config: Required<ApiClientConfig>;

  constructor(config: ApiClientConfig) {
    this.config = {
      baseUrl: config.baseUrl,
      timeout: config.timeout ?? 30000,
      headers: {
        'Content-Type': 'application/json',
        ...config.headers,
      },
    };
  }

  /**
   * Make a GET request
   */
  async get<T>(path: string): Promise<T> {
    return this.request<T>('GET', path);
  }

  /**
   * Make a POST request
   */
  async post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>('POST', path, body);
  }

  /**
   * Make a PUT request
   */
  async put<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>('PUT', path, body);
  }

  /**
   * Make a DELETE request
   */
  async delete<T>(path: string): Promise<T> {
    return this.request<T>('DELETE', path);
  }

  /**
   * Core request method with error handling
   */
  private async request<T>(
    method: string,
    path: string,
    body?: unknown
  ): Promise<T> {
    const url = `${this.config.baseUrl}${path}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.config.timeout);

    try {
      const response = await fetch(url, {
        method,
        headers: this.config.headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        await this.handleErrorResponse(response);
      }

      const data = await response.json();
      return data as T;
    } catch (error) {
      clearTimeout(timeoutId);

      if (error instanceof ApiClientError) {
        throw error;
      }

      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          throw new ApiClientError('Request timeout', 408);
        }
        throw new ApiClientError(error.message);
      }

      throw new ApiClientError('Unknown error occurred');
    }
  }

  /**
   * Handle error responses from the API
   */
  private async handleErrorResponse(response: Response): Promise<never> {
    try {
      const errorData = await response.json();

      if (isApiError(errorData)) {
        throw new ApiClientError(
          errorData.detail,
          response.status,
          errorData.detail
        );
      }

      throw new ApiClientError(
        `Request failed with status ${response.status}`,
        response.status
      );
    } catch (error) {
      if (error instanceof ApiClientError) {
        throw error;
      }

      throw new ApiClientError(
        `Request failed with status ${response.status}`,
        response.status
      );
    }
  }
}

/**
 * Create a singleton instance of the API client
 */
export const apiClient = new ApiClient({
  baseUrl: '/api/proxy',
});

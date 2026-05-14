export interface ApiErrorResponse {
  error: {
    code: string;
    message_key: string;
    message: string;
    details?: {
      fields?: Record<string, { message_key: string; message: string }>;
    };
  };
}

export interface ApiSuccessResponse<T> {
  [key: string]: T;
}

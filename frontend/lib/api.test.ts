import axios from "axios";
import { describe, expect, it } from "vitest";

import { getApiErrorMessage } from "./api";

describe("getApiErrorMessage", () => {
  it("returns a helpful message for network failures", () => {
    const networkError = new axios.AxiosError("Network Error");
    expect(getApiErrorMessage(networkError, "Request failed")).toBe(
      "Cannot reach the API server. Confirm the backend is running on port 8000 and reload the page.",
    );
  });

  it("returns API detail when available", () => {
    const apiError = new axios.AxiosError("Bad Request", "ERR_BAD_REQUEST", undefined, undefined, {
      data: { detail: "Project not found" },
      status: 404,
      statusText: "Not Found",
      headers: {},
      config: {} as never,
    });
    expect(getApiErrorMessage(apiError, "Request failed")).toBe("Project not found");
  });
});

import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import {
  DEFAULT_USER_EMAIL,
  USER_EMAIL_STORAGE_KEY,
  readStoredUserEmail,
  usePersistentUserEmail,
} from "./usePersistentUserEmail";

describe("usePersistentUserEmail", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("defaults to aida@example.com when storage is empty", () => {
    expect(readStoredUserEmail()).toBe(DEFAULT_USER_EMAIL);
  });

  it("reads a trimmed stored email", () => {
    window.localStorage.setItem(USER_EMAIL_STORAGE_KEY, "  dana@example.com  ");

    expect(readStoredUserEmail()).toBe("dana@example.com");
  });

  it("stores non-empty email changes", () => {
    const { result } = renderHook(() => usePersistentUserEmail());

    act(() => {
      result.current.setUserEmail(" mira@example.com ");
    });

    expect(result.current.userEmail).toBe("mira@example.com");
    expect(window.localStorage.getItem(USER_EMAIL_STORAGE_KEY)).toBe("mira@example.com");
  });

  it("keeps the previous stored value when a blank value is provided", () => {
    window.localStorage.setItem(USER_EMAIL_STORAGE_KEY, "aida@example.com");
    const { result } = renderHook(() => usePersistentUserEmail());

    act(() => {
      result.current.setUserEmail("   ");
    });

    expect(result.current.userEmail).toBe("");
    expect(window.localStorage.getItem(USER_EMAIL_STORAGE_KEY)).toBe("aida@example.com");
  });
});

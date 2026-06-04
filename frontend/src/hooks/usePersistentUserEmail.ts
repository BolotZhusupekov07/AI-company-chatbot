import { useState } from "react";

export const DEFAULT_USER_EMAIL = "aida@example.com";
export const USER_EMAIL_STORAGE_KEY = "chat-web-app:user-email";

export interface PersistentUserEmailState {
  userEmail: string;
  setUserEmail: (value: string) => void;
}

export function readStoredUserEmail(storage: Storage = window.localStorage): string {
  const storedValue = storage.getItem(USER_EMAIL_STORAGE_KEY);
  const trimmedValue = storedValue?.trim();
  return trimmedValue || DEFAULT_USER_EMAIL;
}

export function usePersistentUserEmail(): PersistentUserEmailState {
  const [userEmail, setUserEmailState] = useState(() => readStoredUserEmail());

  function setUserEmail(value: string): void {
    const trimmedValue = value.trim();
    setUserEmailState(trimmedValue);

    if (trimmedValue.length > 0) {
      window.localStorage.setItem(USER_EMAIL_STORAGE_KEY, trimmedValue);
    }
  }

  return { userEmail, setUserEmail };
}

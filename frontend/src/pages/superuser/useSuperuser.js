import { createContext, useContext } from "react";

/**
 * Shared superuser state. The provider lives in SuperuserContext.jsx;
 * this file only holds the context object and the consumer hook so that
 * React Fast Refresh keeps working (component files export components only).
 */
export const SuperuserContext = createContext(null);

export function useSuperuser() {
  const value = useContext(SuperuserContext);
  if (!value) {
    throw new Error("useSuperuser must be used inside <SuperuserProvider>.");
  }
  return value;
}


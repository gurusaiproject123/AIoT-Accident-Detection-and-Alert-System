import { createContext, useContext } from 'react';
export const AuthContext = createContext(null);
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('Wrap the application in AuthProvider before using Login or RequireRole.');
  return context;
}

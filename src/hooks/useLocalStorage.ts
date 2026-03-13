import { useState, useEffect, useCallback } from 'react';
export default function useLocalStorage<T>(key: string, defaultValue: T) {
  const [value, setValue] = useState<T>(() => {
    if (typeof window !== 'undefined') {
        try {
            const storedValue = localStorage.getItem(key);
            if (storedValue !== null) {
                return JSON.parse(storedValue);
            }
        } catch (error) {
            console.error(error);
        }
    }
    return defaultValue;
  });

  useEffect(() => {
    if (typeof window !== 'undefined') {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (error) {
            console.error(error);
        }
    }
  }, [key, value]);

  const setValueInLocalStorage = (newValue: T | ((val: T) => T)) => {
      setValue((currentValue) => {
          const result = newValue instanceof Function ? newValue(currentValue) : newValue;
          if (typeof window !== 'undefined') {
            localStorage.setItem(key, JSON.stringify(result));
          }
          return result;
      });
  };

  return [value, setValueInLocalStorage] as const;
}

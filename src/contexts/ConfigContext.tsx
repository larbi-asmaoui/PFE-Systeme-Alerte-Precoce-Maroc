"use client";

import React, { createContext, useContext, ReactNode } from "react";
import config, { Config } from "@/config";
import useLocalStorage from "@/hooks/useLocalStorage";

type ConfigContextType = {
  config: Config;
  setConfig: (newConfig: Config) => void;
  isLoading: boolean;
};

// @ts-ignore
const ConfigContext = createContext<ConfigContextType>(undefined);

interface ConfigProviderProps {
  children: ReactNode;
}

export function ConfigProvider({ children }: ConfigProviderProps) {
  const [configState, setConfigState] = useLocalStorage<Config>(
    "berry-config-ts",
    config,
  );

  const value = {
    config: configState,
    setConfig: setConfigState,
    isLoading: false,
  };

  return (
    <ConfigContext.Provider value={value}>{children}</ConfigContext.Provider>
  );
}

export const useConfig = () => useContext(ConfigContext);

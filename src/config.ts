export const DASHBOARD_PATH = '/';
export const DEFAULT_THEME_MODE = 'system';
export const CSS_VAR_PREFIX = '';

export interface Config {
  fontFamily: string;
  borderRadius: number;
  outlinedFilled: boolean;
  navType: 'light' | 'dark';
  presetColor: 'default' | 'theme1' | 'theme2' | 'theme3' | 'theme4' | 'theme5' | 'theme6';
  locale: string;
  rtlLayout: boolean;
  container: boolean;
}

const config: Config = {
  fontFamily: `'Roboto', sans-serif`,
  borderRadius: 8,
  outlinedFilled: true,
  navType: 'light',
  presetColor: 'default',
  locale: 'en',
  rtlLayout: false,
  container: false
};

export default config;

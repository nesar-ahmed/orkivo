/** Public surface of the auth feature. */

export { LoginForm } from "./components/login-form";
export { RegisterForm } from "./components/register-form";
export { SessionRecovery } from "./components/session-recovery";
export { SignOutButton } from "./components/sign-out-button";
export {
  APP_PREFIX,
  AUTH_PATHS,
  DEFAULT_POST_AUTH_PATH,
  LANDING_PATH,
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  isAppPath,
  isAuthPath,
  isPublicPath,
  safeRedirectTarget,
} from "./auth-policy";
export { login, logout, register, renewSession } from "./api/auth-api";
export {
  isUnauthenticated,
  readCurrentUser,
  readCurrentUserOnce,
  tryReadCurrentUser,
} from "./api/session";

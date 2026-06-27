const DEFAULT_API_ORIGIN = "http://127.0.0.1:8000";

const CSP_DIRECTIVE_DEFAULT_SRC = "default-src 'self'";
const CSP_DIRECTIVE_SCRIPT_SRC = "script-src 'self' 'unsafe-inline' 'unsafe-eval'";
const CSP_DIRECTIVE_STYLE_SRC = "style-src 'self' 'unsafe-inline'";
const CSP_DIRECTIVE_IMG_SRC = "img-src 'self' data: blob:";
const CSP_DIRECTIVE_FONT_SRC = "font-src 'self' data:";
const CSP_DIRECTIVE_FRAME_ANCESTORS = "frame-ancestors 'none'";
const CSP_DIRECTIVE_BASE_URI = "base-uri 'self'";
const CSP_DIRECTIVE_FORM_ACTION = "form-action 'self'";
const CSP_DIRECTIVE_OBJECT_SRC = "object-src 'none'";

const HEADER_CONTENT_SECURITY_POLICY = "Content-Security-Policy";
const HEADER_STRICT_TRANSPORT_SECURITY = "Strict-Transport-Security";
const HEADER_X_CONTENT_TYPE_OPTIONS = "X-Content-Type-Options";
const HSTS_MAX_AGE_SECONDS = 31536000;
const VALUE_STRICT_TRANSPORT_SECURITY = `max-age=${HSTS_MAX_AGE_SECONDS}; includeSubDomains`;
const HEADER_X_FRAME_OPTIONS = "X-Frame-Options";
const HEADER_REFERRER_POLICY = "Referrer-Policy";
const HEADER_PERMISSIONS_POLICY = "Permissions-Policy";

export type SecurityHeader = {
  key: string;
  value: string;
};

function resolveApiOrigin(): string {
  const configuredUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!configuredUrl) {
    return DEFAULT_API_ORIGIN;
  }

  try {
    return new URL(configuredUrl).origin;
  } catch {
    return DEFAULT_API_ORIGIN;
  }
}

export function buildContentSecurityPolicy(apiOrigin: string): string {
  const mediaSources = ["'self'", "blob:", apiOrigin];
  const connectSources = [
    "'self'",
    apiOrigin,
    "ws://127.0.0.1:*",
    "ws://localhost:*",
  ];

  return [
    CSP_DIRECTIVE_DEFAULT_SRC,
    CSP_DIRECTIVE_SCRIPT_SRC,
    CSP_DIRECTIVE_STYLE_SRC,
    CSP_DIRECTIVE_IMG_SRC,
    CSP_DIRECTIVE_FONT_SRC,
    `media-src ${mediaSources.join(" ")}`,
    `connect-src ${connectSources.join(" ")}`,
    CSP_DIRECTIVE_FRAME_ANCESTORS,
    CSP_DIRECTIVE_BASE_URI,
    CSP_DIRECTIVE_FORM_ACTION,
    CSP_DIRECTIVE_OBJECT_SRC,
  ].join("; ");
}

export function buildSecurityHeaders(): SecurityHeader[] {
  const apiOrigin = resolveApiOrigin();

  return [
    {
      key: HEADER_CONTENT_SECURITY_POLICY,
      value: buildContentSecurityPolicy(apiOrigin),
    },
    {
      key: HEADER_STRICT_TRANSPORT_SECURITY,
      value: VALUE_STRICT_TRANSPORT_SECURITY,
    },
    { key: HEADER_X_CONTENT_TYPE_OPTIONS, value: "nosniff" },
    { key: HEADER_X_FRAME_OPTIONS, value: "DENY" },
    { key: HEADER_REFERRER_POLICY, value: "strict-origin-when-cross-origin" },
    {
      key: HEADER_PERMISSIONS_POLICY,
      value: "camera=(), microphone=(), geolocation=()",
    },
  ];
}

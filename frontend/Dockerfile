# AgentAudit frontend — explicit multi-stage build.
# Why not the platform buildpack: it failed on a Next 16 app whose build
# tools (typescript, tailwindcss) are devDependencies; a production-mode
# install skips them and `next build` dies. npm ci here always installs
# the full lockfile.
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
# Primary: strict lockfile install. Fallback: plain resolve — npm 10 (this
# image) rejects some lockfiles npm 11 regenerates locally, and the demo
# must not lose a deploy over lockfile pedantry.
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

FROM node:22-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* values must exist at BUILD time to be inlined into client
# bundles; the platform injects env only at runtime. These two are public
# URLs (no secrets), so they are pinned here deliberately.
ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_BASE=https://agentaudit-api.antideploy.com \
    NEXT_PUBLIC_APP_URL=https://agentaudit-web.antideploy.com
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.ts ./
COPY --from=builder /app/package.json ./
EXPOSE 3000
# PORT is injected by the platform; fall back to Next's default 3000.
CMD ["sh", "-c", "npx next start -p ${PORT:-3000}"]

# Production image: Next.js standalone server.
# Do not bind-mount source over /app — that hides server.js and static assets.
FROM node:22-alpine AS deps
WORKDIR /app
RUN apk add --no-cache libc6-compat
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
RUN apk add --no-cache libc6-compat
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_APP_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_DIST_DIR=.next
RUN if [ -z "$NEXT_PUBLIC_API_URL" ] || [ -z "$NEXT_PUBLIC_APP_URL" ]; then \
      echo "NEXT_PUBLIC_API_URL and NEXT_PUBLIC_APP_URL are required to build the production image"; \
      exit 1; \
    fi && \
    for url in "$NEXT_PUBLIC_API_URL" "$NEXT_PUBLIC_APP_URL"; do \
      echo "$url" | grep -qiE 'localhost|127\.0\.0\.1|0\.0\.0\.0' && { \
        echo "Production image cannot bake localhost into NEXT_PUBLIC_* URLs: $url"; \
        exit 1; \
      }; \
      true; \
    done
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
RUN apk add --no-cache libc6-compat
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]

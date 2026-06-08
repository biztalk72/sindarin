# Hybrid IDP web (Next.js 15 standalone) image.
FROM node:22-slim AS builder
WORKDIR /app
# Rewrite destinations are baked at build time (Next manifest), so the API proxy target must
# be present during `next build`. Compose network default: http://api:8000.
ARG API_PROXY_TARGET=http://api:8000
ENV API_PROXY_TARGET=${API_PROXY_TARGET}
COPY apps/web/package.json apps/web/package-lock.json* ./
RUN npm install
COPY apps/web ./
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]

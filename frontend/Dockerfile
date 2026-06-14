# syntax=docker/dockerfile:1.6

# ---- deps: lockfile-aware npm install ----
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

# ---- builder: next build (standalone) ----
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* 는 빌드 타임에 정적으로 박힘.
# 프로덕션은 같은 origin(Nginx)에서 서빙하므로 빈 문자열 → 상대경로로 호출.
ARG NEXT_PUBLIC_BACKEND_URL=""
ENV NEXT_PUBLIC_BACKEND_URL=$NEXT_PUBLIC_BACKEND_URL

RUN npm run build

# ---- runner: standalone + static만 복사 ----
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Next 14 standalone 산출물 레이아웃:
#   .next/standalone/server.js (+ 최소 node_modules)
#   .next/static            ← 정적 청크. standalone 바깥에 있어 따로 복사.
#   public                  ← 정적 파일. 마찬가지로 따로 복사.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["node", "server.js"]

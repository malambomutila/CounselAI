FROM node:22-alpine AS deps

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ARG NEXT_PUBLIC_API_BASE_URL=
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

RUN npm run build

FROM node:22-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000

RUN addgroup --system counselai && adduser --system --ingroup counselai counselai

# standalone output is a self-contained server.js — no npm or node_modules needed.
COPY --from=builder --chown=counselai:counselai /app/.next/standalone ./
COPY --from=builder --chown=counselai:counselai /app/.next/static ./.next/static
COPY --from=builder --chown=counselai:counselai /app/public ./public

USER counselai

EXPOSE 3000

CMD ["node", "server.js"]

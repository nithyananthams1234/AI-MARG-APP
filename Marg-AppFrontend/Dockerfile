# Builds the MARG web app (static export) and serves it with Caddy, which also
# terminates HTTPS and proxies /api to the backend (see deploy/Caddyfile).
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG EXPO_PUBLIC_API_URL
ENV EXPO_PUBLIC_API_URL=$EXPO_PUBLIC_API_URL
RUN npx expo export --platform web --output-dir dist

FROM caddy:2-alpine
COPY --from=build /app/dist /srv

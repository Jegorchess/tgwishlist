FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Static files are served by Caddy (see deploy/Caddyfile).
FROM caddy:2-alpine
COPY --from=build /app/dist /srv

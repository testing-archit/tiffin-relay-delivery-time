# MP098 web UI  ->  docker build -t mp098-web:1.0 web/
FROM node:24-slim AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM node:24-slim
WORKDIR /web
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
# address of the FastAPI service; overridden in Kubernetes
ENV API_URL=http://localhost:8000
COPY --from=build /web/.next/standalone ./
COPY --from=build /web/.next/static ./.next/static
COPY --from=build /web/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]

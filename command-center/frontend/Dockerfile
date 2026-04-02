FROM node:20-slim AS build

WORKDIR /app
COPY command-center/frontend/package*.json ./
RUN npm ci
COPY command-center/frontend/ .
RUN npm run build

FROM node:20-slim
WORKDIR /app
COPY --from=build /app/.next ./.next
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json .
COPY --from=build /app/public ./public

EXPOSE 3000

CMD ["npm", "start"]

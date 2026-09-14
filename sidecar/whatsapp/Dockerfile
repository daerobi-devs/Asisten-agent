FROM node:20-alpine

WORKDIR /app

# Copy package files and install dependencies
COPY package.json package-lock.json* ./
RUN npm install --omit=dev

# Copy source
COPY server.js ./

EXPOSE 3001

CMD ["node", "server.js"]

# frontend/Dockerfile
FROM node:20-slim

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source
COPY . .

# Expose port
EXPOSE 3000

# Run dev server (for dev mode)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]

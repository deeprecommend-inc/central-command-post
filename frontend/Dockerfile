FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application
COPY . .

# Expose port
EXPOSE 3006

# Set Next.js to use port 3006
ENV PORT=3006

# Default command
CMD ["npm", "run", "dev"]

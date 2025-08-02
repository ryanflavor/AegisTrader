# Use node slim for better performance
FROM node:20-slim

# Accept proxy build arguments
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG NPM_REGISTRY=https://registry.npmmirror.com

# Set proxy environment variables
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}
ENV http_proxy=${HTTP_PROXY}
ENV https_proxy=${HTTPS_PROXY}
ENV no_proxy=${NO_PROXY}

WORKDIR /app

# Copy package files
COPY apps/monitor-ui/package*.json ./

# Configure npm with proxy and install
RUN if [ -n "$HTTP_PROXY" ]; then \
      npm config set proxy $HTTP_PROXY && \
      npm config set https-proxy $HTTPS_PROXY; \
    fi && \
    npm config set registry ${NPM_REGISTRY} && \
    npm install

# Copy application source
COPY apps/monitor-ui/ ./

# Build the application
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Clear proxy env vars for runtime
ENV HTTP_PROXY=""
ENV HTTPS_PROXY=""
ENV http_proxy=""
ENV https_proxy=""

# Expose port
ARG UI_PORT=3100
ENV PORT=${UI_PORT}
EXPOSE ${PORT}

# Run the application
CMD ["npm", "start"]

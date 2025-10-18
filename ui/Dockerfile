FROM nginx:alpine

# No COPY needed - files are mounted as volumes in docker-compose.yml
# This keeps the image small and allows for hot-reload during development

# Expose port 80
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]

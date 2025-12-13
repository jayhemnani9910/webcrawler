FROM node:20-slim
WORKDIR /app
COPY package.json /app/
RUN npm install --production
COPY index.js /app/
EXPOSE 15000
CMD ["node", "index.js"]
